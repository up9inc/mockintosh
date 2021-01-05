FROM python:alpine

WORKDIR /usr/src/mockintosh

COPY requirements.txt .
COPY setup.cfg .
COPY setup.py .
COPY README.md .
COPY mockintosh/ ./mockintosh/

# TODO: git is required for installing pybars3 from GitHub. Remove it when the upstream recieved the update.
RUN apk add git
RUN pip3 install .

ENTRYPOINT ["mockintosh"]
