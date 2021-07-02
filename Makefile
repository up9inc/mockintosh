.PHONY: build

build:
	docker build . -t mockintosh

install:
	pip3 install .

install-dev:
	pip3 install -e .[dev]

install-gpubsub:
	pip3 install -e .[gpubsub]

install-amazonsqs:
	pip3 install -e .[amazonsqs]

test: test-style test-integration test-without-coverage

test-fast: test-style test-without-coverage

coverage: test-with-coverage coverage-after

test-integration: build
	tests_integrated/acceptance.sh && \
	${MAKE} stop-containers

test-without-coverage: copy-assets
	TESTING_ENV=somevalue pytest tests/test_helpers.py -s -vv --log-level=DEBUG && \
	COVERAGE_NO_IMPORT=true pytest tests/test_exceptions.py -s -vv --log-level=DEBUG && \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 pytest tests/test_features.py -s -vv --log-level=DEBUG && \
	${MAKE} test-asyncs

test-with-coverage: test-style copy-assets test-openapi-transpiler
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
	${MAKE} test-asyncs-with-coverage

test-asyncs: test-kafka \
	test-amqp \
	test-redis \
	test-gpubsub \
	test-amazonsqs

test-asyncs-with-coverage: test-kafka-with-coverage \
	test-amqp-with-coverage \
	test-redis-with-coverage \
	test-gpubsub-with-coverage \
	test-amazonsqs-with-coverage

test-kafka: test-kafka-without-coverage

test-kafka-without-coverage: up-kafka
	pytest tests/test_features_async.py::TestAsyncKafka -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-kafka-with-coverage: up-kafka
	COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features_async.py::TestAsyncKafka -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-amqp: test-amqp-without-coverage

test-amqp-without-coverage: up-rabbitmq
	pytest tests/test_features_async.py::TestAsyncAMQP -s -vv --log-level=DEBUG && \
	pytest tests/test_features_async.py::TestAsyncAMQPProperties -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-amqp-with-coverage: up-rabbitmq
	COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features_async.py::TestAsyncAMQP -s -vv --log-level=DEBUG && \
	COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features_async.py::TestAsyncAMQPProperties -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-redis: test-redis-without-coverage

test-redis-without-coverage: up-redis
	pytest tests/test_features_async.py::TestAsyncRedis -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-redis-with-coverage: up-redis
	COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features_async.py::TestAsyncRedis -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-gpubsub: test-gpubsub-without-coverage

test-gpubsub-without-coverage: install-gpubsub up-gpubsub
	PUBSUB_EMULATOR_HOST=localhost:8681 \
	PUBSUB_PROJECT_ID=test-gpubsub \
	pytest tests/test_features_async.py::TestAsyncGpubsub -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-gpubsub-with-coverage: install-gpubsub up-gpubsub
	PUBSUB_EMULATOR_HOST=localhost:8681 \
	PUBSUB_PROJECT_ID=test-gpubsub \
	COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features_async.py::TestAsyncGpubsub -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-amazonsqs: test-amazonsqs-without-coverage

test-amazonsqs-without-coverage: install-amazonsqs up-elasticmq
	pytest tests/test_features_async.py::TestAsyncAmazonSQS -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-amazonsqs-with-coverage: install-amazonsqs up-elasticmq
	COVERAGE_PROCESS_START=true coverage run --parallel -m pytest \
		tests/test_features_async.py::TestAsyncAmazonSQS -s -vv --log-level=DEBUG && \
	${MAKE} stop-containers

test-openapi-transpiler:
	./tests/test-openapi-transpiler.sh

stop-containers:
	docker stop $$(docker ps -a -q) || exit 0

test-style:
	flake8

coverage-after:
	coverage combine && \
	coverage report -m

radon: radon-mi radon-cc

radon-full: radon radon-raw radon-hal

radon-cc:
	radon cc . --show-complexity --average

radon-mi:
	radon mi . --multi --show

radon-raw:
	radon raw . --summary

radon-hal:
	radon hal . --functions

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

copy-assets: copy-certs \
	copy-images \
	copy-data-dir-override \
	copy-amqp \
	copy-redis \
	copy-gpubsub \
	copy-amazonsqs

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

copy-amqp:
	rsync -av tests/configs/yaml/hbs/kafka/ tests/configs/yaml/hbs/amqp/ && \
	python3 ./tests/assets_copy_kafka_to_amqp.py

copy-redis:
	rsync -av tests/configs/yaml/hbs/kafka/ tests/configs/yaml/hbs/redis/ && \
	python3 ./tests/assets_copy_kafka_to_redis.py

copy-gpubsub:
	rsync -av tests/configs/yaml/hbs/kafka/ tests/configs/yaml/hbs/gpubsub/ && \
	python3 ./tests/assets_copy_kafka_to_gpubsub.py

copy-amazonsqs:
	rsync -av tests/configs/yaml/hbs/kafka/ tests/configs/yaml/hbs/amazonsqs/ && \
	python3 ./tests/assets_copy_kafka_to_amazonsqs.py

up-asyncs: up-kafka up-rabbitmq up-redis up-gpubsub up-elasticmq

up-kafka:
	docker run -d -it --rm --name kafka --net=host up9inc/mockintosh:self-contained-kafka && \
	sleep 2

up-rabbitmq:
	docker run -d -it --rm --name rabbitmq --net=host rabbitmq:latest && \
	sleep 10

up-redis:
	docker run -d -it --rm --name redis --net=host redis:latest && \
	sleep 2

up-gpubsub:
	docker run -d -it --rm --name gpubsub --net=host -e PUBSUB_PROJECT1=test-gpubsub,test:test \
		messagebird/gcloud-pubsub-emulator:latest && \
	sleep 2


up-elasticmq:
	docker run -d -it --rm --name elasticmq --net=host softwaremill/elasticmq:latest && \
	sleep 2
