FROM python:3-alpine

COPY ./app ./app
WORKDIR app

RUN pip3 install markupsafe==2.0.1 flask~=1.1.2

EXPOSE 56243

CMD ["python", "./alert_checker.py"]
