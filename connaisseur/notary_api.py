import os
import re
from urllib.parse import quote, urlencode
import requests
from connaisseur.image import Image
from connaisseur.exceptions import (
    NotFoundException,
    UnsupportedTypeException,
    InvalidFormatException,
)
from connaisseur.tuf_role import TUFRole
from connaisseur.trust_data import TrustData
from connaisseur.config import Notary


def get_trust_data(
    notary_config: Notary, image: Image, role: TUFRole, token: str = None
):
    """
    Request the specific trust data, denoted by the `role` and `image` form
    the notary server (`host`). Uses a token, should authentication be
    required.
    """
    if image.repository:
        url = (
            f"https://{notary_config.host}/v2/{image.registry}/{image.repository}/"
            f"{image.name}/_trust/tuf/{role.role}.json"
        )
    else:
        url = (
            f"https://{notary_config.host}/v2/{image.registry}/"
            f"{image.name}/_trust/tuf/{role.role}.json"
        )

    request_kwargs = {"url": url}
    if token:
        request_kwargs["headers"] = {"Authorization": f"Bearer {token}"}
    if notary_config.is_selfsigned:
        request_kwargs["verify"] = notary_config.get_selfsigned_cert()
    response = requests.get(**request_kwargs)

    if not token and response.status_code == 401:
        case_insensitive_headers = {
            k.lower(): response.headers[k] for k in response.headers
        }

        if case_insensitive_headers["www-authenticate"]:
            auth_url = parse_auth(case_insensitive_headers["www-authenticate"])
            token = get_auth_token(notary_config, auth_url)
            return get_trust_data(notary_config, image, role, token)

    if response.status_code == 404:
        raise NotFoundException(
            'no trust data for image "{}".'.format(str(image)), {"tuf_role": role.role}
        )

    response.raise_for_status()

    data = response.json()

    return TrustData(data, role.role)


def get_delegation_trust_data(
    notary_config: Notary, image: Image, role: TUFRole, token: str = None
):
    if os.environ.get("LOG_LEVEL", "INFO") == "DEBUG":
        return get_trust_data(notary_config, image, role, token)

    try:
        return get_trust_data(notary_config, image, role, token)
    except Exception:
        return None


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


def get_auth_token(notary_config: Notary, url: str):
    """
    Return the JWT from the given `url`, using user and password from
    environment variables.

    Raises an exception if a HTTP error status code occurs.
    """
    request_kwargs = {"url": url}

    if notary_config.has_auth:
        auth = notary_config.get_auth()
        request_kwargs["auth"] = requests.auth.HTTPBasicAuth(
            auth.get("USER"), auth.get("PASS")
        )

    if notary_config.is_selfsigned:
        request_kwargs["verify"] = notary_config.get_selfsigned_cert()

    response = requests.get(**request_kwargs)

    if response.status_code >= 500:
        raise NotFoundException(
            "unable to get auth token, likely because of missing trust data.",
            {"auth_url": url},
        )

    response.raise_for_status()

    try:
        if notary_config.is_acr:
            token = response.json()["access_token"]
        else:
            token = response.json()["token"]
    except KeyError:
        raise NotFoundException(
            "no token in authentication server response.", {"auth_url": url}
        )

    token_re = r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$"  # nosec

    if not re.match(token_re, token):
        raise InvalidFormatException(
            "authentication token has wrong format.", {"auth_url": url}
        )
    return token
