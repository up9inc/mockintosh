#!/bin/bash

petstore=tests/configs/oas/petstore.json
COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh $petstore && \
coverage run --parallel -m mockintosh $petstore -c dev.json json && \
coverage run --parallel -m mockintosh $petstore -c dev.yaml yaml && \
coverage run --parallel -m mockintosh $petstore -c dev.yaml && \
jsonschema -i dev.json mockintosh/schema.json || exit 1
