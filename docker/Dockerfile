FROM python:alpine as base

# Build dependencies
FROM base as builder

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt

# Have to upgrade pip and install extra packages due to error when installing frozenlist
# Since we run inside an alpine based container, we cannot compile yarl and multidict
RUN apk add --no-cache gcc~=11.2.1_git20220219-r2 libc-dev~=0.7.2-r3 \
 && pip install --no-cache-dir --upgrade pip~=22.3 \
 && YARL_NO_EXTENSIONS=1 MULTIDICT_NO_EXTENSIONS=1 pip install --no-cache-dir --prefix=/install -r /requirements.txt

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

WORKDIR /app

# Harden image
COPY docker/harden.sh /
RUN sh /harden.sh && rm /harden.sh

# Copy source code and install packages
COPY --from=builder /install /usr/local
COPY --from=cosign_loader /go/cosign/cosign-linux-amd64 /app/cosign/cosign
COPY connaisseur /app/connaisseur

USER 10001:20001

LABEL maintainer="Philipp Belitz <philipp.belitz@securesystems.de>"

CMD ["python", "-m", "connaisseur"]
