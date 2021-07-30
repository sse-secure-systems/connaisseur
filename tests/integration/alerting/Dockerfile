FROM python:3

COPY ./app ./app
WORKDIR app

RUN apt-get update -y
RUN pip3 install flask~=1.1.2

EXPOSE 56243

CMD ["python", "./alert_checker.py"]
