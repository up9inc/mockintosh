.PHONY: build

build:
	docker build . -t mockintosh

install:
	pip3 install .

install-dev:
	pip3 install -e .[dev]

test: test-style test-integration copy-assets up-kafka
	TESTING_ENV=somevalue pytest tests/test_helpers.py -s -vv --log-level=DEBUG && \
	COVERAGE_NO_IMPORT=true pytest tests/test_exceptions.py -s -vv --log-level=DEBUG && \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 pytest tests/test_features.py -s -vv --log-level=DEBUG && \
	docker stop $$(docker ps -a -q)

test-integration: build
	tests_integrated/acceptance.sh && \
	docker stop $$(docker ps -a -q)

test-with-coverage: test-style copy-assets up-kafka
	TESTING_ENV=somevalue coverage run --parallel -m pytest tests/test_helpers.py -s -vv --log-level=DEBUG && \
	COVERAGE_NO_IMPORT=true coverage run --parallel -m pytest tests/test_exceptions.py -s -vv --log-level=DEBUG && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --quiet && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --verbose && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json \
		--bind 127.0.0.1 && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/management/multiresponse.json \
		--enable-tags first,second && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json \
		--logfile dummy.log && \
	COVERAGE_NO_RUN=true DEBUG=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel mockintosh --wrong-arg || \
	coverage run --parallel -m mockintosh tests/configs/yaml/hbs/kafka/config_error.yaml || \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features.py -s -vv --log-level=DEBUG && \
	docker stop $$(docker ps -a -q)

test-style:
	flake8

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

copy-assets: copy-certs copy-images copy-data-dir-override

copy-certs:
	cp tests_integrated/subdir/cert.pem tests/configs/json/hbs/management/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/json/hbs/management/key.pem && \
	cp tests_integrated/subdir/cert.pem tests/configs/yaml/hbs/management/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/yaml/hbs/management/key.pem && \
	cp tests_integrated/subdir/cert.pem tests/configs/yaml/hbs/kafka/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/yaml/hbs/kafka/key.pem && \
	cp tests_integrated/subdir/cert.pem tests/configs/yaml/hbs/core/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/yaml/hbs/core/key.pem

copy-images:
	cp tests/configs/json/hbs/core/image.png tests/configs/yaml/hbs/kafka/
	cp tests/configs/json/hbs/core/image.png tests/configs/json/hbs/core/imagex

copy-data-dir-override:
	cp tests/configs/yaml/hbs/body/body_schema.json tests/configs/yaml/hbs/data_dir_override/
	cp tests/configs/yaml/hbs/body/body_schema_error.json tests/configs/yaml/hbs/data_dir_override/

up-kafka:
	docker run -d -it --net=host up9inc/mockintosh:self-contained-kafka
