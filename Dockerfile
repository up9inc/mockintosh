FROM python:3.9.7-alpine

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

RUN apk add --no-cache gcc musl-dev librdkafka-dev

RUN pip3 install .

WORKDIR /tmp

ENTRYPOINT ["mockintosh"]
