FROM python:alpine

WORKDIR /usr/src/chupeta

COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY chupeta/ ./chupeta/

RUN pip3 install .

ENTRYPOINT ["chupeta"]
