test:
	flake8 && \
	pytest tests -s -vv --log-level=DEBUG && \
	docker build . -t mockintosh && \
	docker run -d -p 8000-8010:8000-8010 -v `pwd`/tests_integrated:/tmp/tests_integrated -e PYTHONPATH=/tmp/tests_integrated mockintosh -v -l /tmp/tests_integrated/server.log --interceptor=custom_interceptors.intercept_for_logging --interceptor=custom_interceptors.intercept_for_modifying /tmp/tests_integrated/integration_config.json && \
	pytest -s -vv --log-level=DEBUG tests_integrated/tests_integration.py && \
	docker stop $$(docker ps -a -q)

test-with-coverage:
	coverage run --parallel -m pytest tests/test_exceptions.py -v --log-level=DEBUG && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --quiet && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --verbose && \
	COVERAGE_NO_RUN=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json --logfile dummy.log && \
	COVERAGE_NO_RUN=true DEBUG=true coverage run --parallel -m mockintosh tests/configs/json/hbs/common/config.json && \
	COVERAGE_PROCESS_START=.coveragerc pytest tests/test_features.py -v --log-level=DEBUG

coverage:
	coverage combine && \
	coverage report -m

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
