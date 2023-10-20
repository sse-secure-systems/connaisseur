import asyncio
import base64
import datetime as dt
import logging

from aiohttp import ClientSession

import connaisseur.constants as const
from connaisseur.exceptions import (
    AmbiguousDigestError,
    InsufficientTrustDataError,
    NotFoundException,
    ValidationError,
)
from connaisseur.image import Image
from connaisseur.trust_root import TrustRoot
from connaisseur.validators.interface import ValidatorInterface
from connaisseur.validators.notaryv1.key_store import KeyStore
from connaisseur.validators.notaryv1.notary import Notary
from connaisseur.validators.notaryv1.tuf_role import TUFRole
from connaisseur.timing import timing


class NotaryV1Validator(ValidatorInterface):
    name: str
    notary: Notary

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.notary = Notary(name, **kwargs)

    @timing(capture_args=["image"])
    async def validate(
        self,
        image: Image,
        session: ClientSession,
        trustRoot: str = None,  # pylint: disable=invalid-name
        delegations: list = None,
        **kwargs,
    ):  # pylint: disable=arguments-differ
        if delegations is None:
            delegations = []
        # get the public root key
        root_key = TrustRoot(self.notary.get_key(trustRoot))
        # prepend `targets/` to the required delegation roles, if not already present
        req_delegations = list(
            map(NotaryV1Validator.__normalize_delegation, delegations)
        )

        # get list of targets fields, containing tag to signed digest mapping from
        # `targets.json` and all potential delegation roles
        signed_image_targets = await self.__process_chain_of_trust(
            session, image, req_delegations, root_key
        )

        # search for digests in given targets
        digests = list(
            map(
                lambda x: NotaryV1Validator.__search_image_targets(x, image),
                signed_image_targets,
            )
        )

        # in case certain delegations are needed, `signed_image_targets` should only
        # consist of delegation role targets. if searched for the signed digest, none of
        # them should be empty
        if req_delegations and not all(digests):
            msg = "Not all required delegations have trust data for image {image}."
            raise InsufficientTrustDataError(message=msg, image=str(image))

        # filter out empty results and squash same elements
        digests = set(filter(None, digests))

        # no digests could be found
        if not digests:
            msg = "Unable to find signed digest for image {image}."
            raise NotFoundException(message=msg, image=str(image))

        # if there is more than one valid digest in the set, no decision can be made,
        # which to chose
        if len(digests) > 1:
            msg = "Found multiple signed digests for image {image}."
            raise AmbiguousDigestError(message=msg, image=str(image))

        return digests.pop()

    @property
    def healthy(self):
        return self.notary.healthy

    @staticmethod
    def __normalize_delegation(delegation_role: str):
        prefix = "targets/"
        if not delegation_role.startswith(prefix):
            delegation_role = prefix + delegation_role
        return delegation_role

    @timing(capture_args=["image"])
    async def __process_chain_of_trust(
        self,
        session: ClientSession,
        image: Image,
        req_delegations: list,
        root_key: TrustRoot,
    ):  # pylint: disable=too-many-branches
        """
        Process the whole chain of trust, provided by the notary
        server (`notary_config`)
        for any given `image`. Request and validate the 'root', 'snapshot',
        'timestamp', 'targets' and potentially 'targets/releases'.
        Additionally, check whether all required delegations are valid.

        Return the signed image targets, which contain the digests.

        Raise `NotFoundExceptions` should no required delegations be present in
        the trust data, or no image targets be found.
        """
        key_store = KeyStore(root_key)

        tuf_roles = ["root", "snapshot", "timestamp", "targets"]

        # load all trust data
        t_start = dt.datetime.now()
        trust_data_list = await asyncio.gather(
            *[
                self.notary.get_trust_data(session, image, TUFRole(role))
                for role in tuf_roles
            ]
        )
        duration = (dt.datetime.now() - t_start).total_seconds()
        logging.debug("Pulled trust data for image %s in %s seconds.", image, duration)
        trust_data = {tuf_roles[i]: trust_data_list[i] for i in range(len(tuf_roles))}

        # validate signature and expiry data of and load root file
        # this does NOT conclude the validation of the root file. To prevent
        # rollback/freeze attacks, the hash still needs to be validated against
        # the snapshot file
        root_trust_data = trust_data["root"]
        root_trust_data.validate_signature(key_store)
        root_trust_data.validate_expiry()

        key_store.update(root_trust_data)

        # validate timestamp file to prevent freeze attacks
        # validates signature and expiry data
        # there is no hash to verify it against since it is short lived
        # TODO should we ensure short expiry duration here?
        timestamp_trust_data = trust_data["timestamp"]
        timestamp_trust_data.validate(key_store)

        # validate snapshot file signature against the key defined in the root file
        # and its hash against the one from the timestamp file
        # and validate expiry
        snapshot_trust_data = trust_data["snapshot"]
        snapshot_trust_data.validate_signature(key_store)

        timestamp_key_store = KeyStore()
        timestamp_key_store.update(timestamp_trust_data)
        snapshot_trust_data.validate_hash(timestamp_key_store)

        snapshot_trust_data.validate_expiry()

        # now snapshot and timestamp files are validated, we can be safe against
        # rollback and freeze attacks if the root file matches the hash of the snapshot
        # file (or the root key has been compromised, which Connaisseur cannot defend
        # against)
        snapshot_key_store = KeyStore()
        snapshot_key_store.update(snapshot_trust_data)
        root_trust_data.validate_hash(snapshot_key_store)

        # if we are safe at this point, we can add the snapshot data to the main KeyStore
        # and proceed with validating the targets file and (potentially) delegation files
        key_store.update(snapshot_trust_data)
        targets_trust_data = trust_data["targets"]
        targets_trust_data.validate(key_store)
        key_store.update(targets_trust_data)

        # if the 'targets.json' has delegation roles defined, get their trust data
        # as well
        if trust_data["targets"].has_delegations() or req_delegations:
            # if no delegations are required, take the "targets/releases" per default
            req_delegations = req_delegations or ["targets/releases"]

            # validate existence of required delegations
            NotaryV1Validator.__validate_all_required_delegations_present(
                req_delegations, trust_data["targets"].get_delegations()
            )

            # download only the required delegation files
            await self.__update_with_delegation_trust_data(
                session, trust_data, req_delegations, key_store, image
            )

            # if certain delegations are required, then only take the targets fields of the
            # required delegation JSONs. otherwise take the targets field of the targets JSON,
            # as long as no delegations are defined in the targets JSON. should there be
            # delegations defined in the targets JSON the targets field of the releases
            # JSON will be used. unfortunately there is a case, where delegations could have
            # been added to a repository, but no signatures were created using the
            # delegations. in this special case, the releases JSON doesn't exist yet and
            # the targets JSON must be used instead
            if req_delegations == ["targets/releases"] and (
                "targets/releases" not in trust_data
                or not trust_data["targets/releases"]
            ):
                req_delegations = ["targets"]
            elif not all(
                target_role in trust_data and trust_data[target_role]
                for target_role in req_delegations
            ):
                tuf_roles = [
                    target_role
                    for target_role in req_delegations
                    if target_role not in trust_data or not trust_data[target_role]
                ]
                msg = (
                    "Unable to find trust data for delegation "
                    "roles {tuf_roles} and image {image}."
                )
                raise NotFoundException(
                    message=msg, tuf_roles=str(tuf_roles), image=str(image)
                )

            image_targets = [
                trust_data[target_role].signed.get("targets", {})
                for target_role in req_delegations
            ]
        else:
            image_targets = [trust_data["targets"].signed.get("targets", {})]

        if not any(image_targets):
            msg = "Unable to find any image digests in trust data."
            raise NotFoundException(message=msg)

        return image_targets

    @staticmethod
    def __search_image_targets(trust_data: dict, image: Image):
        if image.tag:
            if image.tag not in trust_data:
                return None

            base64_digest = trust_data[image.tag]["hashes"][const.SHA256]
            digest = base64.b64decode(base64_digest).hex()

            # if both tag and digest are given
            if image.digest:
                # validate if the digest in the trust_data found by the tag,
                # matches the digest requested by the image reference
                if digest == image.digest:
                    return digest
                else:
                    raise ValidationError(
                        message="Image tag and digest do not match.",
                        tag=image.tag,
                        tag_digest=digest,
                        digest=image.digest,
                    )
            # if only the tag is given
            return digest
        # if only the digest is given
        elif image.digest:
            digest = base64.b64encode(bytes.fromhex(image.digest)).decode("utf-8")
            if digest in {data["hashes"][const.SHA256] for data in trust_data.values()}:
                return image.digest
        return None

    async def __update_with_delegation_trust_data(
        self, session: ClientSession, trust_data, delegations, key_store, image
    ):
        delegation_trust_data_list = await asyncio.gather(
            *[
                self.notary.get_delegation_trust_data(
                    session, image, TUFRole(delegation)
                )
                for delegation in delegations
            ]
        )

        # when delegations are added to the repository, but weren't yet used for signing,
        # the delegation files don't exist yet and are `None`. in this case they are
        # skipped
        delegation_trust_data = {
            delegations[i]: delegation_trust_data_list[i]
            for i in range(len(delegations))
            if delegation_trust_data_list[i]
        }

        for delegation in delegation_trust_data:
            delegation_trust_data[delegation].validate(key_store)
        trust_data.update(delegation_trust_data)

    @staticmethod
    def __validate_all_required_delegations_present(
        required_delegations, present_delegations
    ):
        if required_delegations:
            if present_delegations:
                req_delegations_set = set(required_delegations)
                delegations_set = set(present_delegations)

                # make an intersection between required delegations and actually
                # present ones
                if not req_delegations_set.issubset(delegations_set):
                    missing = list(req_delegations_set - delegations_set)
                    msg = (
                        "Unable to find delegation roles "
                        "{delegation_roles} in trust data."
                    )
                    raise NotFoundException(message=msg, delegation_roles=str(missing))
            else:
                msg = "Unable to find any delegations in trust data."
                raise NotFoundException(message=msg)
