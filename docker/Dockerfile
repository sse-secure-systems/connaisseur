FROM cgr.dev/chainguard/wolfi-base as base

# Build dependencies
FROM base as builder

ARG version=3.11
RUN apk add python-${version} py${version}-pip

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt

# Have to upgrade pip and install extra packages due to error when installing frozenlist
# Since we run inside an alpine based container, we cannot compile yarl and multidict
# also: safety needs gcc no properly install. gcc can't be installed in the final image,
# since apk is no longer available, so safety is added as package to the final image
RUN apk add --no-cache gcc
USER nonroot
RUN YARL_NO_EXTENSIONS=1 MULTIDICT_NO_EXTENSIONS=1 pip install -r /requirements.txt --no-cache-dir --user

# Load and verify Cosign
FROM debian:bullseye-slim as cosign_loader

SHELL ["/bin/bash", "-c"]
ARG COSIGN_VERSION
WORKDIR /go/cosign
COPY docker/release-cosign.pub /go/cosign/release-cosign.pub

RUN apt-get update \
  && apt-get install -y --no-install-recommends openssl=1.1.\* libssl1.1=1.1.\* ca-certificates=20210119\* wget=1.21\* \
  && wget -nv https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64 \
  && wget -nv https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-linux-amd64.sig \
  && openssl dgst -sha256 -verify release-cosign.pub -signature <(base64 -d cosign-linux-amd64.sig) cosign-linux-amd64 \
  && chmod 111 /go/cosign/cosign-linux-amd64

# Build Connaisseur image
FROM base

ARG version=3.11
WORKDIR /app

RUN apk add --no-cache python-${version} && chown -R nonroot.nonroot /app/

USER nonroot

# Copy source code and install packages
COPY --from=builder /home/nonroot/.local/lib/python${version}/site-packages /usr/lib/python${version}/site-packages
COPY --from=builder /home/nonroot/.local/bin /usr/local/bin
COPY --from=cosign_loader /go/cosign/cosign-linux-amd64 /app/cosign/cosign
COPY connaisseur /app/connaisseur

LABEL org.opencontainers.image.documentation="https://sse-secure-systems.github.io/connaisseur/"
LABEL org.opencontainers.image.authors="Philipp Belitz <philipp.belitz@securesystems.de>, Anneke Breust <anneke.breust@securesystems.de>, Christoph Hamsen <christoph.hamsen@securesystems.de>, Teetje Stark <teetje.stark@securesystems.de>"
LABEL org.opencontainers.image.vendor="Secure Systems Engineering"

ENTRYPOINT ["python", "-m", "connaisseur"]
