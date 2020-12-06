FROM python:alpine

WORKDIR /usr/src/chupeta

COPY chupeta/ ./chupeta/
COPY requirements.txt .
COPY setup.cfg .
COPY setup.py .
COPY README.md .

RUN pip3 install .

# EXPOSE 8001
EXPOSE 1-65535

ENTRYPOINT ["chupeta"]
