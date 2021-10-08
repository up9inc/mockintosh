FROM python:3.9.7-slim

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

RUN pip3 install .

WORKDIR /tmp

ENTRYPOINT ["mockintosh"]
