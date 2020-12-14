FROM python:alpine

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

RUN pip3 install .

ENTRYPOINT ["mockintosh"]
