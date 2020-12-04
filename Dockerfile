FROM python:alpine
ENTRYPOINT python -m http.server 8000 | tee -a /tmp/server.log