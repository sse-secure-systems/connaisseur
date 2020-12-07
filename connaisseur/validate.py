import base64
from connaisseur.image import Image
from connaisseur.key_store import KeyStore
from connaisseur.util import normalize_delegation
from connaisseur.notary_api import get_trust_data
from connaisseur.tuf_role import TUFRole
from connaisseur.exceptions import (
    NotFoundException,
    AmbiguousDigestError,
)


def get_trusted_digest(host: str, image: Image, policy_rule: dict):
    """
    Searches in given notary server(`host`) for trust data, that belongs to the
    given `image`, by using the notary API. Also checks whether the given
    `policy_rule` complies.

    Returns the signed digest, belonging to the `image`.
    """
    # concat `targets/` to the  required delegation roles, if not already present
    req_delegations = list(
        map(normalize_delegation, policy_rule.get("delegations", []))
    )

    # get list of targets fields, containing tag to signed digest mapping from
    # `targets.json` and all potential delegation roles
    signed_image_targets = process_chain_of_trust(host, image, req_delegations)

    # search for digests or tag, depending on given image
    search_image_targets = (
        search_image_targets_for_digest
        if image.has_digest()
        else search_image_targets_for_tag
    )

    # filter out the searched for digests, if present
    digests = list(map(lambda x: search_image_targets(x, image), signed_image_targets))

    # in case certain delegations are needed, `signed_image_targets` should only
    # consist of delegation role targets. if searched for the signed digest, none of
    # them should be empty
    if req_delegations and not all(digests):
        raise NotFoundException(
            'not all required delegations have trust data for image "{}".'.format(
                str(image)
            )
        )

    # filter out empty results and squash same elements
    digests = set(filter(None, digests))

    # no digests could be found
    if not digests:
        raise NotFoundException(
            'could not find signed digest for image "{}" in trust data.'.format(
                str(image)
            )
        )

    # if there is more than one valid digest in the set, no decision can be made, which
    # to chose
    if len(digests) > 1:
        raise AmbiguousDigestError("found multiple signed digests for the same image.")

    return digests.pop()


def process_chain_of_trust(host: str, image: Image, req_delegations: list):
    """
    Processes the whole chain of trust, provided by the notary server (`host`)
    for any given `image`. The 'root', 'snapshot', 'timestamp', 'targets' and
    potentially 'targets/releases' are requested in this order and afterwards
    validated, also according to the `policy_rule`.

    Returns the the signed image targets, which contain the digests.

    Raises `NotFoundExceptions` should no required delegetions be present in
    the trust data, or no image targets be found.
    """
    tuf_roles = ["root", "snapshot", "timestamp", "targets"]
    trust_data = {}
    key_store = KeyStore()

    # get all trust data and collect keys (from root and targets), as well as
    # hashes (from snapshot and timestamp)
    for role in tuf_roles:
        trust_data[role] = get_trust_data(host, image, TUFRole(role))
        key_store.update(trust_data[role])

    # if the 'targets.json' has delegation roles defined, get their trust data
    # as well
    if trust_data["targets"].has_delegations():
        for delegation in trust_data["targets"].get_delegations():
            trust_data[delegation] = get_trust_data(host, image, TUFRole(delegation))

    # validate all trust data's signatures, expiry dates and hashes
    for role in trust_data:
        trust_data[role].validate(key_store)

    # validate needed delegations
    if req_delegations:
        if trust_data["targets"].has_delegations():
            delegations = trust_data["targets"].get_delegations()

            req_delegations_set = set(req_delegations)
            delegations_set = set(delegations)

            delegations_set.discard("targets/releases")

            # make an intersection between required delegations and actually
            # present ones
            if not req_delegations_set.issubset(delegations_set):
                missing = list(req_delegations_set - delegations_set)
                raise NotFoundException(
                    "could not find delegation roles {} in trust data.".format(
                        str(missing)
                    )
                )
        else:
            raise NotFoundException("could not find any delegations in trust data.")

    # if certain delegations are required, then only take the targets fields of the
    # required delegation JSON's. otherwise take the targets field of the targets JSON, as
    # long as no delegations are defined in the targets JSON. should there be delegations
    # defined in the targets JSON the targets field of the releases JSON will be used.
    if req_delegations:
        image_targets = [
            trust_data[target_role].signed.get("targets", {})
            for target_role in req_delegations
        ]
    else:
        targets_key = (
            "targets/releases" if trust_data["targets"].has_delegations() else "targets"
        )
        image_targets = [trust_data[targets_key].signed.get("targets", {})]

    if not any(image_targets):
        raise NotFoundException("could not find any image digests in trust data.")

    return image_targets


def search_image_targets_for_digest(trust_data: dict, image: Image):
    """
    Searches in the `trust_data` for a signed digest, given an `image` with
    digest.
    """
    image_digest = base64.b64encode(bytes.fromhex(image.digest)).decode("utf-8")
    if image_digest in {data["hashes"]["sha256"] for data in trust_data.values()}:
        return image.digest

    return None


def search_image_targets_for_tag(trust_data: dict, image: Image):
    """
    Searches in the `trust_data` for a digest, given an `image` with tag.
    """
    image_tag = image.tag
    if image_tag not in trust_data:
        return None

    base64_digest = trust_data[image_tag]["hashes"]["sha256"]
    return base64.b64decode(base64_digest).hex()
