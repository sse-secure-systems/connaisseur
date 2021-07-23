import argparse
import asyncio
import base64

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from connaisseur.image import Image
from connaisseur.validators.notaryv1.notary import Notary
from connaisseur.validators.notaryv1.tuf_role import TUFRole


async def get_pub_root_key(host: str, image: Image):
    notary = Notary("no", host, ["not_empty"])
    root_td = await notary.get_trust_data(image, TUFRole("root"))

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
    root_key_id, root_key = asyncio.run(
        get_pub_root_key(args.server, Image(args.image))
    )
    print(f"KeyID: {root_key_id}\nKey: {root_key}")
