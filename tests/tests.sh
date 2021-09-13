#!/bin/bash -xe

# this file is single entrypoint, to be used in local Dockerized tests
cd $(dirname $0)/..

rm -f .coverage.*
docker ps  # test if docker is operational

tests/ps.sh &

docker kill kafka || true

make install-dev
make test-asyncs
