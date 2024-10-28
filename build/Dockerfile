FROM golang:1.23-alpine AS build

WORKDIR /go/src

COPY go.mod go.sum ./
ENV CGO_ENABLED=0
ENV GOMODCACHE=/root/.cache/go-build
RUN --mount=type=cache,target=/root/.cache/go-build go mod tidy && \
    go mod download -x

COPY . ./
RUN --mount=type=cache,target=/root/.cache/go-build \
    go build -o /go/bin ./cmd/connaisseur

FROM alpine:3 AS certs
# hadolint ignore=DL3018
RUN apk --update --no-cache add ca-certificates

FROM scratch

WORKDIR /
COPY --from=build /go/bin/connaisseur /app/bin/connaisseur
COPY --from=certs /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt

USER 10001:20001

ENTRYPOINT ["/app/bin/connaisseur"]
