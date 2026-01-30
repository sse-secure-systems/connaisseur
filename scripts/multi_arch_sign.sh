REF=$(yq e '.kubernetes.deployment.image.repository' charts/connaisseur/values.yaml)
TAG=v$(yq e '.appVersion' charts/connaisseur/Chart.yaml)
RAW="$(docker buildx imagetools inspect --raw "${REF}:${TAG}")"
SIZE="$(printf "%s" "$RAW" | wc -c | tr -d ' ')"
SHA="$(printf "%s" "$RAW" | sha256sum | awk '{print $1}')"
 
echo "image=$REF:${TAG}"
echo "size=$SIZE sha256=$SHA"

NOTARY_SERVER="https://notary.docker.io"
TRUST_DIR="${HOME}/.docker/trust"
GUN="docker.io/${REF}"


# sign the image with notary
if [ -d "${TRUST_DIR}" ]; then
  echo "Signing image ${REF}:${TAG} with notary..."
  notary -s "${NOTARY_SERVER}" -d "${TRUST_DIR}" addhash \
    "${GUN}" \
    "${TAG}" \
    "${SIZE}" \
    --sha256 "${SHA}" \
    --roles "targets/releases" \
    --publish
else
  echo "Skipping notary signature: TRUST_DIR ${TRUST_DIR} does not exist"
fi


# sign the image with cosign
COSIGN_KEY="${HOME}/.config/cosign/sse.key"
if [ -f "${COSIGN_KEY}" ]; then
  echo "Signing image ${REF}:${TAG} with cosign..."
  cosign sign --key "${COSIGN_KEY}" "${REF}@sha256:${SHA}"
else
  echo "Skipping cosign signature: COSIGN_KEY ${COSIGN_KEY} does not exist"
fi


# sign the image with notation
NOTATION_KEY="${HOME}/.config/notation/localkeys/sse.key"
if [ -f "${NOTATION_KEY}" ]; then
  echo "Signing image ${REF}:${TAG} with notation..."
  notation sign --key "sse" "${GUN}@sha256:${SHA}"
else
  echo "Skipping notation signature: NOTATION_KEY ${NOTATION_KEY} does not exist"
fi
