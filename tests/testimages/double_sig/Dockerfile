FROM gcc@sha256:f993601701a37bef71e7f8fc1ef9410b09b15556f4371b06dcc10202cc81f9ea as builder

WORKDIR /

COPY main.c /main.c
RUN gcc -o /main -static /main.c

FROM scratch

COPY --from=builder /main /main

ENTRYPOINT ["./main"]
