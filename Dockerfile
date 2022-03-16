FROM python:3.9.7-alpine

RUN apk add --no-cache gcc musl-dev librdkafka-dev

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

RUN pip3 install .

WORKDIR /tmp
RUN mockintosh --help

ENTRYPOINT ["mockintosh"]
