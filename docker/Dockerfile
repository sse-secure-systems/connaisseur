FROM python:3-alpine as base

# Build dependencies
FROM base as builder

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt
# Since we run inside an alpine based container, we cannot compile yarl and multidic
RUN YARL_NO_EXTENSIONS=1 MULTIDICT_NO_EXTENSIONS=1 pip install --no-cache-dir --prefix=/install -r /requirements.txt

# Build Cosign
FROM golang:buster as go_builder

ARG COSIGN_VERSION
RUN git clone -b "v${COSIGN_VERSION}" --single-branch --depth 1 https://github.com/sigstore/cosign.git
WORKDIR /go/cosign
RUN GO111MODULE=on CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build ./cmd/cosign/main.go

# Build Connaisseur image
FROM base

WORKDIR /app

# Harden image
COPY docker/harden.sh /
RUN sh /harden.sh && rm /harden.sh

# Copy source code and install packages
COPY --from=builder /install /usr/local
COPY --from=go_builder /go/cosign/main /app/cosign/cosign
COPY connaisseur /app/connaisseur

USER 1000:2000

LABEL maintainer="Philipp Belitz <philipp.belitz@securesystems.de>"

CMD ["python", "-m", "connaisseur"]
