import base64
import os
import re
from urllib.parse import quote, urlencode
import requests
from connaisseur.image import Image
from connaisseur.exceptions import (
    NotFoundException,
    UnsupportedTypeException,
    InvalidFormatException,
    AmbiguousDigestError,
)
from connaisseur.tuf_role import TUFRole
from connaisseur.key_store import KeyStore
from connaisseur.trust_data import TrustData
from connaisseur.util import normalize_delegation


def health_check(host: str):
    """
    Does a health check for a given notary server by using it's API.
    """
    if not host:
        return False

    url = f"https://{host}/_notary_server/health"

    request_kwargs = {"url": url}
    if is_notary_selfsigned():
        request_kwargs["verify"] = "/etc/certs/notary.crt"
    response = requests.get(**request_kwargs)

    return response.status_code == 200


def is_notary_selfsigned():
    """
    Checks whether the notary server should be considered insecure and a
    self-signed certificate needs to be used to contact the server.
    """
    return os.environ.get("SELFSIGNED_NOTARY", "0") == "1"


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

    # get a list from all `targets` fields from `targets.json` + delegation roles or
    # just the delegation roles, should there be required delegation according to the
    # policy
    if req_delegations:
        image_targets = [
            trust_data[target_role].signed.get("targets", {})
            for target_role in req_delegations
        ]
    else:
        image_targets = [
            trust_data[target_role].signed.get("targets", {})
            for target_role in trust_data
            if re.match("targets(/[^/\\s]+)?", target_role)
        ]

    if not any(image_targets):
        raise NotFoundException("could not find any image digests in trust data.")

    return image_targets


def get_trust_data(host: str, image: Image, role: TUFRole, token: str = None):
    """
    Request the specific trust data, denoted by the `role` and `image` form
    the notary server (`host`). Uses a token, should authentication be
    required.
    """
    if image.repository:
        url = (
            f"https://{host}/v2/{image.registry}/{image.repository}/"
            f"{image.name}/_trust/tuf/{role.role}.json"
        )
    else:
        url = (
            f"https://{host}/v2/{image.registry}/"
            f"{image.name}/_trust/tuf/{role.role}.json"
        )

    request_kwargs = {"url": url}
    if token:
        request_kwargs["headers"] = {"Authorization": f"Bearer {token}"}
    if is_notary_selfsigned():
        request_kwargs["verify"] = "/etc/certs/notary.crt"
    response = requests.get(**request_kwargs)

    if not token and response.status_code == 401:
        case_insensitive_headers = {
            k.lower(): response.headers[k] for k in response.headers
        }

        if case_insensitive_headers["www-authenticate"]:
            auth_url = parse_auth(case_insensitive_headers["www-authenticate"])
            token = get_auth_token(auth_url)
            return get_trust_data(host, image, role, token)

    if response.status_code == 404:
        raise NotFoundException(
            'no trust data for image "{}".'.format(str(image)), {"tuf_role": role.role}
        )

    response.raise_for_status()

    data = response.json()

    return TrustData(data, role.role)


def parse_auth(auth_header: str):
    """
    Generates an URL from the 'Www-authenticate' header, where a token can be
    requested.
    """
    auth_types = [
        "Basic",
        "Bearer",
        "Digest",
        "HOBA",
        "Mutual",
        "Negotiate",
        "OAuth",
        "SCRAM-SHA-1",
        "SCRAM-SHA-256",
        "vapid",
    ]
    auth_type_re = re.compile("({}) realm".format("|".join(auth_types)))
    params_re = re.compile(r'(\w+)="?([\w\.\/\:\-\_]+)"?')

    auth_type = next(iter(auth_type_re.findall(auth_header)), None)

    if not auth_type or auth_type != "Bearer":
        raise UnsupportedTypeException(
            "unsupported authentication type for getting trust data.",
            {"auth_header": auth_header},
        )

    params_dict = dict(params_re.findall(auth_header))

    try:
        realm = quote(params_dict.pop("realm"), safe="/:")
    except KeyError:
        raise NotFoundException(
            "could not find any realm in authentication header.",
            {"auth_header": auth_header},
        )
    params = urlencode(params_dict, safe="/:")

    url = f"{realm}?{params}"

    if not url.startswith("https"):
        raise InvalidFormatException(
            "authentication through insecure channel.", {"auth_url": url}
        )

    if ".." in url or url.count("//") > 1:
        raise InvalidFormatException("potential path traversal.", {"auth_url": url})

    return url


def get_auth_token(url: str):
    """
    Return the JWT from the given `url`, using user and password from
    environment variables.

    Raises an exception if a HTTP error status code occurs.
    """
    user = os.environ.get("NOTARY_USER")
    password = os.environ.get("NOTARY_PASS")
    request_kwargs = {"url": url, "auth": requests.auth.HTTPBasicAuth(user, password)}

    if is_notary_selfsigned():
        request_kwargs["verify"] = "/etc/certs/notary.crt"

    response = requests.get(**request_kwargs)

    if response.status_code >= 500:
        raise NotFoundException(
            "unable to get auth token, likely because of missing trust data.",
            {"auth_url": url},
        )

    response.raise_for_status()

    try:
        token = response.json()["token"]
    except KeyError:
        raise NotFoundException(
            "no token in authentication server response.", {"auth_url": url}
        )

    token_re = r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$"

    if not re.match(token_re, token):
        raise InvalidFormatException(
            "authentication token has wrong format.", {"auth_url": url}
        )
    return token


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
