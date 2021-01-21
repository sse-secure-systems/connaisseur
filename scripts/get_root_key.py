import base64
import argparse
import connaisseur.notary_api as api
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from connaisseur.image import Image
from connaisseur.tuf_role import TUFRole


def get_pub_root_key(host: str, image: Image):
    root_td = api.get_trust_data(host, image, TUFRole("root"))

    root_key_id = root_td.signatures[0].get("keyid")
    root_cert_base64 = (
        root_td.get_keys().get(root_key_id, {}).get("keyval", {}).get("public")
    )

    if not root_cert_base64:
        raise Exception("Error getting the root public cert")

    root_cert_pem = base64.b64decode(bytearray(root_cert_base64, "utf-8"))
    root_cert = x509.load_pem_x509_certificate(root_cert_pem, default_backend())
    root_public_bytes = root_cert.public_key().public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    )
    root_public_key = root_public_bytes.decode("utf-8")

    return root_key_id, root_public_key


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Gets the root public key and key ID "
            "from a notary server for a specific image."
        )
    )
    parser.add_argument(
        "--server",
        "-s",
        help="address of the notary server",
        type=str,
        default="notary.docker.io",
    )
    parser.add_argument(
        "--image", "-i", help="name of the image", type=str, required=True
    )
    args = parser.parse_args()
    root_key_id, root_key = get_pub_root_key(args.server, Image(args.image))
    print(f"KeyID: {root_key_id}\nKey: {root_key}")
