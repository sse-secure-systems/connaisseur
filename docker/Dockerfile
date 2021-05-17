FROM python:3-alpine as base

# build dependencies
FROM base as builder

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /requirements.txt

# build cosign
FROM golang:buster as go_builder

ARG COSIGN_VERSION
RUN git clone -b "v${COSIGN_VERSION}" --single-branch --depth 1 https://github.com/sigstore/cosign.git
WORKDIR /go/cosign
RUN GO111MODULE=on CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build ./cmd/cosign/main.go

# build connaisseur image
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
