#!/bin/sh -xe

docker run -d -it --net=host up9inc/mockintosh:self-contained-kafka
docker run -d -it --net=host rabbitmq:latest
docker run -d -it --net=host redis:latest

docker run -it mockintosh --help
docker run -it mockintosh --sample-config /tmp/sample.yml

docker run -d --net=host -v `pwd`/tests_integrated:/tmp/tests_integrated \
    -e PYTHONPATH=/tmp/tests_integrated mockintosh \
    -v \
    -l /tmp/tests_integrated/server.log \
    --interceptor=custom_interceptors.intercept_for_logging \
    --interceptor=custom_interceptors.intercept_for_modifying \
    /tmp/tests_integrated/integration_config.yaml

sleep 5

pytest tests_integrated/tests_integration.py -s -v --log-level=DEBUG # -m kafka