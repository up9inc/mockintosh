# Chupeta, the API mocking server for microservice environments

## About

We aim for cloud-native/microservices, so the main case is many mocks running at once. Also, we aim for small Docker
image size, and small RAM requirement.

Today's services are all about performance, so we offer special features for performance/reliability testing
(see [this section](#performancechaos-profiles)).

We respect the achievements of predecessors (Wiremock, Mockoon etc), we offer similar configuration syntax.

## Build

Installation it directly:

```bash
pip3 install .
```

or as a Docker image:

```bash
docker build -t chupeta .
```

## Run

Running directly:

```bash
chupeta examples/template.j2
```

or as a Docker container:

```bash
docker run -p 8000-8010:8000-8010 -v `pwd`/tests/templates/template.json.j2:/template.json.j2 chupeta /template.json.j2
# or
docker run --network host -v `pwd`/tests/templates/template.json.j2:/template.json.j2 chupeta /template.json.j2
```
