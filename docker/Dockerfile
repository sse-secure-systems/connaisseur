FROM python:alpine as base

# build dependencies
FROM base as builder

RUN mkdir /install
WORKDIR /install
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /requirements.txt

# build connaisseur image
FROM base

WORKDIR /app

# Harden image
COPY docker/harden.sh /
RUN sh /harden.sh && rm /harden.sh

# Copy source code and install packages
COPY --from=builder /install /usr/local
RUN mkdir /app/cosign && echo -e "#!/bin/sh \nexit 1" > /app/cosign/cosign && chmod 777 /app/cosign/cosign
COPY connaisseur /app/connaisseur

USER 1000:2000

LABEL maintainer="Philipp Belitz <philipp.belitz@securesystems.de>"

CMD ["python", "-m", "connaisseur"]
