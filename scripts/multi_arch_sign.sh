set -euo pipefail

REF=$(yq e '.kubernetes.deployment.image.repository' charts/connaisseur/values.yaml)
TAG=v$(yq e '.appVersion' charts/connaisseur/Chart.yaml)
RAW="$(docker buildx imagetools inspect --raw "${REF}:${TAG}")"
SIZE="$(printf "%s" "${RAW}" | wc -c | tr -d ' ')"
SHA="$(printf "%s" "${RAW}" | sha256sum | awk '{print $1}')"

echo "image=${REF}:${TAG}"
echo "size=${SIZE} sha256=${SHA}"
echo

if [[ "${REF}" == docker.io/* ]]; then
  GUN="${REF}"
else
  GUN="docker.io/${REF}"
fi

# potentially set dockerhub auth for notary from docker config
if [[ -n "${NOTARY_AUTH:-}" ]]; then
  echo "Using existing NOTARY_AUTH environment variable"
else
  echo "Trying to use NOTARY_AUTH from docker config"
  CFG="${HOME}/.docker/config.json"
  if [[ ! -f "${CFG}" ]]; then
    echo "No docker config found"
  else
    REGISTRY="$(jq -r '.auths | keys[] | select(contains("docker.io"))' ${CFG})"
    REGISTRY_COUNT=$(jq -r '[.auths | keys[] | select(contains("docker.io"))] | length' ${CFG})
    if [[ ${REGISTRY_COUNT} -gt 1 ]]; then
      echo "Ambiguous. Found ${REGISTRY_COUNT} possible auth configuration for docker.io."
      echo "Continuing without setting NOTARY_AUTH..."
    elif [[ ${REGISTRY_COUNT} -lt 1 ]]; then
      echo "No possible auth configuration for docker.io found."
      echo "Continuing without setting NOTARY_AUTH..."
    else
      echo "Found auth configuration for ${REGISTRY} in ${CFG}"
      read -r -p "Use docker configuration for ${REGISTRY} as auth for Notary? [y/N] " answer
      if [[ "${answer}" == "y" ]]; then
        export NOTARY_AUTH="$(jq -r ".auths.\"${REGISTRY}\".auth" ${CFG})"
      fi
    fi
  fi
fi


# sign the image with notary
NOTARY_SERVER="https://notary.docker.io"
TRUST_DIR="${HOME}/.docker/trust"
if [[ -d "${TRUST_DIR}" ]]; then
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
if [[ -f "${COSIGN_KEY}" ]]; then
  echo "Signing image ${REF}:${TAG} with cosign..."
  cosign sign --key "${COSIGN_KEY}" "${REF}@sha256:${SHA}"
else
  echo "Skipping cosign signature: COSIGN_KEY ${COSIGN_KEY} does not exist"
fi


# sign the image with notation
NOTATION_CFGDIR="${HOME}/.config/notation"
NOTATION_KEY="${NOTATION_CFGDIR}/localkeys/sse.key"
if [[ -f "${NOTATION_KEY}" ]]; then
  if ! grep ${NOTATION_KEY} ${NOTATION_CFGDIR}/signingkeys.json; then
    echo "Key missing from notation cfg"
    exit 1
  fi
  echo "Signing image ${REF}:${TAG} with notation..."
  notation sign --key "sse" "${GUN}@sha256:${SHA}"
else
  echo "Skipping notation signature: NOTATION_KEY ${NOTATION_KEY} does not exist"
fi
