set -euof pipefail

SCRIPT_PATH=$(dirname $0)
SERVICE_NAME=$(yq e '.name' $SCRIPT_PATH/../Chart.yaml)

cd $SCRIPT_PATH
openssl genrsa -out tls.key 4096
cat <<EOF > tls-csr.conf
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[ req_distinguished_name ]

[ v3_req ]
basicConstraints = CA:FALSE
subjectAltName = @alt_names
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[ alt_names ]
DNS.1 = $SERVICE_NAME-svc
DNS.2 = $SERVICE_NAME-svc.$SERVICE_NAME
DNS.3 = $SERVICE_NAME-svc.$SERVICE_NAME.svc
DNS.4 = $SERVICE_NAME-svc.$SERVICE_NAME.svc.cluster.local
EOF

cat <<EOF > tls-crt.conf
[ v3_ca]
basicConstraints = CA:FALSE
subjectAltName = @alt_names
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[ alt_names ]
DNS.1 = $SERVICE_NAME-svc
DNS.2 = $SERVICE_NAME-svc.$SERVICE_NAME
DNS.3 = $SERVICE_NAME-svc.$SERVICE_NAME.svc
DNS.4 = $SERVICE_NAME-svc.$SERVICE_NAME.svc.cluster.local
EOF

openssl req -new -key tls.key -sha256 -config tls-csr.conf -subj "/CN=$SERVICE_NAME-svc.$SERVICE_NAME.svc" -out tls.csr
openssl x509 -req -days 36500 -in tls.csr -signkey tls.key -sha256 -extensions v3_ca -extfile tls-crt.conf -out tls.crt
