FROM python:slim

ARG IMAGE_NAME
ENV IMAGE_NAME $IMAGE_NAME

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

RUN pip3 install .
RUN env
RUN set

ENTRYPOINT ["mockintosh"]
