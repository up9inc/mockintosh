#!/bin/bash -xe

# this file is single entrypoint, to be used in local Dockerized tests
cd $(dirname $0)

rm -f .coverage.*
docker ps  # test if docker is operational
docker kill kafka || true

make build
docker run -it mockintosh --help
docker image ls mockintosh

tests/ps.sh &

make install-dev
make test-with-coverage
make stop-containers
make test-integration