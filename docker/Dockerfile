ARG K6_VERSION=2.3.0
ARG K6_COMMIT=e0887846143ab176d4b5483c9d52cf3b3e009f1a

# Release marker retained so Dependabot continues to surface upstream k6 image
# updates. The runtime binary is rebuilt below so security-qualified Go module
# overrides can be applied without losing exact upstream release provenance.
FROM grafana/k6:2.3.0@sha256:9c2dee7f8ed74d317e4027c06a10f169b625638189de8d4555d0b3486a5aeb34 AS upstream-release

FROM --platform=$BUILDPLATFORM golang:1.27.1-alpine3.24@sha256:8a5910f31396cd4d89662f56c68b3ae31d374308270a1c3bd96672ee5ed43414 AS builder
ARG K6_VERSION
ARG K6_COMMIT
ARG TARGETOS
ARG TARGETARCH

WORKDIR /src/k6
RUN apk add --no-cache git=~2
RUN git init . \
    && git remote add origin https://github.com/grafana/k6.git \
    && git fetch --depth=1 origin "refs/tags/v${K6_VERSION}:refs/tags/v${K6_VERSION}" \
    && git checkout --detach "v${K6_VERSION}" \
    && test "$(git rev-parse HEAD)" = "${K6_COMMIT}"

# Emergency compiled-dependency security overrides live in a deliberately
# minimal repository-owned Go module. Each allowlisted version is applied to
# the ephemeral upstream checkout, verified after Go's module selection, and
# then vendored before compilation. The k6 release tag/commit remain unchanged.
COPY docker/security-overrides/go.mod /tmp/k6-security-overrides.mod
RUN awk ' \
      $1 == "require" && NF == 3 { print $2, $3; next } \
      $1 == "require" && $2 == "(" { in_require = 1; next } \
      in_require && $1 == ")" { in_require = 0; next } \
      in_require && NF == 2 { print $1, $2 } \
    ' /tmp/k6-security-overrides.mod > /tmp/k6-security-overrides.txt \
    && test "$(wc -l < /tmp/k6-security-overrides.txt)" -eq 2 \
    && while read -r MODULE VERSION; do \
         case "${MODULE}" in \
           golang.org/x/crypto|google.golang.org/grpc) GOFLAGS=-mod=mod go get "${MODULE}@${VERSION}" ;; \
           *) echo "unsupported security override: ${MODULE}" >&2; exit 1 ;; \
         esac; \
       done < /tmp/k6-security-overrides.txt \
    && while read -r MODULE VERSION; do \
         test "$(GOFLAGS=-mod=mod go list -m -f '{{.Version}}' "${MODULE}")" = "${VERSION}"; \
       done < /tmp/k6-security-overrides.txt \
    && go mod vendor \
    && CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
       go build -trimpath -o /out/k6

FROM alpine:3.24.2@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6 AS runtime
ARG K6_VERSION
ARG K6_COMMIT

# Keep the final OS package graph governed without consulting or mutating a
# package repository. The patch-versioned runtime base is digest-pinned and
# this stage deliberately installs no additional OS packages. k6 is built with
# CGO disabled; the CA trust bundle is copied from the pinned builder below.

# The trust store is copied from the digest-pinned builder stage rather than
# installing a separate floating ca-certificates package in the runtime stage.
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
RUN adduser -D -u 12345 -g 12345 k6

LABEL org.opencontainers.image.source="https://github.com/grafana/k6" \
      org.opencontainers.image.version="${K6_VERSION}" \
      org.opencontainers.image.revision="${K6_COMMIT}"

WORKDIR /src
COPY --from=builder /out/k6 /usr/bin/k6
COPY --chown=12345:12345 lib /src/lib
COPY --chown=12345:12345 tests /src/tests
RUN mkdir -p /src/reports && chown -R 12345:12345 /src

USER 12345
ENTRYPOINT ["k6"]

# Image startup is deliberately non-traffic-generating. A caller must select
# `run` explicitly and provide K6_BASE_URL before any scenario can send traffic.
CMD ["version"]
