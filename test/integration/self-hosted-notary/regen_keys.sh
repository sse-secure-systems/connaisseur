# This is how the keys were generated. To be executed from this folder, not repo root
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:secp384r1 -days 3650 \
  -nodes -keyout "notary.key" -out "notary.crt" -subj "/CN=notary-server.default.svc.cluster.local" \
  -addext "subjectAltName=DNS:notary-server.default.svc.cluster.local,DNS:*.notary-server.default.svc.cluster.local,DNS:notary-signer.default.svc.cluster.local,DNS:*.notary-signer.default.svc.cluster.local"
cp notary.crt notary-service-container/server/
cp notary.key notary-service-container/server/
mv notary.crt notary-service-container/signer/
mv notary.key notary-service-container/signer/

echo "You still need to adapt values in install.yaml!!!"
