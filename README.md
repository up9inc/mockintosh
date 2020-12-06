# Chupeta, the API mocking server for microservice environments

## About

We aim for cloud-native/microservices, so the main case is many mocks running at once. Also, we aim for small Docker
image size, and small RAM requirement.

Today's services are all about performance, so we offer special features for performance/reliability testing
(see [this section](#performancechaos-profiles)).

We respect the achievements of predecessors (Wiremock, Mockoon etc), we offer similar configuration syntax.

## Build

Installating it directly:

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

or the Docker container:

```bash
docker run -p 8000-8010:8000-8010 -v /home/mertyildiran/Documents/UP9/chupeta/examples/template.j2:/template.j2 chupeta /template.j2
# or
docker run --network host -v /home/mertyildiran/Documents/UP9/chupeta/examples/template.j2:/template.j2 chupeta /template.j2
```
