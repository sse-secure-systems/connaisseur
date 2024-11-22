# This is how the keys were generated. To be executed from this folder, not repo root
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:secp384r1 -days 3650 \
  -nodes -keyout "notary.key" -out "notary.crt" -subj "/CN=notary.server" \
  -addext "subjectAltName=DNS:notary.server,DNS:*.notary.server,DNS:notary.signer,DNS:*.notary.signer"
cp notary.crt server/
cp notary.key server/
mv notary.crt signer/
mv notary.key signer/

echo "You still need to adapt values in install.yaml!!!"
