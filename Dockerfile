FROM python:alpine

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

RUN apk add --no-cache build-base openssl-dev libffi-dev
RUN pip3 install .

ENTRYPOINT ["mockintosh"]
