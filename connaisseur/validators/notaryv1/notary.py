import json
import os
import re
import ssl
from typing import Optional
from urllib.parse import quote, urlencode

import aiohttp
import requests

from connaisseur.exceptions import (
    InvalidFormatException,
    NotFoundException,
    PathTraversalError,
    UnknownTypeException,
)
from connaisseur.image import Image
from connaisseur.validators.notaryv1.trust_data import TrustData
from connaisseur.validators.notaryv1.tuf_role import TUFRole


class Notary:

    name: str
    host: str
    root_keys: list
    is_acr: bool
    auth: dict
    cert: Optional[ssl.SSLContext]

    CERT_PATH = "/app/connaisseur/certs/{}.crt"

    def __init__(
        self,
        name: str,
        host: str,
        trust_roots: list,
        is_acr: bool = False,
        auth: dict = None,
        cert: str = None,
        **kwargs,
    ):  # pylint: disable=unused-argument
        self.name = name
        self.host = host
        self.root_keys = trust_roots or []
        self.is_acr = is_acr
        if auth is None:
            auth = {}
        self.auth = {"login" if k == "username" else k: v for k, v in auth.items()}
        self.cert = self.__get_context(cert) if cert else None

    @staticmethod
    def __get_context(cert: str):
        try:
            return ssl.create_default_context(cadata=cert)
        except Exception:
            return None

    def get_key(self, key_name: str = None):
        """
        Return the public root key with name `key_name` in DER format, without any
        whitespaces. If `key_name` is None, return the top most element of the
        public root key list.

        Raise `NotFoundException` if no top most element can be found.
        """
        key_name = key_name or "default"
        try:
            key = next(key["key"] for key in self.root_keys if key["name"] == key_name)
        except StopIteration as err:
            msg = (
                'Trust root "{key_name}" not configured for validator "{notary_name}".'
            )
            raise NotFoundException(
                message=msg, key_name=key_name, notary_name=self.name
            ) from err
        return "".join(key)

    @property
    def healthy(self):
        if self.is_acr:
            return True

        try:
            url = f"https://{self.host}/_notary_server/health"
            request_kwargs = {"url": url, "verify": self.cert}
            response = requests.get(**request_kwargs)

            return response.status_code == 200
        except Exception:
            return False

    async def get_trust_data(self, image: Image, role: TUFRole, token: str = None):
        im_repo = f"{image.repository}/" if image.repository else ""
        url = (
            f"https://{self.host}/v2/{image.registry}/{im_repo}"
            f"{image.name}/_trust/tuf/{str(role)}.json"
        )

        async with aiohttp.ClientSession() as session:
            request_kwargs = {
                "url": url,
                "ssl": self.cert,
                "headers": ({"Authorization": f"Bearer {token}"} if token else None),
            }
            async with session.get(**request_kwargs) as response:
                status = response.status
                if (
                    status == 401
                    and not token
                    and ("www-authenticate" in [k.lower() for k in response.headers])
                ):
                    auth_url = self.__parse_auth(
                        {k.lower(): v for k, v in response.headers.items()}[
                            "www-authenticate"
                        ]
                    )
                    token = await self.__get_auth_token(auth_url)
                    return await self.get_trust_data(image, role, token)

                if status == 404:
                    msg = "Unable to get {tuf_role} trust data from {notary_name}."
                    raise NotFoundException(
                        message=msg, notary_name=self.name, tuf_role=str(role)
                    )

                response.raise_for_status()
                data = await response.text()
                return TrustData(json.loads(data), str(role))

    async def get_delegation_trust_data(
        self, image: Image, role: TUFRole, token: str = None
    ):
        try:
            return await self.get_trust_data(image, role, token)
        except Exception as ex:
            if os.environ.get("LOG_LEVEL", "INFO") == "DEBUG":
                raise ex
            return None

    def __parse_auth(self, header: str):
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
        auth_type_re = re.compile(f'({"|".join(auth_types)}) realm')
        params_re = re.compile(r'(\w+)="?([\w./:\-_]+)"?')

        auth_type = next(iter(auth_type_re.findall(header)), None)
        params_dict = dict(params_re.findall(header))

        if not auth_type or auth_type != "Bearer":
            msg = (
                "{auth_type} is an unsupported authentication"
                " type in notary {notary_name}."
            )
            raise UnknownTypeException(
                message=msg, auth_type=auth_type, notary_name=self.name
            )

        try:
            realm = quote(params_dict.pop("realm"), safe="/:")
        except KeyError as err:
            msg = (
                "Unable to find authentication realm in auth"
                " header for notary {notary_name}."
            )
            raise NotFoundException(
                message=msg, notary_name=self.name, auth_header=params_dict
            ) from err
        params = urlencode(params_dict, safe="/:")

        url = f"{realm}?{params}"

        if not url.startswith("https"):
            msg = (
                "authentication through insecure channel "
                "for notary {notary_name} is prohibited."
            )
            raise InvalidFormatException(
                message=msg, notary_name=self.name, auth_url=url
            )

        if ".." in url or url.count("//") > 1:
            msg = (
                "Potential path traversal in authentication"
                " url for notary {notary_name}."
            )
            raise PathTraversalError(message=msg, notary_name=self.name, auth_url=url)

        return url

    async def __get_auth_token(self, url: str):
        """
        Return the JWT from the given `url`, using user and password from
        environment variables.

        Raise an exception if a HTTP error status code occurs.
        """
        async with aiohttp.ClientSession() as session:
            request_kwargs = {
                "url": url,
                "ssl": self.cert,
                "auth": (aiohttp.BasicAuth(**self.auth) if self.auth else None),
            }
            async with session.get(**request_kwargs) as response:
                if response.status >= 500:
                    msg = "Unable to get authentication token from {auth_url}."
                    raise NotFoundException(
                        message=msg, notary_name=self.name, auth_url=url
                    )

                response.raise_for_status()

                try:
                    token_key = "access_token" if self.is_acr else "token"
                    token = (await response.json(content_type=None))[token_key]
                except KeyError as err:
                    msg = "Unable to retrieve authentication token from {auth_url} response."
                    raise NotFoundException(
                        message=msg, notary_name=self.name, auth_url=url
                    ) from err

                token_re = (
                    r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$"  # nosec
                )

                if not re.match(token_re, token):
                    msg = "{validation_kind} has an invalid format."
                    raise InvalidFormatException(
                        message=msg,
                        validation_kind="Authentication token",
                        notary_name=self.name,
                        auth_url=url,
                    )
                return token
