.PHONY: build

build:
	docker build . -t mockintosh

install:
	pip3 install .

install-dev:
	pip3 install -e .[dev]

test: test-integration copy-certs
	flake8 && \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 pytest tests -s -vv --log-level=DEBUG

test-integration: build
	docker run -d -p 8000-8010:8000-8010 -v `pwd`/tests_integrated:/tmp/tests_integrated \
		-e PYTHONPATH=/tmp/tests_integrated mockintosh \
		-v \
		-l /tmp/tests_integrated/server.log \
		--interceptor=custom_interceptors.intercept_for_logging \
		--interceptor=custom_interceptors.intercept_for_modifying \
		/tmp/tests_integrated/integration_config.yaml && \
	sleep 5 && \
	pytest tests_integrated/tests_integration.py -s -vv --log-level=DEBUG && \
	docker stop $$(docker ps -a -q)

test-with-coverage: copy-certs
	coverage run --parallel -m pytest tests/test_exceptions.py -s -vv --log-level=DEBUG && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --quiet && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --verbose && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json \
		--logfile dummy.log && \
	COVERAGE_NO_RUN=true DEBUG=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel mockintosh --wrong-arg || \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 COVERAGE_PROCESS_START=.coveragerc pytest tests/test_features.py -s -vv --log-level=DEBUG

coverage-after:
	coverage combine && \
	coverage report -m

coverage: test-with-coverage coverage-after

cert:
	openssl req \
		-new \
		-newkey rsa:4096 \
		-days 3650 \
		-nodes \
		-x509 \
		-subj "/C=US/ST=California/L=San Francisco/O=UP9.com/CN=Mockintosh" \
		-keyout mockintosh/ssl/key.pem \
		-out mockintosh/ssl/cert.pem

copy-certs:
	cp tests_integrated/subdir/cert.pem tests/configs/json/hbs/management/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/json/hbs/management/key.pem && \
	cp tests_integrated/subdir/cert.pem tests/configs/yaml/hbs/management/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/yaml/hbs/management/key.pem
