import base64
import re

import ecdsa
import rsa

from connaisseur.exceptions import InvalidFormatException

KMS_REGEX = r"^(awskms|gcpkms|azurekms|hashivault|k8s):\/{2,3}[a-zA-Z0-9_.+\/:-]+$"
KEYLESS_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class TrustRootInterface:
    """
    Interface from which all trust roots inherit.
    """

    def __new__(cls, data: object):
        instance = super(TrustRootInterface, cls).__new__(cls)
        instance.__init__(data)
        return instance

    def __init__(self, data: object) -> None:
        self.value = data

    def __str__(self) -> str:
        return self.value


class TrustRoot(TrustRootInterface):
    """
    Abstract TrustRoot class used to represent key material or similar entities, used in
    verification processes.

    May contain a public key, reference to a key or any other type of trust root.
    """

    value: object

    def __new__(cls, data: str):
        try:
            tr_cls, tr_data = TrustRoot.__get_type_cls_and_data(data)
            return tr_cls.__new__(tr_cls, tr_data)
        except Exception as err:
            msg = "Error loading the trust root."
            raise InvalidFormatException(message=msg) from err

    @staticmethod
    def __get_type_cls_and_data(data: str):
        if re.match(KEYLESS_REGEX, data):
            return KeyLessTrustRoot, data
        elif re.match(KMS_REGEX, data):
            return KMSKey, data
        elif key := TrustRoot.__check_and_return_ecdsa(data):
            return ECDSAKey, key
        elif key := TrustRoot.__check_and_return_rsa(data):
            return RSAKey, key
        return None, data

    @staticmethod
    def __check_and_return_ecdsa(data: str):
        try:
            return ecdsa.VerifyingKey.from_pem(data)
        except Exception:
            return None

    @staticmethod
    def __check_and_return_rsa(data: str):
        try:
            return rsa.PublicKey.load_pkcs1_openssl_pem(data)
        except Exception:
            return None


class ECDSAKey(TrustRootInterface):
    def __str__(self) -> str:
        return base64.b64encode(self.value.to_der()).decode("utf-8")


class RSAKey(TrustRootInterface):
    def __str__(self) -> str:
        return base64.b64encode(self.value.save_pkcs1("DER")).decode("utf-8")


class KMSKey(TrustRootInterface):
    pass


class KeyLessTrustRoot(TrustRootInterface):
    pass
