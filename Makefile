.PHONY: build

build:
	docker build . -t mockintosh

install:
	pip3 install .

install-dev:
	pip3 install -e .[dev]

test: test-integration copy-certs start-kafka
	flake8 && \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 pytest tests -s -vv --log-level=DEBUG && \
	${MAKE} stop-kafka

test-integration: build start-kafka
	docker run -d -p 8000-8010:8000-8010 --add-host host.docker.internal:host-gateway -v `pwd`/tests_integrated:/tmp/tests_integrated \
		-e PYTHONPATH=/tmp/tests_integrated mockintosh \
		-v \
		-l /tmp/tests_integrated/server.log \
		--interceptor=custom_interceptors.intercept_for_logging \
		--interceptor=custom_interceptors.intercept_for_modifying \
		/tmp/tests_integrated/integration_config.yaml && \
	sleep 5 && \
	KAFK=host.docker.internal pytest tests_integrated/tests_integration.py -s -vv --log-level=DEBUG && \
	docker stop $$(docker ps -a -q) && stop-kafka

test-with-coverage: copy-certs start-kafka
	coverage run --parallel -m pytest tests/test_helpers.py -s -vv --log-level=DEBUG && \
	coverage run --parallel -m pytest tests/test_exceptions.py -s -vv --log-level=DEBUG && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --quiet && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --verbose && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json \
		--logfile dummy.log && \
	COVERAGE_NO_RUN=true DEBUG=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel mockintosh --wrong-arg || \
	MOCKINTOSH_FALLBACK_TO_TIMEOUT=3 COVERAGE_PROCESS_START=.coveragerc pytest \
		tests/test_features.py -s -vv --log-level=DEBUG && \
	${MAKE} stop-kafka

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
	cp tests_integrated/subdir/key.pem tests/configs/yaml/hbs/management/key.pem && \
	cp tests_integrated/subdir/cert.pem tests/configs/json/hbs/kafka/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/json/hbs/kafka/key.pem && \
	cp tests_integrated/subdir/cert.pem tests/configs/yaml/hbs/kafka/cert.pem && \
	cp tests_integrated/subdir/key.pem tests/configs/yaml/hbs/kafka/key.pem

download-kafka:
	curl -o kafka.tgz https://downloads.apache.org/kafka/2.7.0/kafka_2.13-2.7.0.tgz && \
	tar -xzf kafka.tgz && \
	mv kafka_2.13-2.7.0 kafka

start-kafka:
	rm -rf /tmp/kafka-logs && \
	rm -rf /tmp/zookeeper && \
	kafka/bin/zookeeper-server-start.sh kafka/config/zookeeper.properties & \
	echo "$$!" > "kafka_zookeeper.pid" && \
	sleep 5 && \
	kafka/bin/kafka-server-start.sh kafka/config/server.properties & \
	echo "$$!" > "kafka_server.pid" && \
	sleep 5

stop-kafka:
	kill -9 $$(cat kafka_server.pid) && \
	kill -9 $$(cat kafka_zookeeper.pid)
