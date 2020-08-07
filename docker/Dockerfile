FROM python:alpine

WORKDIR /app

# Copy source code and install packages
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY connaisseur /app/connaisseur

LABEL maintainer="Philipp Belitz <philipp.belitz@securesystems.de>"

CMD ["python", "-m", "connaisseur"]
