set -euof pipefail

SCRIPT_PATH=$(dirname $0)
SERVICE_NAME=$(yq r $SCRIPT_PATH/../Chart.yaml name)

cd $SCRIPT_PATH
openssl genrsa -out ca.key 4096

cat <<EOF > ca.conf
[ req ]
default_bits       = 4096
default_md         = sha512
default_keyfile    = ca.key
prompt             = no
encrypt_key        = yes

# base request
distinguished_name = req_distinguished_name

# distinguished_name
[ req_distinguished_name ]
countryName            = "DE"
stateOrProvinceName    = "Berlin"
localityName           = "Berlin"
organizationName       = "SSE"
organizationalUnitName = "Engineering Department"
commonName             = "connaisseur.internal"
emailAddress           = "no-reply@securesystems.de"
EOF
openssl req -new -x509 -key ca.key -out ca.crt -config ca.conf

openssl genrsa -out tls-key.pem 4096
cat <<EOF > tls.conf
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[ req_distinguished_name ]
[ v3_req ]
basicConstraints=CA:FALSE
subjectAltName=@alt_names
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[ alt_names ]
DNS.1 = $SERVICE_NAME-svc
DNS.2 = $SERVICE_NAME-svc.$SERVICE_NAME
DNS.3 = $SERVICE_NAME-svc.$SERVICE_NAME.svc
DNS.4 = $SERVICE_NAME-svc.$SERVICE_NAME.svc.cluster.local
EOF
openssl req -new -key tls-key.pem -subj "/CN=$SERVICE_NAME-svc.$SERVICE_NAME.svc" -out tls.csr -config tls.conf
openssl x509 -req -in tls.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out tls-crt.pem
