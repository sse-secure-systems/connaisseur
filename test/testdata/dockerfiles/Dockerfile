FROM gcc@sha256:f993601701a37bef71e7f8fc1ef9410b09b15556f4371b06dcc10202cc81f9ea AS builder

ARG MESSAGE
ENV MESSAGE=$MESSAGE

WORKDIR /

RUN apt update && apt install -y gettext

COPY main.c /main.c
RUN envsubst < /main.c > /main_.c
RUN gcc -o /main -static /main_.c

FROM scratch

COPY --from=builder /main /main

ENTRYPOINT ["./main"]
