FROM python:alpine

WORKDIR /app

# Harden image
COPY docker/harden.sh /
RUN sh /harden.sh && rm /harden.sh

# Copy source code and install packages
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY connaisseur /app/connaisseur

USER 1000:2000

LABEL maintainer="Philipp Belitz <philipp.belitz@securesystems.de>"

CMD ["python", "-m", "connaisseur"]
