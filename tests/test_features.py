#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests mock server's features.
"""

import os
import random
import re
import time
import json
import socket
import threading
import subprocess
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

import yaml
import pytest
import httpx
from openapi_spec_validator import validate_spec
from jsonschema.validators import validate as jsonschema_validate
from backports.datetime_fromisoformat import MonkeyPatch

import mockintosh
from mockintosh import kafka
from mockintosh.constants import PROGRAM, BASE64, PYBARS
from mockintosh.performance import PerformanceProfile
from mockintosh.methods import _b64encode
from utilities import (
    tcping,
    run_mock_server,
    get_config_path,
    nostdout,
    nostderr,
    is_valid_uuid,
    is_ascii
)

MonkeyPatch.patch_fromisoformat()

__location__ = os.path.abspath(os.path.dirname(__file__))

configs = [
    'configs/json/hbs/common/config.json',
    'configs/json/j2/common/config.json',
    'configs/yaml/hbs/common/config.yaml',
    'configs/yaml/j2/common/config.yaml'
]

MGMT = os.environ.get('MGMT', 'https://localhost:8000')
SRV_8000 = os.environ.get('SRV1', 'http://localhost:8000')
SRV_8001 = os.environ.get('SRV1', 'http://localhost:8001')
SRV_8002 = os.environ.get('SRV2', 'http://localhost:8002')
SRV_8003 = os.environ.get('SRV2', 'http://localhost:8003')
SRV_8004 = os.environ.get('SRV2', 'http://localhost:8004')

SRV_8001_HOST = 'service1.example.com'
SRV_8002_HOST = 'service2.example.com'
SRV_8003_HOST = 'service3.example.com'
SRV_8004_HOST = 'service4.example.com'

SRV_8001_SSL = SRV_8001[:4] + 's' + SRV_8001[4:]
SRV_8002_SSL = SRV_8002[:4] + 's' + SRV_8002[4:]
SRV_8003_SSL = SRV_8003[:4] + 's' + SRV_8003[4:]

KAFKA_ADDR = os.environ.get('KAFKA_ADDR', 'localhost:9092')
KAFKA_CONSUME_WAIT = os.environ.get('KAFKA_CONSUME_WAIT', 10)

HAR_JSON_SCHEMA = {"$ref": "https://raw.githubusercontent.com/undera/har-jsonschema/master/har-schema.json"}

should_cov = os.environ.get('COVERAGE_PROCESS_START', False)


@pytest.mark.parametrize(('config'), configs)
class TestCommon():

    def setup_method(self):
        config = self._item.callspec.getparam('config')
        self.mock_server_process = run_mock_server(get_config_path(config))

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_ping_ports(self, config):
        ports = (8001, 8002)
        for port in ports:
            result, _ = tcping('localhost', port)
            if not result:
                raise AssertionError("Port %d is closed!" % port)

    def test_users(self, config):
        resp = httpx.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['total'], int)
        assert isinstance(data['users'], list)
        assert isinstance(data['users'][0]['id'], int)
        assert data['users'][0]['firstName']
        assert isinstance(data['users'][0]['firstName'], str)
        assert data['users'][0]['lastName']
        assert isinstance(data['users'][0]['lastName'], str)
        assert isinstance(data['users'][0]['friends'], list) or data['users'][0]['friends'] is None

    def test_user(self, config):
        user_id = random.randint(1, 1000)
        resp = httpx.get(SRV_8001 + '/users/%s' % user_id, headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['id'], int)
        assert data['firstName']
        assert isinstance(data['firstName'], str)
        assert data['lastName']
        assert isinstance(data['lastName'], str)
        assert isinstance(data['friends'], list) or data['friends'] is None

    def test_companies(self, config):
        resp = httpx.post(SRV_8002 + '/companies', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['total'], int)
        assert isinstance(data['companies'], list)
        assert data['companies'][0]['name']
        assert isinstance(data['companies'][0]['name'], str)
        assert data['companies'][0]['motto']
        assert isinstance(data['companies'][0]['motto'], str)


class TestCommandLineArguments():

    def setup_method(self):
        self.mock_server_process = None

    def teardown_method(self):
        if self.mock_server_process is not None:
            self.mock_server_process.terminate()

    def test_no_arguments(self):
        with nostderr():
            self.mock_server_process = run_mock_server()
        assert self.mock_server_process.is_alive() is False

    @pytest.mark.parametrize(('config'), configs)
    def test_wrong_argument(self, config):
        with nostderr():
            self.mock_server_process = run_mock_server(get_config_path(config), '--wrong-option', wait=1)
        assert self.mock_server_process.is_alive() is False

    @pytest.mark.parametrize(('config'), configs)
    def test_missing_config_file(self, config):
        with nostderr():
            self.mock_server_process = run_mock_server('missing_file.json', wait=1)
        assert self.mock_server_process.is_alive() is False

    @pytest.mark.parametrize(('config'), configs)
    def test_quiet(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--quiet')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_verbose(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--verbose')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_bind_address(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--bind', '127.0.0.1')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_interceptor_single(self, config):
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.dummy1'
        )
        resp = httpx.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
        assert 414 == resp.status_code

    @pytest.mark.parametrize(('config'), configs)
    def test_interceptor_multiple(self, config):
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.dummy1',
            '--interceptor=interceptingpackage.interceptors.dummy2'
        )
        resp = httpx.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
        assert 417 == resp.status_code

    def test_logfile(self):
        config = 'configs/not_existing_file'
        logfile_name = 'error.log'
        if os.path.isfile(logfile_name):
            os.remove(logfile_name)
        self.mock_server_process = run_mock_server(get_config_path(config), '--logfile', logfile_name)
        assert self.mock_server_process.is_alive() is False
        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            error_log = file.read()
            assert 'Mock server loading error' in error_log and 'No such file or directory' in error_log

    def test_services_list(self):
        config = 'configs/json/hbs/core/multiple_services_on_same_port.json'
        self.mock_server_process = run_mock_server(get_config_path(config), 'Mock for Service1')

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8001 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service3', headers={'Host': SRV_8003_HOST})
        assert 404 == resp.status_code

    def test_port_override(self):
        os.environ['MOCKINTOSH_FORCE_PORT'] = '8002'
        config = 'configs/json/hbs/core/multiple_services_on_same_port.json'
        self.mock_server_process = run_mock_server(get_config_path(config), 'Mock for Service1')

        resp = httpx.get(SRV_8002 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        result, _ = tcping('localhost', '8001')
        assert not result


class TestInterceptors():

    def setup_method(self):
        self.mock_server_process = None

    def teardown_method(self):
        if self.mock_server_process is not None:
            self.mock_server_process.terminate()

    @pytest.mark.parametrize(('config'), configs)
    def test_not_existing_path(self, config):
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.not_existing_path'
        )
        resp = httpx.get(SRV_8003 + '/interceptor-modified')
        assert 201 == resp.status_code
        assert 'intercepted' == resp.text
        assert resp.headers['someheader'] == 'some-i-val'

    @pytest.mark.parametrize(('config'), configs)
    def test_intercept_logging(self, config):
        logfile_name = 'server.log'
        if os.path.isfile(logfile_name):
            os.remove(logfile_name)
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.intercept_logging',
            '--logfile',
            logfile_name
        )
        resp = httpx.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as fp:
            assert any('Processed intercepted request' in line for line in fp)

    @pytest.mark.parametrize(('config'), configs)
    def test_request_object(self, config):
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.request_object'
        )
        resp = httpx.get(
            SRV_8003 + '/request1?a=hello%20world&b=3',
            headers={'Cache-Control': 'no-cache'}
        )
        assert 200 == resp.status_code

        resp = httpx.post(
            SRV_8003 + '/request2',
            data={'param1': 'value1', 'param2': 'value2'}
        )
        assert 200 == resp.status_code


class TestCore():

    def setup_method(self):
        self.mock_server_process = None

    def teardown_method(self):
        if self.mock_server_process is not None:
            self.mock_server_process.terminate()

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/no_templating_engine.json',
        'configs/json/j2/core/no_templating_engine.json',
        'configs/yaml/hbs/core/no_templating_engine.yaml',
        'configs/yaml/j2/core/no_templating_engine.yaml'
    ])
    def test_no_templating_engine_should_default_to_handlebars(self, config):
        var = 'print_this'
        with nostdout() and nostderr():
            self.mock_server_process = run_mock_server(get_config_path(config))
        resp = httpx.get(SRV_8001 + '/%s' % var, headers={'Host': SRV_8001_HOST})
        if 'j2' in config:
            assert 404 == resp.status_code
        else:
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == var

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/templating_engine_in_response.json',
        'configs/json/j2/core/templating_engine_in_response.json',
        'configs/yaml/hbs/core/templating_engine_in_response.yaml',
        'configs/yaml/j2/core/templating_engine_in_response.yaml'
    ])
    def test_correct_templating_engine_in_response_should_render_correctly(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = httpx.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['hello'], str)

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/no_templating_engine_in_response.json',
        'configs/json/j2/core/no_templating_engine_in_response.json',
        'configs/yaml/hbs/core/no_templating_engine_in_response.yaml',
        'configs/yaml/j2/core/no_templating_engine_in_response.yaml'
    ])
    def test_no_templating_engine_in_response_should_default_to_handlebars(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = httpx.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})

        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        if 'j2' in config:
            assert data['hello'] == '{{ fake.first_name() }}'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/no_use_templating_no_templating_engine_in_response.json',
        'configs/json/j2/core/no_use_templating_no_templating_engine_in_response.json',
        'configs/yaml/hbs/core/no_use_templating_no_templating_engine_in_response.yaml',
        'configs/yaml/j2/core/no_use_templating_no_templating_engine_in_response.yaml'
    ])
    def test_no_use_templating_no_templating_engine_in_response_should_default_to_handlebars(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = httpx.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})

        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        if 'j2' in config:
            assert data['hello'] == '{{ fake.first_name() }}'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/use_templating_false_in_response.json',
        'configs/json/j2/core/use_templating_false_in_response.json',
        'configs/yaml/hbs/core/use_templating_false_in_response.yaml',
        'configs/yaml/j2/core/use_templating_false_in_response.yaml'
    ])
    def test_use_templating_false_should_not_render(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = httpx.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})

        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'

    def test_multiple_services_on_same_port(self):
        config = 'configs/json/hbs/core/multiple_services_on_same_port.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8001 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

    def test_two_services_one_with_hostname_one_without(self):
        config = 'configs/json/hbs/core/two_services_one_with_hostname_one_without.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        # Service 1 (the one without the hostname) should accept any `Host` header
        resp = httpx.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        # Service 2 (the one with the hostname) should require a correct `Host` header
        resp = httpx.get(SRV_8002 + '/')
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8002 + '/', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

    def test_endpoint_id_header(self):
        config = 'configs/json/hbs/core/endpoint_id_header.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['X-%s-Endpoint-Id' % PROGRAM] == 'endpoint-id-1'

        resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['X-%s-Endpoint-Id' % PROGRAM] == 'endpoint-id-2'

    def test_http_verbs(self):
        config = 'configs/json/hbs/core/http_verbs.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'GET request'

        resp = httpx.get(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'GET request'

        resp = httpx.post(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'POST request'

        resp = httpx.head(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == ''

        resp = httpx.delete(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'DELETE request'

        resp = httpx.patch(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'PATCH request'

        resp = httpx.put(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'PUT request'

        resp = httpx.options(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'OPTIONS request'

    def test_http_verb_not_allowed(self):
        config = 'configs/json/hbs/core/http_verbs.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/method-not-allowed-unless-post')
        assert 405 == resp.status_code
        assert 'Supported HTTP methods: POST' == resp.text

        resp = httpx.post(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code
        assert 'Supported HTTP methods: GET' == resp.text

        resp = httpx.head(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code

        resp = httpx.delete(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code
        assert 'Supported HTTP methods: GET' == resp.text

        resp = httpx.patch(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code
        assert 'Supported HTTP methods: GET' == resp.text

        resp = httpx.put(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code
        assert 'Supported HTTP methods: GET' == resp.text

        resp = httpx.options(SRV_8001 + '/method-not-allowed-unless-get')
        assert 404 == resp.status_code

    def test_no_response_body_204(self):
        config = 'configs/json/hbs/core/no_response_body_204.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/endpoint1')
        assert 204 == resp.status_code

    def test_empty_response_body(self):
        config = 'configs/json/hbs/core/empty_response_body.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/endpoint1')
        assert 200 == resp.status_code
        assert resp.text == ''

    def test_binary_response(self):
        config = 'configs/json/hbs/core/binary_response.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['hello'], str)

        resp = httpx.get(SRV_8001 + '/image')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'image/png'
        with open(get_config_path('configs/json/hbs/core/image.png'), 'rb') as file:
            assert resp.content == file.read()

    def test_binary_request_body(self):
        config = 'configs/yaml/hbs/core/binary_request_body.yaml'
        self.mock_server_process = run_mock_server(get_config_path(config))

        with open(get_config_path('configs/json/hbs/core/image.png'), 'rb') as file:
            image_file = file.read()
            resp = httpx.post(SRV_8001 + '/endpoint1', files={'example': image_file})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == _b64encode(image_file)

            resp = httpx.post(SRV_8001 + '/endpoint1', data={'example': image_file})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == _b64encode(image_file)

    def test_ssl_true(self):
        config = 'configs/json/hbs/core/ssl_true.json'
        self.mock_server_process = run_mock_server(get_config_path(config), wait=20)

        resp = httpx.get(SRV_8001_SSL + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

        resp = httpx.get(SRV_8003_SSL + '/service3', headers={'Host': SRV_8003_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service3'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/undefined.json',
        'configs/json/j2/core/undefined.json',
    ])
    def test_undefined_var(self, config):
        logfile_name = 'server.log'
        if os.path.isfile(logfile_name):
            os.remove(logfile_name)

        self.mock_server_process = run_mock_server(get_config_path(config), '--logfile', logfile_name)
        resp = httpx.get(SRV_8001 + '/undefined')
        assert 200 == resp.status_code
        assert resp.text == 'Hello {{undefined_var}} world'

        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            server_log = file.read()
            if 'j2' in config:
                assert "WARNING] Jinja2: Could not find variable `undefined_var`" in server_log
            else:
                assert "WARNING] Handlebars: Could not find variable 'undefined_var'" in server_log

        resp = httpx.get(SRV_8001 + '/undefined2')
        assert 200 == resp.status_code
        if 'j2' in config:
            assert resp.text == 'Hello {{undefined_helper(1, 2)}} world'
        else:
            assert resp.text == 'Hello {{undefined_helper 1 2}} world'

        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            server_log = file.read()
            if 'j2' in config:
                assert "WARNING] Jinja2: Could not find variable `undefined_helper`" in server_log
            else:
                assert "WARNING] Handlebars: Could not find property undefined_helper" in server_log

        resp = httpx.get(SRV_8001 + '/undefined3')
        assert 200 == resp.status_code
        if 'j2' in config:
            assert resp.text == 'Hello {{undefined_obj.attr(1, 2)}} world'
        else:
            assert resp.text == 'Hello {{undefined_obj.attr 1 2}} world'

        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            server_log = file.read()
            if 'j2' in config:
                assert "WARNING] Jinja2: Could not find variable `undefined_obj`" in server_log
            else:
                assert "WARNING] Handlebars: Could not find object attribute 'undefined_obj.attr'" in server_log

        resp = httpx.get(SRV_8001 + '/undefined4')
        assert 200 == resp.status_code
        if 'j2' in config:
            assert resp.text == '{{ date.date(\'%Y-%m-%d %H:%M %f\', false, 99999) }}'
        else:
            assert resp.text == '{{ date.date \'%Y-%m-%d %H:%M %f\' false 99999 }}'

        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            server_log = file.read()
            if 'j2' in config:
                assert "WARNING] Jinja2: date() takes from 1 to 3 positional arguments but 4 were given" in server_log
            else:
                assert "WARNING] Handlebars: date() takes from 2 to 4 positional arguments but 5 were given" in server_log

        resp = httpx.get(SRV_8001 + '/undefined5')
        assert 200 == resp.status_code
        assert resp.text == 'Hello {{date.undefined_attr}} world'

        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            server_log = file.read()
            if 'j2' in config:
                assert "WARNING] Jinja2: 'mockintosh.j2.methods.Date object' has no attribute 'undefined_attr'" in server_log
            else:
                assert "WARNING] Handlebars: Could not find object attribute 'date.undefined_attr'" in server_log

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/counter.yaml',
        'configs/yaml/j2/core/counter.yaml'
    ])
    def test_counter(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        for i in range(1, 6):
            resp = httpx.get(SRV_8001 + '/counter', headers={'Host': SRV_8001_HOST})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == 'Hello %d world' % i

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/random.yaml',
        'configs/yaml/j2/core/random.yaml'
    ])
    def test_random(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/int')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert str(int(resp.text)) == resp.text

        resp = httpx.get(SRV_8001 + '/float')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert re.match(r'^-?\d+(?:\.\d+)?$', resp.text)

        resp = httpx.get(SRV_8001 + '/alphanum')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert len(resp.text) == 7

        resp = httpx.get(SRV_8001 + '/hex')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert int(resp.text, 16)

        resp = httpx.get(SRV_8001 + '/uuid4')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert is_valid_uuid(resp.text)

        resp = httpx.get(SRV_8001 + '/ascii')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert len(resp.text) == 11
        assert is_ascii(resp.text)

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/subexpression.yaml',
        'configs/yaml/j2/core/subexpression.yaml'
    ])
    def test_subexpression(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/subexpression')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert re.match(r'^-?\d+(?:\.\d+)?$', resp.text)

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/date.json',
        'configs/json/j2/core/date.json',
        'configs/yaml/hbs/core/date.yaml',
        'configs/yaml/j2/core/date.yaml'
    ])
    def test_date(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/timestamp')
        utcnow = datetime.utcnow()
        now = time.time()

        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        resp_int = int(resp.text)
        diff = now - resp_int
        assert diff < 1

        resp = httpx.get(SRV_8001 + '/timestamp-shift')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        assert int(segments[0]) < int(segments[1])
        assert int(segments[0]) > int(segments[2])

        resp = httpx.get(SRV_8001 + '/ftimestamp')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        diff = now - float(segments[0])
        assert diff < 1
        assert len(segments[0].split('.')[1]) <= 3
        assert len(segments[1].split('.')[1]) <= 7

        resp = httpx.get(SRV_8001 + '/ftimestamp-shift')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        assert float(segments[0]) < float(segments[1])
        assert float(segments[0]) > float(segments[2])

        resp = httpx.get(SRV_8001 + '/date')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        pattern = '%Y-%m-%dT%H:%M:%S.%f'
        delta = utcnow - datetime.strptime(segments[0], pattern)
        assert delta.days < 2
        pattern = '%Y-%m-%d %H:%M'
        delta = utcnow - datetime.strptime(segments[1], pattern)
        assert delta.seconds / 60 < 2

        resp = httpx.get(SRV_8001 + '/date-shift')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        pattern = '%Y-%m-%d %H:%M %f'
        delta = utcnow - datetime.strptime(data['now'], pattern)
        assert delta < timedelta(days=2)
        delta = utcnow - datetime.strptime(data['1_week_back'], pattern)
        assert delta < timedelta(days=9)
        delta = datetime.strptime(data['1_week_forward'], pattern) - utcnow
        assert delta > timedelta(days=5)
        delta = utcnow - datetime.strptime(data['1_day_back'], pattern)
        assert delta < timedelta(days=3)
        delta = datetime.strptime(data['1_day_forward'], pattern) - utcnow
        assert delta > timedelta(seconds=82800)
        delta = utcnow - datetime.strptime(data['1_hour_back'], pattern)
        assert delta < timedelta(seconds=3700)
        delta = datetime.strptime(data['1_hour_forward'], pattern) - utcnow
        assert delta > timedelta(seconds=3500)
        delta = utcnow - datetime.strptime(data['1_minute_back'], pattern)
        assert delta < timedelta(seconds=120)

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/connection_reset.yaml'
    ])
    def test_connection_reset(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/normal')
        assert 200 == resp.status_code
        assert resp.text == 'Hello world'

        try:
            httpx.get(SRV_8001 + '/reset')
        except httpx.ReadError as e:
            assert str(e) == '[Errno 104] Connection reset by peer'

        try:
            httpx.get(SRV_8001 + '/close')
        except httpx.RemoteProtocolError as e:
            assert 'ConnectionClosed' in str(e)

        try:
            httpx.get(SRV_8001 + '/reset2')
        except httpx.ReadError as e:
            assert str(e) == '[Errno 104] Connection reset by peer'

        try:
            httpx.get(SRV_8001 + '/close2')
        except httpx.RemoteProtocolError as e:
            assert 'ConnectionClosed' in str(e)

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/faker.json',
        'configs/json/j2/core/faker.json'
    ])
    def test_faker(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/faker')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['bothify'], str) and len(data['bothify']) == 5
        assert isinstance(data['bothify_args'], str) and len(data['bothify_args']) == 5
        assert isinstance(data['hexify'], str) and len(data['hexify']) == 4
        assert isinstance(data['hexify_args'], str) and len(data['hexify_args']) == 30
        assert isinstance(data['language_code'], str) and 2 <= len(data['language_code']) <= 3
        assert isinstance(data['lexify'], str) and len(data['lexify']) == 4
        assert isinstance(data['lexify_args'], str) and len(data['lexify_args']) == 29
        assert isinstance(data['lexify'], str) and len(data['lexify']) == 4
        assert isinstance(data['locale'], str) and 5 <= len(data['locale']) <= 6
        assert isinstance(data['numerify'], str) and 0 <= int(data['numerify']) <= 999
        assert isinstance(data['random_choices'][0], str)
        assert 0 <= data['random_digit'] <= 9
        assert 1 <= data['random_digit_not_null'] <= 9
        assert isinstance(data['random_element'], str)
        assert isinstance(data['random_elements'][0], str)
        assert 0 <= data['random_int'] <= 9999
        assert 10000 <= data['random_int_args'] <= 50000
        assert isinstance(data['random_letter'], str)
        assert isinstance(data['random_letters'][0], str)
        assert isinstance(data['random_letters_args'][0], str)
        assert data['random_lowercase_letter'].lower() == data['random_lowercase_letter']
        assert isinstance(data['random_sample'][0], str)
        assert data['random_uppercase_letter'].upper() == data['random_uppercase_letter']

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/escape_html.yaml',
        'configs/yaml/j2/core/escape_html.yaml'
    ])
    def test_escape_html(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/endp1')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == '&amp; &lt; &quot; &gt;'

    def test_cors(self):
        config = 'tests_integrated/integration_config.yaml'
        config_path = os.path.abspath(os.path.join(os.path.join(__location__, '..'), config))
        self.mock_server_process = run_mock_server(config_path)

        hdr = {
            "origin": "http://someorigin",
            "Access-Control-Request-Headers": "authorization, x-api-key"
        }
        resp = httpx.options(SRV_8001 + '/cors-request', headers=hdr)
        assert 204 == resp.status_code
        assert hdr['origin'] == resp.headers.get("access-control-allow-origin")
        assert hdr['Access-Control-Request-Headers'] == resp.headers.get("Access-Control-Allow-Headers")
        assert "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT" == resp.headers.get("access-control-allow-methods")

        resp = httpx.post(SRV_8001 + '/cors-request', json={}, headers=hdr)
        assert hdr['origin'] == resp.headers.get("access-control-allow-origin")
        assert hdr['Access-Control-Request-Headers'] == resp.headers.get("Access-Control-Allow-Headers")
        assert "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT" == resp.headers.get("access-control-allow-methods")
        assert 201 == resp.status_code

        resp = httpx.options(SRV_8001 + '/cors-request-overridden', headers=hdr)
        assert 401 == resp.status_code

        resp = httpx.options(SRV_8001 + '/nonexistent', headers=hdr)
        assert 404 == resp.status_code

        resp = httpx.options(SRV_8001 + '/cors-request')
        assert 404 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/random.yaml'
    ])
    def test_404_image(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/404-img.png')
        assert 404 == resp.status_code
        assert b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A' == resp.content[:8]
        assert resp.headers['Content-Type'] == 'image/png'


@pytest.mark.parametrize(('config'), [
    'configs/json/hbs/status/status_code.json',
    'configs/json/j2/status/status_code.json',
    'configs/yaml/hbs/status/status_code.yaml',
    'configs/yaml/j2/status/status_code.yaml',
])
class TestStatus():

    def setup_method(self):
        config = self._item.callspec.getparam('config')
        self.mock_server_process = run_mock_server(get_config_path(config))

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_status_code(self, config):
        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 202 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 403 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

    def test_status_code_templated(self, config):
        query = '?rc=303'
        resp = httpx.get(SRV_8002 + '/service2-endpoint2' + query, headers={'Host': SRV_8002_HOST})
        assert 303 == resp.status_code

        query = '?rc=wrong'
        resp = httpx.get(SRV_8002 + '/service2-endpoint2' + query, headers={'Host': SRV_8002_HOST})
        assert 500 == resp.status_code
        assert 'Status code is neither an integer nor in \'RST\', \'FIN\'!' == resp.text


@pytest.mark.parametrize(('config'), [
    'configs/json/hbs/headers/config.json',
    'configs/json/j2/headers/config.json',
    'configs/yaml/hbs/headers/config.yaml',
    'configs/yaml/j2/headers/config.yaml'
])
class TestHeaders():

    def setup_method(self):
        config = self._item.callspec.getparam('config')
        self.mock_server_process = run_mock_server(get_config_path(config))

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_parameter(self, config):
        param = str(int(time.time()))
        resp = httpx.get(SRV_8001 + '/parameter', headers={"hdr1": param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with parameter: %s' % param

        resp = httpx.get(SRV_8001 + '/parameter/template-file', headers={"hdr1": param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with parameter'] == param

    def test_static_value(self, config):
        static_val = 'myValue'
        resp = httpx.get(SRV_8001 + '/static-value', headers={"hdr1": static_val})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with static value: %s' % static_val

        resp = httpx.get(SRV_8001 + '/static-value/template-file', headers={"hdr1": static_val})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with static value'] == static_val

    def test_regex_capture_group(self, config):
        param = str(int(time.time()))
        resp = httpx.get(SRV_8001 + '/regex-capture-group', headers={"hdr1": 'prefix-%s-suffix' % param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with regex capture group: %s' % param

        resp = httpx.get(SRV_8001 + '/regex-capture-group/template-file', headers={"hdr1": 'prefix-%s-suffix' % param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with regex capture group'] == param

    def test_missing_header_should_400(self, config):
        static_val = 'myValue'
        resp = httpx.get(SRV_8001 + '/static-value', headers={"hdrX": static_val})
        assert 400 == resp.status_code
        assert '\'Hdr1\' not in the request headers!' == resp.text

        resp = httpx.get(SRV_8001 + '/static-value/template-file', headers={"hdrX": static_val})
        assert 400 == resp.status_code
        assert '\'Hdr1\' not in the request headers!' == resp.text

    def test_wrong_static_value_should_400(self, config):
        static_val = 'wrongValue'
        resp = httpx.get(SRV_8001 + '/static-value', headers={"hdr1": static_val})
        assert 400 == resp.status_code
        assert ('Request header value \'%s\' on key \'Hdr1\' does not match to regex: ^myValue$') % static_val == resp.text

        resp = httpx.get(SRV_8001 + '/static-value/template-file', headers={"hdr1": static_val})
        assert 400 == resp.status_code
        assert ('Request header value \'%s\' on key \'Hdr1\' does not match to regex: ^myValue$') % static_val == resp.text

    def test_wrong_regex_pattern_should_400(self, config):
        param = str(int(time.time()))
        resp = httpx.get(SRV_8001 + '/regex-capture-group', headers={"hdr1": 'idefix-%s-suffix' % param})
        assert 400 == resp.status_code
        assert ('Request header value \'idefix-%s-suffix\' on key \'Hdr1\' does not match to regex: ^prefix-(.+)-suffix$' % param) == resp.text

        resp = httpx.get(SRV_8001 + '/regex-capture-group/template-file', headers={"hdr1": 'idefix-%s-suffix' % param})
        assert 400 == resp.status_code
        assert ('Request header value \'idefix-%s-suffix\' on key \'Hdr1\' does not match to regex: ^prefix-(.+)-suffix$' % param) == resp.text

    def test_first_alternative(self, config):
        static_val = 'myValue'
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        resp = httpx.get(SRV_8001 + '/alternative', headers={
            "hdr1": static_val,
            "hdr2": param2,
            "hdr3": 'prefix-%s-suffix' % param3
        })
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'headers match: %s %s %s' % (static_val, param2, param3)

        resp = httpx.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr1": static_val,
            "hdr2": param2,
            "hdr3": 'prefix-%s-suffix' % param3
        })
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['request.headers.hdr1'] == static_val
        assert data['anyValIntoVar'] == param2
        assert data['capturedVar'] == param3

    def test_second_alternative(self, config):
        static_val = 'another header'
        resp = httpx.get(SRV_8001 + '/alternative', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'hdr4 request header: %s' % static_val

        resp = httpx.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['hdr4 request header'] == static_val

    def test_nonexisting_alternative_should_400(self, config):
        static_val = 'another header'
        resp = httpx.get(SRV_8001 + '/alternative', headers={
            "hdr5": static_val
        })
        assert 400 == resp.status_code
        assert '\'Hdr4\' not in the request headers!' == resp.text

        resp = httpx.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr5": static_val
        })
        assert 400 == resp.status_code
        assert '\'Hdr4\' not in the request headers!' == resp.text

    def test_response_headers_in_first_alternative(self, config):
        static_val = 'myValue'
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        resp = httpx.get(SRV_8001 + '/alternative', headers={
            "hdr1": static_val,
            "hdr2": param2,
            "hdr3": 'prefix-%s-suffix' % param3
        })
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.cookies['name1'] == param2
        assert resp.cookies['name2'] == 'prefix-%s-suffix' % param3

        resp = httpx.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr1": static_val,
            "hdr2": param2,
            "hdr3": 'prefix-%s-suffix' % param3
        })
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.cookies['name1'] == param2
        assert resp.cookies['name2'] == 'prefix-%s-suffix' % param3

    def test_response_headers_in_second_alternative(self, config):
        static_val = 'another header'
        resp = httpx.get(SRV_8001 + '/alternative', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['Hdr4'] == 'hdr4 request header: %s' % static_val

        resp = httpx.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.headers['Hdr4'] == 'hdr4 request header: %s' % static_val

    def test_global_headers(self, config):
        resp = httpx.get(SRV_8001 + '/global-headers')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['global-hdr1'] == 'globalval1'
        assert resp.headers['global-hdr2'] == 'globalval2'

        resp = httpx.get(SRV_8001 + '/global-headers-modified')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['global-hdr1'] == 'overridden'
        assert resp.headers['global-hdr2'] == 'globalval2'


@pytest.mark.parametrize(('config'), [
    'configs/json/hbs/path/config.json',
    'configs/json/j2/path/config.json',
    'configs/yaml/hbs/path/config.yaml',
    'configs/yaml/j2/path/config.yaml'
])
class TestPath():

    def setup_method(self):
        config = self._item.callspec.getparam('config')
        self.mock_server_process = run_mock_server(get_config_path(config))

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_parameter(self, config):
        param = str(int(time.time()))
        resp = httpx.get(SRV_8001 + '/parameterized1/text/%s/subval' % param)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'intoVar capture: %s' % param

        resp = httpx.get(SRV_8001 + '/parameterized1/template-file/%s/subval' % param)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['var'] == param

    def test_static_value_priority(self, config):
        resp = httpx.get(SRV_8001 + '/parameterized1/text/staticVal/subval')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'static path components have priority'

    def test_regex_match(self, config):
        path = '/parameterized2/text/prefix-%s/subval' % str(int(time.time()))
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'regex match: %s' % path

        path = '/parameterized2/template-file/prefix-%s/subval' % str(int(time.time()))
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['request']['path'] == path

        path = '/parameterized2/text/wrongprefix-%s/subval' % str(int(time.time()))
        resp = httpx.get(SRV_8001 + path)
        assert 404 == resp.status_code

    def test_regex_capture_group(self, config):
        param = str(int(time.time()))
        path = '/parameterized1/text/prefix2-%s/subval2' % param
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'regex capture group: %s' % param

        path = '/parameterized1/template-file/prefix2-%s/subval2' % param
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['capture'] == param

    def test_multiple_parameters(self, config):
        param1 = str(int(time.time()))
        param2 = str(int(time.time()))
        param3 = str(int(time.time()))
        resp = httpx.get(SRV_8001 + '/parameterized3/text/%s/%s/%s' % (param1, param2, param3))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'var1: %s, var2: %s, var3: %s' % (param1, param2, param3)

        resp = httpx.get(SRV_8001 + '/parameterized3/template-file/%s/%s/%s' % (param1, param2, param3))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['var1'] == param1
        assert data['var2'] == param2
        assert data['var3'] == param3

    def test_multiple_regex_capture_groups(self, config):
        param1 = str(int(time.time()))
        param2 = str(int(time.time()))
        param3 = str(int(time.time()))
        param4 = str(int(time.time()))
        param5 = str(int(time.time()))
        path = '/parameterized4/text/prefix-%s-%s-%s-suffix/%s_%s' % (param1, param2, param3, param4, param5)
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'var1: %s, var2: %s, var3: %s, var4: %s, var5: %s' % (
            param1,
            param2,
            param3,
            param4,
            param5
        )

        path = '/parameterized4/template-file/prefix-%s-%s-%s-suffix/%s_%s' % (param1, param2, param3, param4, param5)
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['var1'] == param1
        assert data['var2'] == param2
        assert data['var3'] == param3
        assert data['var4'] == param4
        assert data['var5'] == param5

    def test_multiple_parameters_and_regex_capture_groups(self, config):
        param1 = str(int(time.time()))
        param2 = str(int(time.time()))
        param3 = str(int(time.time()))
        param4 = str(int(time.time()))
        param5 = str(int(time.time()))
        path = '/parameterized5/text/%s/prefix-%s-%s-suffix/%s/prefix2-%s' % (param1, param2, param3, param4, param5)
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'var1: %s, var2: %s, var3: %s, var4: %s, var5: %s' % (
            param1,
            param2,
            param3,
            param4,
            param5
        )

        path = '/parameterized5/template-file/%s/prefix-%s-%s-suffix/%s/prefix2-%s' % (
            param1,
            param2,
            param3,
            param4,
            param5
        )
        resp = httpx.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['var1'] == param1
        assert data['var2'] == param2
        assert data['var3'] == param3
        assert data['var4'] == param4
        assert data['var5'] == param5

    def test_path_segment_capture_conflict(self, config):
        param1 = str(int(time.time()))
        param2 = str(int(time.time()))
        resp = httpx.delete(SRV_8001 + '/carts/%s' % param1)
        assert 202 == resp.status_code

        resp = httpx.post(SRV_8001 + '/carts/%s/items' % param1)
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json'
        data = resp.json()
        assert data['id'] == 'L8VEqJRB4R'

        resp = httpx.get(SRV_8001 + '/carts/%s/merge' % param1)
        assert 202 == resp.status_code

        resp = httpx.get(SRV_8001 + '/carts/%s/items' % param1)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json'
        data = resp.json()
        assert isinstance(data, list) and not data

        resp = httpx.patch(SRV_8001 + '/carts/%s/items' % param1)
        assert 202 == resp.status_code

        resp = httpx.delete(SRV_8001 + '/carts/%s/items/%s' % (param1, param2))
        assert 202 == resp.status_code

    def test_auto_regex(self, config):
        hello = 'hello'
        world = 'world'
        x = 'x'
        y = 'y'

        resp = httpx.get(SRV_8001 + '/%s-%s/another' % (hello, world))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s' % world

        resp = httpx.get(SRV_8001 + '/%s-middle-%s/another' % (x, y))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s %s' % (x, y)

        resp = httpx.get(SRV_8001 + '/%s-middle2-7/another' % x)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s' % x

        resp = httpx.get(SRV_8001 + '/%s2-prefix-%s/another' % (hello, world))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s' % world

    def test_auto_query_string(self, config):
        hello = 'hello'
        world = 'world'
        goodbye = 'goodbye'

        resp = httpx.get(SRV_8001 + '/search?q=%s' % hello)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s' % hello

        resp = httpx.get(SRV_8001 + '/search2?q=%s&s=%s' % (hello, world))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s %s' % (hello, world)

        resp = httpx.get(SRV_8001 + '/abc1-xx%sxx' % hello)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s' % hello

        resp = httpx.get(SRV_8001 + '/abc2-xx%sxx?q=%s&s=%s' % (hello, world, goodbye))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s %s %s' % (hello, world, goodbye)

        resp = httpx.get(SRV_8001 + '/abc3-xx%sxx?q=abc4-xx%sxx&s=%s' % (hello, world, goodbye))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s %s %s' % (hello, world, goodbye)

        resp = httpx.get(SRV_8001 + '/abc5-xx%sxx?q=%s&s=%s#some-string' % (hello, world, goodbye))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'result: %s %s %s' % (hello, world, goodbye)

    def test_array_parameter_and_key_templating(self, config):
        v1 = 'v1'
        v2 = 'v2'
        somedata = 'somedata'

        resp = httpx.get(SRV_8001 + '/qstr-multiparam1?param[]=%s&param[]=%s' % (v1, v2))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == '%s %s' % (v1, v2)

        resp = httpx.get(SRV_8001 + '/qstr-multiparam2?param[]=%s' % v1)
        assert 400 == resp.status_code

        resp = httpx.get(SRV_8001 + '/qstr-multiparam2?param1=%s&param2=%s' % (v1, v2))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == '%s %s' % (v1, v2)

        resp = httpx.get(SRV_8001 + '/qstr-multiparam3?prefix-%s-suffix' % somedata)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == '%s' % somedata


@pytest.mark.parametrize(('config'), [
    'configs/json/hbs/query_string/config.json',
    'configs/json/j2/query_string/config.json',
    'configs/yaml/hbs/query_string/config.yaml',
    'configs/yaml/j2/query_string/config.yaml'
])
class TestQueryString():

    def setup_method(self):
        config = self._item.callspec.getparam('config')
        self.mock_server_process = run_mock_server(get_config_path(config))

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_parameter(self, config):
        param = str(int(time.time()))
        query = '?param1=%s' % param
        resp = httpx.get(SRV_8001 + '/parameter' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with parameter: %s' % param

        resp = httpx.get(SRV_8001 + '/parameter/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with parameter'] == param

    def test_static_value(self, config):
        static_val = 'my Value'
        query = '?param1=%s' % static_val
        resp = httpx.get(SRV_8001 + '/static-value' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with static value: %s' % static_val

        resp = httpx.get(SRV_8001 + '/static-value/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with static value'] == static_val

    def test_regex_capture_group(self, config):
        param = str(int(time.time()))
        query = '?param1=prefix-%s-suffix' % param
        resp = httpx.get(SRV_8001 + '/regex-capture-group' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with regex capture group: %s' % param

        resp = httpx.get(SRV_8001 + '/regex-capture-group/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with regex capture group'] == param

    def test_missing_query_param_should_400(self, config):
        static_val = 'myValue'
        query = '?paramX=%s' % static_val
        resp = httpx.get(SRV_8001 + '/static-value' + query)
        assert 400 == resp.status_code
        assert 'Key \'param1\' couldn\'t found in the query string!' == resp.text

        resp = httpx.get(SRV_8001 + '/static-value/template-file' + query)
        assert 400 == resp.status_code
        assert 'Key \'param1\' couldn\'t found in the query string!' == resp.text

    def test_wrong_static_value_should_400(self, config):
        static_val = 'wrong Value'
        query = '?param1=%s' % static_val
        resp = httpx.get(SRV_8001 + '/static-value' + query)
        assert 400 == resp.status_code
        assert ('Request query parameter value \'%s\' on key \'param1\' does not match to regex: ^my Value$' % static_val) == resp.text

        resp = httpx.get(SRV_8001 + '/static-value/template-file' + query)
        assert 400 == resp.status_code
        assert ('Request query parameter value \'%s\' on key \'param1\' does not match to regex: ^my Value$' % static_val) == resp.text

    def test_wrong_regex_pattern_should_400(self, config):
        param = str(int(time.time()))
        query = '?param1=idefix-%s-suffix' % param
        resp = httpx.get(SRV_8001 + '/regex-capture-group' + query)
        assert 400 == resp.status_code
        assert ('Request query parameter value \'idefix-%s-suffix\' on key \'param1\' does not match to regex: ^prefix-(.+)-suffix$' % param) == resp.text

        resp = httpx.get(SRV_8001 + '/regex-capture-group/template-file' + query)
        assert 400 == resp.status_code
        assert ('Request query parameter value \'idefix-%s-suffix\' on key \'param1\' does not match to regex: ^prefix-(.+)-suffix$' % param) == resp.text

    def test_first_alternative(self, config):
        static_val = 'my Value'
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        query = '?param1=%s&param2=%s&param3=prefix-%s-suffix' % (static_val, param2, param3)
        resp = httpx.get(SRV_8001 + '/alternative' + query)
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'query string match: %s %s %s' % (static_val, param2, param3)

        resp = httpx.get(SRV_8001 + '/alternative/template-file' + query)
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['request.queryString.param1'] == static_val
        assert data['anyValIntoVar'] == param2
        assert data['capturedVar'] == param3

    def test_second_alternative(self, config):
        static_val = 'another query string'
        query = '?param4=%s' % static_val
        resp = httpx.get(SRV_8001 + '/alternative' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'param4 request query string: %s' % static_val

        resp = httpx.get(SRV_8001 + '/alternative/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['param4 request query string'] == static_val

    def test_nonexisting_alternative_should_400(self, config):
        static_val = 'another query string'
        query = '?param5=%s' % static_val
        resp = httpx.get(SRV_8001 + '/alternative' + query)
        assert 400 == resp.status_code
        assert 'Key \'param4\' couldn\'t found in the query string!' == resp.text

        resp = httpx.get(SRV_8001 + '/alternative/template-file' + query)
        assert 400 == resp.status_code
        assert 'Key \'param4\' couldn\'t found in the query string!' == resp.text


@pytest.mark.parametrize(('config'), [
    'configs/json/hbs/body/config.json',
    'configs/json/j2/body/config.json',
    'configs/yaml/hbs/body/config.yaml',
    'configs/yaml/j2/body/config.yaml'
])
class TestBody():

    def setup_method(self):
        config = self._item.callspec.getparam('config')
        self.mock_server_process = run_mock_server(get_config_path(config))

    def teardown_method(self):
        self.mock_server_process.terminate()

    def test_jsonpath_templating(self, config):
        resp = httpx.post(SRV_8001 + '/body-jsonpath-tpl', json={"key": "val", "key2": 123})
        assert 200 == resp.status_code
        assert 'body jsonpath matched: val 123' == resp.text

        resp = httpx.post(SRV_8001 + '/body-jsonpath-tpl', json={"key": None})
        assert 200 == resp.status_code
        assert 'body jsonpath matched: null ' == resp.text

        resp = httpx.post(SRV_8001 + '/body-jsonpath-tpl', data="not json")
        assert 200 == resp.status_code
        if 'j2' in config:
            assert "body jsonpath matched: {{jsonPath(request.json, '$.key')}} {{jsonPath(request.json, '$.key2')}}" == resp.text
        else:
            assert "body jsonpath matched: {{jsonPath request.json '$.key'}} {{jsonPath request.json '$.key2'}}" == resp.text

    def test_body_json_schema(self, config):
        paths = ['/body-json-schema', '/body-json-schema-file']
        for path in paths:
            resp = httpx.post(SRV_8001 + path, json={"somekey": "valid"})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == 'body json schema matched'

            resp = httpx.post(SRV_8001 + path, json={"somekey2": "invalid"})
            assert 400 == resp.status_code

            data = 'hello world'
            resp = httpx.post(SRV_8001 + path, data=data)
            assert 400 == resp.status_code
            assert resp.text == 'JSON decode error of the request body:\n\n%s' % data

        resp = httpx.post(SRV_8001 + '/body-json-schema-file-error', json={"somekey": "valid"})
        assert 500 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'JSON decode error of the JSON schema file: @body_schema_error.json'

    def test_body_regex(self, config):
        resp = httpx.post(SRV_8001 + '/body-regex', data="somewhere 1-required-2 is present")
        assert 200 == resp.status_code
        assert "body regex matched: 1 2" == resp.text

        resp = httpx.post(SRV_8001 + '/body-regex', data="somewhere a-required-b is not present")
        assert 400 == resp.status_code

    def test_body_urlencoded(self, config):
        data = {'key1': 'constant', 'key2': 'val1', 'key3': 'prefix-val2-val3-suffix'}
        resp = httpx.post(SRV_8001 + '/body-urlencoded', data=data)
        assert 200 == resp.status_code
        assert "body urlencoded matched: constant val1 val2 val3" == resp.text

        data_wrong = {'key1': 'val1', 'key2': 'prefix-val2-val3-idefix'}
        resp = httpx.post(SRV_8001 + '/body-urlencoded', data=data_wrong)
        assert 400 == resp.status_code

        data_wrong = {'key2': 'val1', 'key3': 'prefix-val2-val3-idefix'}
        resp = httpx.post(SRV_8001 + '/body-urlencoded', data=data_wrong)
        assert 400 == resp.status_code

    def test_body_multipart(self, config):
        files = {'key1': 'constant', 'key2': 'val1', 'key3': 'prefix-val2-val3-suffix'}
        resp = httpx.post(SRV_8001 + '/body-multipart', files=files)
        assert 200 == resp.status_code
        assert "body multipart matched: constant val1 val2 val3" == resp.text

        files_wrong = {'key1': 'val1', 'key2': 'prefix-val2-val3-idefix'}
        resp = httpx.post(SRV_8001 + '/body-multipart', files=files_wrong)
        assert 400 == resp.status_code

        files_wrong = {'key2': 'val1', 'key3': 'prefix-val2-val3-idefix'}
        resp = httpx.post(SRV_8001 + '/body-multipart', files=files_wrong)
        assert 400 == resp.status_code

    def test_body_text(self, config):
        data = 'hello world'
        resp = httpx.post(SRV_8001 + '/body-text', data=data)
        assert 200 == resp.status_code
        assert "body text matched: %s" % data == resp.text


class TestManagement():

    def setup_method(self):
        self.mock_server_process = None

    def teardown_method(self):
        if self.mock_server_process is not None:
            self.mock_server_process.terminate()

    @pytest.mark.parametrize(('config', 'suffix'), [
        ('configs/json/hbs/management/config.json', '/'),
        ('configs/yaml/hbs/management/config.yaml', '/'),
        ('configs/json/hbs/management/config.json', ''),
        ('configs/yaml/hbs/management/config.yaml', '')
    ])
    def test_get_root(self, config, suffix):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + suffix, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'

        resp = httpx.get(SRV_8001 + '/__admin' + suffix, headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_config(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + '/config', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_config.json'), 'r').read()[:-1]

        resp = httpx.get(MGMT + '/config?format=yaml', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        assert resp.text == open(get_config_path('configs/stats_config.yaml'), 'r').read()

        resp = httpx.get(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_config_service1.json'), 'r').read()[:-1]

        resp = httpx.get(SRV_8001 + '/__admin/config?format=yaml', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        assert resp.text == open(get_config_path('configs/stats_config_service1.yaml'), 'r').read()

        resp = httpx.get(SRV_8002 + '/__admin/config', headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_config_service2.json'), 'r').read()[:-1]

        resp = httpx.get(SRV_8002 + '/__admin/config?format=yaml', headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        assert resp.text == open(get_config_path('configs/stats_config_service2.yaml'), 'r').read()

    @pytest.mark.parametrize(('config', '_format'), [
        ('configs/json/hbs/management/config.json', 'json'),
        ('configs/yaml/hbs/management/config.yaml', 'json'),
        ('configs/json/hbs/management/config.json', 'yaml'),
        ('configs/yaml/hbs/management/config.yaml', 'yaml')
    ])
    def test_post_config(self, config, _format):
        self.mock_server_process = run_mock_server(get_config_path(config))

        with open(get_config_path('configs/json/hbs/management/new_config.%s' % _format), 'r') as file:
            resp = httpx.post(MGMT + '/config', data=file.read(), verify=False)
            assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8001 + '/service1-new-config', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-config'

        resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

        resp = httpx.get(MGMT + '/config', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        with open(get_config_path('configs/json/hbs/management/new_config.json'), 'r') as file:
            data = json.load(file)
            assert data == resp.json()

        resp = httpx.get(MGMT + '/config?format=yaml', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        with open(get_config_path('configs/json/hbs/management/new_config.yaml'), 'r') as file:
            data = yaml.safe_load(file.read())
            assert data == yaml.safe_load(resp.text)

        with open(get_config_path('configs/json/hbs/management/new_service1.%s' % _format), 'r') as file:
            resp = httpx.post(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, data=file.read(), verify=False)
            assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8001 + '/service1-new-service', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-service'

        resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

        with open(get_config_path('configs/json/hbs/management/new_service2.%s' % _format), 'r') as file:
            resp = httpx.post(SRV_8002 + '/__admin/config', headers={'Host': SRV_8002_HOST}, data=file.read(), verify=False)
            assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8001 + '/service1-new-service', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-service'

        param = str(int(time.time()))
        resp = httpx.get(SRV_8002 + '/changed-endpoint/%s' % param, headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'var: %s' % param

        # Bad httpx
        resp = httpx.post(MGMT + '/config', data='hello: world:', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text.startswith('JSON/YAML decode error')

        resp = httpx.post(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, data='hello: world:', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text.startswith('JSON/YAML decode error')

        with open(get_config_path('configs/json/hbs/management/new_config.%s' % _format), 'r') as file:
            data = yaml.safe_load(file.read())
            data['incorrectKey'] = ''
            resp = httpx.post(MGMT + '/config', data=json.dumps(data), verify=False)
            assert 400 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text.startswith('JSON schema validation error:')

        with open(get_config_path('configs/json/hbs/management/new_service1.%s' % _format), 'r') as file:
            data = yaml.safe_load(file.read())
            data['incorrectKey'] = ''
            resp = httpx.post(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, data=json.dumps(data), verify=False)
            assert 400 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text.startswith('JSON schema validation error:')

        # Restricted field
        with open(get_config_path('configs/json/hbs/management/new_config.%s' % _format), 'r') as file:
            data = yaml.safe_load(file.read())
            data['services'][0]['port'] = 42
            resp = httpx.post(MGMT + '/config', data=json.dumps(data), verify=False)
            assert 500 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == "'port' field is restricted!"

        with open(get_config_path('configs/json/hbs/management/new_service1.%s' % _format), 'r') as file:
            data = yaml.safe_load(file.read())
            data['port'] = 42
            resp = httpx.post(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, data=json.dumps(data), verify=False)
            assert 500 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == "'port' field is restricted!"

    @pytest.mark.parametrize(('config', '_format'), [
        ('configs/json/hbs/management/config.json', 'json'),
        ('configs/yaml/hbs/management/config.yaml', 'json'),
        ('configs/json/hbs/management/config.json', 'yaml'),
        ('configs/yaml/hbs/management/config.yaml', 'yaml')
    ])
    def test_post_config_only_service_level(self, config, _format):
        self.mock_server_process = run_mock_server(get_config_path(config))

        with open(get_config_path('configs/json/hbs/management/new_service1.%s' % _format), 'r') as file:
            resp = httpx.post(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, data=file.read(), verify=False)
            assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8001 + '/service1-new-service', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-service'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_stats(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        param = str(int(time.time()))

        for _ in range(2):
            resp = httpx.get(MGMT + '/stats', verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()
            assert data['global']['request_counter'] == 0
            assert data['global']['avg_resp_time'] == 0
            assert data['global']['status_code_distribution'] == {}
            assert data['services'][0]['hint'] == 'service1.example.com:8001 - Mock for Service1'
            assert data['services'][0]['request_counter'] == 0
            assert data['services'][0]['avg_resp_time'] == 0
            assert data['services'][0]['status_code_distribution'] == {}
            assert data['services'][0]['endpoints'][0]['hint'] == 'GET /service1'
            assert data['services'][0]['endpoints'][0]['request_counter'] == 0
            assert data['services'][0]['endpoints'][0]['avg_resp_time'] == 0
            assert data['services'][0]['endpoints'][0]['status_code_distribution'] == {}
            assert data['services'][0]['endpoints'][1]['hint'] == 'GET /service1-second/{{var}}'
            assert data['services'][0]['endpoints'][1]['request_counter'] == 0
            assert data['services'][0]['endpoints'][1]['avg_resp_time'] == 0
            assert data['services'][0]['endpoints'][1]['status_code_distribution'] == {}
            assert data['services'][1]['hint'] == 'service2.example.com:8002 - Mock for Service2'
            assert data['services'][1]['request_counter'] == 0
            assert data['services'][1]['avg_resp_time'] == 0
            assert data['services'][1]['status_code_distribution'] == {}
            assert data['services'][1]['endpoints'][0]['hint'] == 'GET /service2'
            assert data['services'][1]['endpoints'][0]['request_counter'] == 0
            assert data['services'][1]['endpoints'][0]['avg_resp_time'] == 0
            assert data['services'][1]['endpoints'][0]['status_code_distribution'] == {}
            assert data['services'][1]['endpoints'][1]['hint'] == 'GET /service2-rst'
            assert data['services'][1]['endpoints'][1]['request_counter'] == 0
            assert data['services'][1]['endpoints'][1]['avg_resp_time'] == 0
            assert data['services'][1]['endpoints'][1]['status_code_distribution'] == {}
            assert data['services'][1]['endpoints'][2]['hint'] == 'GET /service2-fin'
            assert data['services'][1]['endpoints'][2]['request_counter'] == 0
            assert data['services'][1]['endpoints'][2]['avg_resp_time'] == 0
            assert data['services'][1]['endpoints'][2]['status_code_distribution'] == {}

            for _ in range(5):
                resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
                assert 200 == resp.status_code

            for _ in range(3):
                resp = httpx.get(SRV_8001 + '/service1-second/%s' % param, headers={'Host': SRV_8001_HOST}, verify=False)
                assert 201 == resp.status_code
                assert resp.text == 'service1-second: %s' % param

            for _ in range(2):
                resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST}, verify=False)
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = httpx.get(SRV_8002 + '/service2-rst', headers={'Host': SRV_8002_HOST}, verify=False)
                except httpx.ReadError as e:
                    assert str(e) == '[Errno 104] Connection reset by peer'
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = httpx.get(SRV_8002 + '/service2-fin', headers={'Host': SRV_8002_HOST}, verify=False)
                except httpx.RemoteProtocolError as e:
                    assert 'ConnectionClosed' in str(e)
                assert 200 == resp.status_code

            resp = httpx.get(MGMT + '/stats', verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()

            # `request_counter` assertions
            assert data['global']['request_counter'] == 14
            assert data['services'][0]['request_counter'] == 8
            assert data['services'][0]['endpoints'][0]['request_counter'] == 5
            assert data['services'][0]['endpoints'][1]['request_counter'] == 3
            assert data['services'][1]['request_counter'] == 6
            assert data['services'][1]['endpoints'][0]['request_counter'] == 2
            assert data['services'][1]['endpoints'][1]['request_counter'] == 2
            assert data['services'][1]['endpoints'][2]['request_counter'] == 2

            # `status_code_distribution` assertions
            assert data['global']['status_code_distribution']['200'] == 7
            assert data['global']['status_code_distribution']['201'] == 3
            assert data['global']['status_code_distribution']['RST'] == 2
            assert data['global']['status_code_distribution']['FIN'] == 2
            assert data['services'][0]['status_code_distribution']['200'] == 5
            assert data['services'][0]['status_code_distribution']['201'] == 3
            assert data['services'][0]['endpoints'][0]['status_code_distribution']['200'] == 5
            assert data['services'][0]['endpoints'][1]['status_code_distribution']['201'] == 3
            assert data['services'][1]['status_code_distribution']['200'] == 2
            assert data['services'][1]['status_code_distribution']['RST'] == 2
            assert data['services'][1]['status_code_distribution']['FIN'] == 2

            resp = httpx.delete(MGMT + '/stats', verify=False)
            assert 204 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_stats_service(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        param = str(int(time.time()))

        for _ in range(2):
            resp = httpx.get(SRV_8001 + '/__admin/stats', headers={'Host': SRV_8001_HOST}, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()
            assert data['request_counter'] == 0
            assert data['avg_resp_time'] == 0
            assert data['status_code_distribution'] == {}
            assert data['endpoints'][0]['hint'] == 'GET /service1'
            assert data['endpoints'][0]['request_counter'] == 0
            assert data['endpoints'][0]['avg_resp_time'] == 0
            assert data['endpoints'][0]['status_code_distribution'] == {}
            assert data['endpoints'][1]['hint'] == 'GET /service1-second/{{var}}'
            assert data['endpoints'][1]['request_counter'] == 0
            assert data['endpoints'][1]['avg_resp_time'] == 0
            assert data['endpoints'][1]['status_code_distribution'] == {}

            for _ in range(5):
                resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
                assert 200 == resp.status_code

            for _ in range(3):
                resp = httpx.get(SRV_8001 + '/service1-second/%s' % param, headers={'Host': SRV_8001_HOST}, verify=False)
                assert 201 == resp.status_code
                assert resp.text == 'service1-second: %s' % param

            resp = httpx.get(SRV_8001 + '/__admin/stats', headers={'Host': SRV_8001_HOST}, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()

            # `request_counter` assertions
            assert data['request_counter'] == 8
            assert data['endpoints'][0]['request_counter'] == 5
            assert data['endpoints'][1]['request_counter'] == 3

            # `status_code_distribution` assertions
            assert data['status_code_distribution']['200'] == 5
            assert data['status_code_distribution']['201'] == 3
            assert data['endpoints'][0]['status_code_distribution']['200'] == 5
            assert data['endpoints'][1]['status_code_distribution']['201'] == 3

            resp = httpx.delete(SRV_8001 + '/__admin/stats', headers={'Host': SRV_8001_HOST}, verify=False)
            assert 204 == resp.status_code

        for _ in range(2):
            resp = httpx.get(SRV_8002 + '/__admin/stats', headers={'Host': SRV_8002_HOST}, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()
            assert data['request_counter'] == 0
            assert data['avg_resp_time'] == 0
            assert data['status_code_distribution'] == {}
            assert data['endpoints'][0]['hint'] == 'GET /service2'
            assert data['endpoints'][0]['request_counter'] == 0
            assert data['endpoints'][0]['avg_resp_time'] == 0
            assert data['endpoints'][0]['status_code_distribution'] == {}
            assert data['endpoints'][1]['hint'] == 'GET /service2-rst'
            assert data['endpoints'][1]['request_counter'] == 0
            assert data['endpoints'][1]['avg_resp_time'] == 0
            assert data['endpoints'][1]['status_code_distribution'] == {}
            assert data['endpoints'][2]['hint'] == 'GET /service2-fin'
            assert data['endpoints'][2]['request_counter'] == 0
            assert data['endpoints'][2]['avg_resp_time'] == 0
            assert data['endpoints'][2]['status_code_distribution'] == {}

            for _ in range(2):
                resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST}, verify=False)
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = httpx.get(SRV_8002 + '/service2-rst', headers={'Host': SRV_8002_HOST}, verify=False)
                except httpx.ReadError as e:
                    assert str(e) == '[Errno 104] Connection reset by peer'
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = httpx.get(SRV_8002 + '/service2-fin', headers={'Host': SRV_8002_HOST}, verify=False)
                except httpx.RemoteProtocolError as e:
                    assert 'ConnectionClosed' in str(e)
                assert 200 == resp.status_code

            resp = httpx.get(SRV_8002 + '/__admin/stats', headers={'Host': SRV_8002_HOST}, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()

            # `request_counter` assertions
            assert data['request_counter'] == 6
            assert data['endpoints'][0]['request_counter'] == 2
            assert data['endpoints'][1]['request_counter'] == 2
            assert data['endpoints'][2]['request_counter'] == 2

            # `status_code_distribution` assertions
            assert data['status_code_distribution']['200'] == 2
            assert data['status_code_distribution']['RST'] == 2
            assert data['status_code_distribution']['FIN'] == 2

            resp = httpx.delete(SRV_8002 + '/__admin/stats', headers={'Host': SRV_8002_HOST}, verify=False)
            assert 204 == resp.status_code

    @pytest.mark.parametrize(('config, level'), [
        ('configs/json/hbs/management/multiresponse.json', 'global'),
        ('configs/json/hbs/management/multiresponse.json', 'service'),
    ])
    def test_post_reset_iterators(self, config, level):
        self.mock_server_process = run_mock_server(get_config_path(config))

        for _ in range(3):
            for i in range(2):
                resp = httpx.get(SRV_8001 + '/service1-multi-response-looped', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = httpx.get(SRV_8001 + '/service1-multi-response-looped-empty-list', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert not resp.text

                resp = httpx.get(SRV_8001 + '/service1-no-response', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert not resp.text

                resp = httpx.get(SRV_8001 + '/service1-multi-response-nonlooped', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = httpx.get(SRV_8001 + '/service1-dataset-inline', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'dset: val%d' % (i + 1)

                resp = httpx.get(SRV_8001 + '/service1-dataset-inline-nonlooped', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'dset: val%d' % (i + 1)

                resp = httpx.get(SRV_8001 + '/service1-dataset-fromfile', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'dset: val%d' % (i + 1)

            resp = httpx.get(SRV_8001 + '/service1-multi-response-nonlooped', headers={'Host': SRV_8001_HOST})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == 'resp%d' % 3

            resp = httpx.get(SRV_8001 + '/service1-multi-response-nonlooped', headers={'Host': SRV_8001_HOST})
            assert 410 == resp.status_code

            resp = httpx.get(SRV_8001 + '/service1-dataset-inline-nonlooped', headers={'Host': SRV_8001_HOST})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == 'dset: val%d' % 3

            resp = httpx.get(SRV_8001 + '/service1-dataset-inline-nonlooped', headers={'Host': SRV_8001_HOST})
            assert 410 == resp.status_code

            if level == 'service':
                resp = httpx.post(SRV_8001 + '/__admin/reset-iterators', headers={'Host': SRV_8001_HOST})
                assert 204 == resp.status_code

            for i in range(2):
                resp = httpx.get(SRV_8002 + '/service2-multi-response-looped', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = httpx.get(SRV_8002 + '/service2-multi-response-nonlooped', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = httpx.get(SRV_8002 + '/service2-dataset-inline', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'dset: val%d' % (i + 1)

            if level == 'service':
                resp = httpx.post(SRV_8002 + '/__admin/reset-iterators', headers={'Host': SRV_8002_HOST})
                assert 204 == resp.status_code

            if level == 'global':
                resp = httpx.post(MGMT + '/reset-iterators', verify=False)
                assert 204 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/multiresponse.json',
    ])
    def test_tagged_responses(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8003 + '/__admin/tag')
        assert 204 == resp.status_code

        resp = httpx.post(MGMT + '/tag', data="first", verify=False)
        assert 204 == resp.status_code

        resp = httpx.post(MGMT + '/tag?current=first', verify=False)
        assert 204 == resp.status_code

        resp = httpx.get(MGMT + '/tag', verify=False)
        assert 200 == resp.status_code
        data = resp.json()
        for tag in data['tags']:
            assert "first" == tag

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "1.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "1.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.3" == resp.text

        # no tag set - only untagged responses
        resp = httpx.post(SRV_8003 + '/__admin/tag', data="")
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.3" == resp.text

        # first tag set - "first" + untagged responses
        resp = httpx.post(SRV_8003 + '/__admin/tag', data="first")
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8003 + '/__admin/tag')
        assert 200 == resp.status_code
        assert "first" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "1.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "1.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.3" == resp.text

        # first tag set - "second" + untagged responses
        resp = httpx.post(SRV_8003 + '/__admin/tag?current=second')
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "2.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "2.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-responses')
        assert 200 == resp.status_code
        assert "3.3" == resp.text

        # case of no valid response
        resp = httpx.get(SRV_8003 + '/tagged-confusing')
        assert 410 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/multiresponse.json',
    ])
    def test_tagged_datasets(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.post(MGMT + '/tag', data="first", verify=False)
        assert 204 == resp.status_code

        resp = httpx.get(MGMT + '/tag', verify=False)
        assert 200 == resp.status_code
        data = resp.json()
        for tag in data['tags']:
            assert "first" == tag

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 1.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 1.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.3" == resp.text

        # no tag set - only untagged responses
        resp = httpx.post(SRV_8003 + '/__admin/tag', data="")
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.3" == resp.text

        # first tag set - "first" + untagged responses
        resp = httpx.post(SRV_8003 + '/__admin/tag', data="first")
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8003 + '/__admin/tag')
        assert 200 == resp.status_code
        assert "first" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 1.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 1.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.3" == resp.text

        # first tag set - "second" + untagged responses
        resp = httpx.post(SRV_8003 + '/__admin/tag', data="second")
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 2.1" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 2.2" == resp.text

        resp = httpx.get(SRV_8003 + '/tagged-datasets')
        assert 200 == resp.status_code
        assert "dset: 3.3" == resp.text

        # case of no valid response
        resp = httpx.get(SRV_8003 + '/tagged-confusing')
        assert 410 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_unhandled(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + '/unhandled', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'services': []}
        assert expected_data == resp.json()

        resp = httpx.get(SRV_8001 + '/service1x', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1y?a=b&c=d', headers={'Host': SRV_8001_HOST, 'Example-Header': 'Example-Value', 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8002 + '/service2z', headers={'Host': SRV_8002_HOST, 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8002 + '/service2q?a=b&a=c', headers={'Host': SRV_8002_HOST, 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8002 + '/service2q?a[]=b&a[]=c', headers={'Host': SRV_8002_HOST, 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(MGMT + '/unhandled', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_unhandled.json'), 'r').read()[:-1]

        resp = httpx.get(MGMT + '/unhandled?format=yaml', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        assert resp.text == open(get_config_path('configs/stats_unhandled.yaml'), 'r').read()

        resp = httpx.get(SRV_8001 + '/__admin/unhandled', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_unhandled_service1.json'), 'r').read()[:-1]

        resp = httpx.get(SRV_8001 + '/__admin/unhandled?format=yaml', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        assert resp.text == open(get_config_path('configs/stats_unhandled_service1.yaml'), 'r').read()

        resp = httpx.get(SRV_8002 + '/__admin/unhandled', headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_unhandled_service2.json'), 'r').read()[:-1]

        resp = httpx.get(SRV_8002 + '/__admin/unhandled?format=yaml', headers={'Host': SRV_8002_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/x-yaml'
        assert resp.text == open(get_config_path('configs/stats_unhandled_service2.yaml'), 'r').read()

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/no_endpoints.json'
    ])
    def test_get_unhandled_no_endpoints(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + '/unhandled', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'services': []}
        assert expected_data == resp.json()

        resp = httpx.get(SRV_8001 + '/service1x', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(MGMT + '/unhandled', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert len(data['services']) == 1

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_unhandled_changing_headers(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(
            SRV_8001 + '/service1x',
            headers={
                'Host': SRV_8001_HOST,
                'User-Agent': 'mockintosh-test',
                'hdr1': 'val1',
                'hdr2': 'val2',
                'hdr3': 'val3'
            },
            verify=False
        )
        assert 404 == resp.status_code

        resp = httpx.get(MGMT + '/unhandled', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        headers = [x.lower() for x in data['services'][0]['endpoints'][0]['headers']]
        assert set(['hdr1', 'hdr2', 'hdr3']).issubset(set(headers))

        resp = httpx.get(
            SRV_8001 + '/service1x',
            headers={
                'Host': SRV_8001_HOST,
                'User-Agent': 'mockintosh-test',
                'hdr1': 'val1',
                'hdr2': 'val22'
            },
            verify=False
        )
        assert 404 == resp.status_code

        resp = httpx.get(MGMT + '/unhandled', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        headers = [x.lower() for x in data['services'][0]['endpoints'][0]['headers']]
        assert 'hdr1' in headers
        assert 'hdr2' not in headers
        assert 'hdr3' not in headers

    @pytest.mark.parametrize(('config', 'admin_url', 'admin_headers'), [
        ('configs/json/hbs/management/config.json', MGMT, {}),
        ('configs/yaml/hbs/management/config.yaml', MGMT, {}),
        ('configs/json/hbs/management/config.json', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST}),
        ('configs/yaml/hbs/management/config.yaml', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST})
    ])
    def test_delete_unhandled(self, config, admin_url, admin_headers):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(admin_url + '/unhandled', headers=admin_headers, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        ref = data['services'] if admin_url == MGMT else data['services'][0]['endpoints']
        assert len(ref) == 0

        resp = httpx.get(SRV_8001 + '/service1x', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, verify=False)
        assert 404 == resp.status_code

        resp = httpx.get(admin_url + '/unhandled', headers=admin_headers, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        ref = data['services'] if admin_url == MGMT else data['services'][0]['endpoints']
        assert len(ref) == 1
        if admin_url == MGMT:
            len(data['services'][0]['endpoints']) == 1

        resp = httpx.delete(admin_url + '/unhandled', headers=admin_headers, verify=False)
        assert 204 == resp.status_code

        resp = httpx.get(admin_url + '/unhandled', headers=admin_headers, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        ref = data['services'] if admin_url == MGMT else data['services'][0]['endpoints']
        assert len(ref) == 0

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml',
        'tests_integrated/integration_config.yaml'
    ])
    def test_get_oas(self, config):
        config_path = None
        if config.startswith('tests_integrated'):
            config_path = os.path.abspath(os.path.join(os.path.join(__location__, '..'), config))
        else:
            config_path = get_config_path(config)
        self.mock_server_process = run_mock_server(config_path)

        resp = None
        resp = httpx.get(MGMT + '/oas', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        for document in data['documents']:
            validate_spec(document)

        if config.startswith('tests_integrated'):
            resp = httpx.get(SRV_8001 + '/__admin/oas')
        else:
            resp = httpx.get(SRV_8001 + '/__admin/oas', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        validate_spec(resp.json())

        if not config.startswith('tests_integrated'):
            resp = httpx.get(SRV_8002 + '/__admin/oas', headers={'Host': SRV_8002_HOST}, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            validate_spec(resp.json())

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config_custom_oas.json',
        'configs/json/hbs/management/config_custom_oas2.json'
    ])
    def test_get_oas_custom(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + '/oas', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['documents'][0]['info']['title'] == 'Mock for Service1 CUSTOM'

        resp = httpx.get(SRV_8001 + '/__admin/oas', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['info']['title'] == 'Mock for Service1 CUSTOM'

    @pytest.mark.parametrize(('config', 'path'), [
        ('configs/json/hbs/management/config_custom_oas3.json', 'oas_documents/not_existing_file.json'),
        ('configs/json/hbs/management/config_custom_oas4.json', '../common/config.json')
    ])
    def test_get_oas_custom_wrong_path(self, config, path):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + '/oas', verify=False)
        assert 500 == resp.status_code
        # assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        # assert resp.text == 'External OAS document \'%s\' couldn\'t be accessed or found!' % path

        resp = httpx.get(SRV_8001 + '/__admin/oas', headers={'Host': SRV_8001_HOST})
        assert 500 == resp.status_code
        # assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        # assert resp.text == 'External OAS document \'%s\' couldn\'t be accessed or found!' % path

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/resources.json'
    ])
    def test_resources(self, config):
        text_state_1 = 'hello world'
        text_state_2 = 'hello solar system'
        text_state_3 = 'hello galaxy'
        text_state_4 = 'hello universe'
        text_state_5 = 'hello multiverse'
        body_txt_rel_path = 'res/body.txt'
        body_txt_path = get_config_path('configs/json/hbs/management/%s' % body_txt_rel_path)
        new_body_txt_rel_path = 'new_res/new_body.txt'
        new_body_txt_rel_path2 = 'new_res/new_body2.txt'
        os.makedirs(os.path.dirname(body_txt_path), exist_ok=True)
        with open(body_txt_path, 'w') as file:
            file.write(text_state_1)

        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/service1-file', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == text_state_1

        resp = httpx.get(MGMT + '/resources?path=%s' % body_txt_rel_path, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == text_state_1

        resp = httpx.get(MGMT + '/resources?path=%s&format=stream' % body_txt_rel_path, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/octet-stream'
        assert resp.text == text_state_1

        resp = httpx.get(MGMT + '/resources', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert body_txt_rel_path in data['files']

        resp = httpx.get(SRV_8001 + '/__admin/resources', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert body_txt_rel_path in data['files']

        resp = httpx.post(MGMT + '/resources', data={'path': body_txt_rel_path, 'file': text_state_2}, verify=False)
        assert 204 == resp.status_code
        resp = httpx.get(MGMT + '/resources?path=%s' % body_txt_rel_path, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == text_state_2

        resp = httpx.post(
            MGMT + '/resources',
            data={'path': os.path.dirname(body_txt_rel_path)},
            files={os.path.split(body_txt_rel_path)[1]: text_state_3},
            verify=False
        )
        assert 204 == resp.status_code
        resp = httpx.get(MGMT + '/resources?path=%s' % body_txt_rel_path, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == text_state_3

        resp = httpx.delete(MGMT + '/resources?path=%s' % body_txt_rel_path, verify=False)
        assert 204 == resp.status_code
        resp = httpx.get(SRV_8001 + '/service1-file', headers={'Host': SRV_8001_HOST})
        assert 500 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'External template file \'res/body.txt\' couldn\'t be accessed or found!'
        resp = httpx.get(SRV_8001 + '/service1-file2', headers={'Host': SRV_8001_HOST})
        assert 500 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'External template file \'res/body.txt\' couldn\'t be accessed or found!'
        resp = httpx.get(SRV_8001 + '/service1-file-forbidden-path', headers={'Host': SRV_8001_HOST})
        assert 500 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'External template file \'../body/config.json\' couldn\'t be accessed or found!'
        resp = httpx.get(MGMT + '/resources?path=%s' % body_txt_rel_path, verify=False)
        assert 400 == resp.status_code

        with open(get_config_path('configs/json/hbs/management/new_resources.json'), 'r') as file:
            resp = httpx.post(MGMT + '/config', data=file.read(), verify=False)
            assert 204 == resp.status_code
        resp = httpx.get(SRV_8001 + '/service1-file', headers={'Host': SRV_8001_HOST})
        assert 404 == resp.status_code
        resp = httpx.get(MGMT + '/resources?path=%s' % body_txt_rel_path, verify=False)
        assert 400 == resp.status_code
        resp = httpx.get(SRV_8001 + '/service1-new-file', headers={'Host': SRV_8001_HOST})
        assert 500 == resp.status_code

        resp = httpx.post(
            MGMT + '/resources',
            data={'path': os.path.dirname(new_body_txt_rel_path)},
            files={os.path.split(new_body_txt_rel_path)[1]: text_state_4},
            verify=False
        )
        assert 204 == resp.status_code
        resp = httpx.get(MGMT + '/resources?path=%s' % new_body_txt_rel_path, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == text_state_4

        resp = httpx.post(MGMT + '/resources', data={'path': new_body_txt_rel_path, 'file': text_state_5}, verify=False)
        assert 204 == resp.status_code
        resp = httpx.post(MGMT + '/resources', data={'path': new_body_txt_rel_path2, 'file': text_state_5}, verify=False)
        assert 204 == resp.status_code
        resp = httpx.get(MGMT + '/resources?path=%s' % new_body_txt_rel_path, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == text_state_5

        resp = httpx.delete(MGMT + '/resources?path=%s' % new_body_txt_rel_path2, verify=False)
        assert 204 == resp.status_code
        resp = httpx.delete(MGMT + '/resources?path=%s' % os.path.dirname(new_body_txt_rel_path), verify=False)
        assert 204 == resp.status_code
        resp = httpx.get(SRV_8001 + '/service1-new-file', headers={'Host': SRV_8001_HOST})
        assert 500 == resp.status_code
        resp = httpx.get(MGMT + '/resources?path=%s' % new_body_txt_rel_path, verify=False)
        assert 400 == resp.status_code

    def test_resources_various(self):
        config = 'tests_integrated/integration_config.yaml'
        config_path = os.path.abspath(os.path.join(os.path.join(__location__, '..'), config))
        self.mock_server_process = run_mock_server(config_path)

        resp = httpx.get(MGMT + '/resources', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert 'subdir/empty_schema.json' in data['files']
        assert 'cors.html' in data['files']
        assert 'subdir/image.png' in data['files']
        assert '/etc/hosts' not in data['files']
        assert len(data['files']) == len(set(data['files']))

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/resources.json'
    ])
    def test_resources_bad(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(MGMT + '/resources?path=', verify=False)
        assert 400 == resp.status_code

        resp = httpx.get(MGMT + '/resources?path=../common/config.json', verify=False)
        assert 403 == resp.status_code

        resp = httpx.get(MGMT + '/resources?path=not/defined/path', verify=False)
        assert 400 == resp.status_code

        resp = httpx.get(MGMT + '/resources?path=oas_documents/not_existing_file.txt', verify=False)
        assert 400 == resp.status_code

        resp = httpx.get(MGMT + '/resources?path=oas_documents', verify=False)
        assert 400 == resp.status_code

        resp = httpx.get(MGMT + '/resources?path=oas_documents/service1.json', verify=False)
        assert 400 == resp.status_code

        text = 'hello world'

        resp = httpx.post(MGMT + '/resources', data={'path': '', 'file': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'path': '../common/config.json', 'file': text}, verify=False)
        assert 403 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'path': 'somepath'}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'file': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'path': 'not/defined/path', 'file': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'path': 'oas_documents', 'file': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', files={'somepath': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'path': 'oas_documents/'}, files={'../../common/config.json': text}, verify=False)
        assert 403 == resp.status_code

        resp = httpx.post(MGMT + '/resources', data={'path': 'not/defined'}, files={'path': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.post(MGMT + '/resources', files={'oas_documents': text}, verify=False)
        assert 400 == resp.status_code

        resp = httpx.delete(MGMT + '/resources', verify=False)
        assert 400 == resp.status_code

        resp = httpx.delete(MGMT + '/resources?path=', verify=False)
        assert 400 == resp.status_code

        resp = httpx.delete(MGMT + '/resources?path=../common/config.json', verify=False)
        assert 403 == resp.status_code

        resp = httpx.delete(MGMT + '/resources?path=not/defined/path', verify=False)
        assert 400 == resp.status_code

        resp = httpx.delete(MGMT + '/resources?path=dataset.json', verify=False)
        assert 400 == resp.status_code

    @pytest.mark.parametrize(('config', 'admin_url', 'admin_headers'), [
        ('configs/json/hbs/management/config.json', MGMT, {}),
        ('configs/yaml/hbs/management/config.yaml', MGMT, {}),
        ('configs/json/hbs/management/config.json', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST}),
        ('configs/yaml/hbs/management/config.yaml', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST})
    ])
    def test_traffic_log(self, config, admin_url, admin_headers):
        self.mock_server_process = run_mock_server(get_config_path(config))
        test_start_time = datetime.fromtimestamp(time.time()).replace(tzinfo=timezone(timedelta(seconds=10800)))
        service1_response = 'service1'
        service2_response = 'service2'

        for _ in range(2):
            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert not data['log']['_enabled']
            assert data['log']['version'] == '1.2'
            assert data['log']['creator']['name'] == PROGRAM.capitalize()
            assert data['log']['creator']['version'] == mockintosh.__version__
            assert len(data['log']['entries']) == 0

            resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == service1_response

            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert not data['log']['_enabled']
            assert len(data['log']['entries']) == 0

            resp = httpx.post(admin_url + '/traffic-log', data={"enable": True}, headers=admin_headers, verify=False)
            assert 204 == resp.status_code

            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert data['log']['_enabled']
            assert len(data['log']['entries']) == 0

            for _ in range(3):
                resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == service1_response

            for _ in range(2):
                resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == service2_response

            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert data['log']['_enabled']
            if admin_headers:
                assert len(data['log']['entries']) == 3
            else:
                assert len(data['log']['entries']) == 5

            url_parsed1 = urlparse(SRV_8001)
            for entry in data['log']['entries'][0:2]:
                assert entry['_serviceName'] == 'Mock for Service1'
                assert datetime.fromisoformat(entry['startedDateTime']) > test_start_time
                assert entry['time'] > 0

                assert entry['request']['method'] == 'GET'
                assert entry['request']['url'] == '%s://%s:%s/service1' % (url_parsed1.scheme, SRV_8001_HOST, url_parsed1.port)
                assert entry['request']['httpVersion'] == 'HTTP/1.1'
                assert not entry['request']['cookies']
                request_headers = {x['name']: x['value'] for x in entry['request']['headers']}
                assert request_headers['User-Agent'] == 'python-httpx/%s' % httpx.__version__
                assert request_headers['Accept-Encoding'].startswith('gzip, deflate')
                assert request_headers['Accept'] == '*/*'
                assert request_headers['Connection'] == 'keep-alive'
                assert request_headers['Host'] == SRV_8001_HOST
                assert not entry['request']['queryString']
                assert entry['request']['headersSize'] == -1
                assert entry['request']['bodySize'] == 0

                assert entry['response']['status'] == 200
                assert entry['response']['statusText'] == 'OK'
                assert entry['response']['httpVersion'] == 'HTTP/1.1'
                assert not entry['response']['cookies']
                response_headers = {x['name']: x['value'] for x in entry['response']['headers']}
                assert response_headers['Server'] == '%s/%s' % (PROGRAM.capitalize(), mockintosh.__version__)
                assert response_headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert response_headers['Content-Type'] == entry['response']['content']['mimeType'] == 'text/html; charset=UTF-8'
                assert 'Date' in response_headers
                assert response_headers['X-%s-Prompt' % PROGRAM.capitalize()] == 'Hello, I\'m %s.' % PROGRAM.capitalize()
                assert 'Etag' in response_headers
                assert int(response_headers['Content-Length']) == entry['response']['content']['size'] == 8
                assert entry['response']['content']['text'] == service1_response
                assert entry['response']['redirectURL'] == ''
                assert entry['response']['headersSize'] == -1

                assert entry['cache'] == {}
                assert entry['timings']['send'] == 0
                assert entry['timings']['receive'] == 0
                assert entry['timings']['wait'] == entry['time']
                assert entry['timings']['connect'] == 0
                assert entry['timings']['ssl'] == 0

                addr = socket.gethostbyname(url_parsed1.hostname)
                assert entry['serverIPAddress'] == addr
                assert int(entry['connection']) == url_parsed1.port

            if not admin_headers:
                url_parsed2 = urlparse(SRV_8002)
                for entry in data['log']['entries'][3:4]:
                    assert entry['_serviceName'] == 'Mock for Service2'
                    assert datetime.fromisoformat(entry['startedDateTime']) > test_start_time
                    assert entry['time'] > 0

                    assert entry['request']['method'] == 'GET'
                    assert entry['request']['url'] == '%s://%s:%s/service2' % (url_parsed2.scheme, SRV_8002_HOST, url_parsed2.port)
                    assert entry['response']['content']['text'] == service2_response

            resp = httpx.post(admin_url + '/traffic-log', data={"enable": False}, headers=admin_headers, verify=False)
            assert 204 == resp.status_code

            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert not data['log']['_enabled']
            if admin_headers:
                assert len(data['log']['entries']) == 3
            else:
                assert len(data['log']['entries']) == 5

            for _ in range(1):
                resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == service1_response

            for _ in range(1):
                resp = httpx.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == service2_response

            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert not data['log']['_enabled']
            if admin_headers:
                assert len(data['log']['entries']) == 3
            else:
                assert len(data['log']['entries']) == 5

            resp = httpx.delete(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert not data['log']['_enabled']
            if admin_headers:
                assert len(data['log']['entries']) == 3
            else:
                assert len(data['log']['entries']) == 5

            resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            data = resp.json()
            jsonschema_validate(data, HAR_JSON_SCHEMA)
            assert not data['log']['_enabled']
            assert len(data['log']['entries']) == 0

    @pytest.mark.parametrize(('config', 'admin_url', 'admin_headers'), [
        ('configs/json/hbs/management/config.json', MGMT, {}),
        ('configs/yaml/hbs/management/config.yaml', MGMT, {}),
        ('configs/json/hbs/management/config.json', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST}),
        ('configs/yaml/hbs/management/config.yaml', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST})
    ])
    def test_traffic_log_query_string(self, config, admin_url, admin_headers):
        self.mock_server_process = run_mock_server(get_config_path(config))
        somekey = 'somekey'
        somevalue = 'somevalue'
        somevalue2 = 'somevalue2'

        resp = httpx.post(admin_url + '/traffic-log', data={"enable": True}, headers=admin_headers, verify=False)
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1?%s=%s' % (somekey, somevalue), headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        jsonschema_validate(data, HAR_JSON_SCHEMA)
        assert data['log']['_enabled']
        assert len(data['log']['entries']) == 1
        assert len(data['log']['entries'][0]['request']['queryString']) == 1
        assert data['log']['entries'][0]['request']['queryString'][0]['name'] == somekey
        assert data['log']['entries'][0]['request']['queryString'][0]['value'] == somevalue

        resp = httpx.get(SRV_8001 + '/service1?%s=%s&%s=%s' % (somekey, somevalue, somekey, somevalue2), headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        jsonschema_validate(data, HAR_JSON_SCHEMA)
        assert data['log']['_enabled']
        assert len(data['log']['entries']) == 2
        assert len(data['log']['entries'][1]['request']['queryString']) == 2
        assert data['log']['entries'][1]['request']['queryString'][0]['name'] == somekey
        assert data['log']['entries'][1]['request']['queryString'][0]['value'] == somevalue
        assert data['log']['entries'][1]['request']['queryString'][1]['name'] == somekey
        assert data['log']['entries'][1]['request']['queryString'][1]['value'] == somevalue2

    @pytest.mark.parametrize(('config', 'admin_url', 'admin_headers'), [
        ('configs/json/hbs/management/config.json', MGMT, {}),
        ('configs/yaml/hbs/management/config.yaml', MGMT, {}),
        ('configs/json/hbs/management/config.json', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST}),
        ('configs/yaml/hbs/management/config.yaml', SRV_8001 + '/__admin', {'Host': SRV_8001_HOST})
    ])
    def test_traffic_log_post_data(self, config, admin_url, admin_headers):
        self.mock_server_process = run_mock_server(get_config_path(config))
        somekey = 'somekey'
        somevalue = 'somevalue'
        service1_response = 'service1'

        resp = httpx.post(admin_url + '/traffic-log', data={"enable": True}, headers=admin_headers, verify=False)
        assert 204 == resp.status_code

        # POST form data
        resp = httpx.post(SRV_8001 + '/service1-post', headers={'Host': SRV_8001_HOST}, data={somekey: somevalue})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == service1_response

        # POST multipart binary
        image_file = None
        with open(get_config_path('configs/json/hbs/core/image.png'), 'rb') as file:
            image_file = file.read()
            resp = httpx.post(SRV_8001 + '/service1-post', headers={'Host': SRV_8001_HOST}, files={somekey: image_file})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == service1_response

        # POST plain text
        resp = httpx.post(SRV_8001 + '/service1-post', headers={'Host': SRV_8001_HOST}, data=somevalue)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == service1_response

        # POST binary
        resp = httpx.post(SRV_8001 + '/service1-post', headers={'Host': SRV_8001_HOST}, data=image_file)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == service1_response

        resp = httpx.get(admin_url + '/traffic-log', headers=admin_headers, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        jsonschema_validate(data, HAR_JSON_SCHEMA)
        assert data['log']['_enabled']
        assert len(data['log']['entries']) == 4

        # POST form data
        assert data['log']['entries'][0]['request']['bodySize'] == 17
        assert len(data['log']['entries'][0]['request']['postData']['params']) == 1
        assert data['log']['entries'][0]['request']['postData']['mimeType'] == 'application/x-www-form-urlencoded'
        assert data['log']['entries'][0]['request']['postData']['params'][0]['name'] == somekey
        assert data['log']['entries'][0]['request']['postData']['params'][0]['value'] == somevalue
        assert not data['log']['entries'][0]['request']['postData']['text']

        # POST multipart binary
        assert data['log']['entries'][1]['request']['bodySize'] == 796
        assert len(data['log']['entries'][1]['request']['postData']['params']) == 1
        assert data['log']['entries'][1]['request']['postData']['mimeType'] == 'multipart/form-data'
        assert data['log']['entries'][1]['request']['postData']['params'][0]['name'] == somekey
        assert data['log']['entries'][1]['request']['postData']['params'][0]['value'] == _b64encode(image_file)
        assert data['log']['entries'][1]['request']['postData']['params'][0]['_encoding'] == BASE64
        assert not data['log']['entries'][1]['request']['postData']['text']

        # POST plain text
        assert data['log']['entries'][2]['request']['bodySize'] == 9
        assert len(data['log']['entries'][2]['request']['postData']['params']) == 0
        assert data['log']['entries'][2]['request']['postData']['mimeType'] == 'text/plain'
        assert data['log']['entries'][2]['request']['postData']['text'] == somevalue

        # POST binary
        assert data['log']['entries'][3]['request']['bodySize'] == 611
        assert len(data['log']['entries'][3]['request']['postData']['params']) == 0
        assert data['log']['entries'][3]['request']['postData']['mimeType'] == 'text/plain'
        assert data['log']['entries'][3]['request']['postData']['text'] == _b64encode(image_file)
        assert data['log']['entries'][3]['request']['postData']['_encoding'] == BASE64

    def test_traffic_log_binary_response(self):
        config = 'configs/json/hbs/core/binary_response.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.post(SRV_8000 + '/traffic-log', data={"enable": True})
        assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/image')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'image/png'
        image_file = None
        with open(get_config_path('configs/json/hbs/core/image.png'), 'rb') as file:
            image_file = file.read()
            assert resp.content == image_file

        resp = httpx.get(SRV_8000 + '/traffic-log')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        jsonschema_validate(data, HAR_JSON_SCHEMA)
        assert data['log']['_enabled']
        assert len(data['log']['entries']) == 1

        assert data['log']['entries'][0]['response']['content']['size'] == 611
        assert data['log']['entries'][0]['response']['content']['mimeType'] == 'image/png'
        assert data['log']['entries'][0]['response']['content']['text'] == _b64encode(image_file)
        assert data['log']['entries'][0]['response']['content']['encoding'] == BASE64

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/headers/config.json',
        'configs/yaml/hbs/headers/config.yaml'
    ])
    def test_update_global_headers(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/global-headers')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['global-hdr1'] == 'globalval1'
        assert resp.headers['global-hdr2'] == 'globalval2'

        with open(get_config_path(config), 'r') as file:
            data = yaml.safe_load(file.read())
            data['globals']['headers']['global-hdr1'] = 'globalvalX'
            data['globals']['headers']['global-hdr2'] = 'globalvalY'
            resp = httpx.post(SRV_8000 + '/config', data=json.dumps(data))
            assert 204 == resp.status_code

        resp = httpx.get(SRV_8001 + '/global-headers')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['global-hdr1'] == 'globalvalX'
        assert resp.headers['global-hdr2'] == 'globalvalY'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/performance/config.json'
    ])
    def test_update_performance_profile(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8000 + '/config')
        assert 200 == resp.status_code
        data = resp.json()
        assert data['globals']['performanceProfile'] == 'profile1'

        with open(get_config_path(config), 'r') as file:
            data = yaml.safe_load(file.read())
            data['globals']['performanceProfile'] = 'profile2'
            resp = httpx.post(SRV_8000 + '/config', data=json.dumps(data))
            assert 204 == resp.status_code

        resp = httpx.get(SRV_8000 + '/config')
        assert 200 == resp.status_code
        data = resp.json()
        assert data['globals']['performanceProfile'] == 'profile2'

    @pytest.mark.parametrize(('config'), [
        'configs/fallback_to.json',
        'configs/fallback_to.yaml'
    ])
    def test_fallback_to(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8000 + '/unhandled')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'services': []}
        assert expected_data == resp.json()

        resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = httpx.get(SRV_8000 + '/unhandled')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'services': []}
        assert expected_data == resp.json()

        resp = httpx.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
        assert resp.headers['Server'] == '%s/%s' % (PROGRAM.capitalize(), mockintosh.__version__)
        assert resp.headers['X-%s-Prompt' % PROGRAM.capitalize()] == 'Hello, I\'m %s.' % PROGRAM.capitalize()
        assert resp.headers['X-Content-Type-Options'] == 'nosniff'
        data = resp.json()

        assert data['code'] == 200
        assert type(data['meta']['pagination']['total']) is int
        assert data['meta']['pagination']['limit'] == 20
        assert len(data['data']) <= 20
        assert data['data'][0].keys() >= {'id', 'name', 'email', 'gender', 'status', 'created_at', 'updated_at'}

        resp = httpx.get(SRV_8000 + '/unhandled')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        assert data['services'][0]['name'] == 'Mock for Service1'
        assert data['services'][0]['port'] == 8001
        assert data['services'][0]['endpoints'][0]['path'] == '/users'
        assert data['services'][0]['endpoints'][0]['method'] == 'GET'
        assert data['services'][0]['endpoints'][0]['response']['status'] == 200
        assert data['services'][0]['endpoints'][0]['response']['headers']['Content-Type'] == 'application/json; charset=utf-8'
        assert data['services'][0]['endpoints'][0]['response']['headers']['Server'] == '%s/%s' % (PROGRAM.capitalize(), mockintosh.__version__)
        assert data['services'][0]['endpoints'][0]['response']['headers']['X-%s-Prompt' % PROGRAM.capitalize()] == 'Hello, I\'m %s.' % PROGRAM.capitalize()
        assert data['services'][0]['endpoints'][0]['response']['headers']['X-Content-Type-Options'] == 'nosniff'
        body = json.loads(data['services'][0]['endpoints'][0]['response']['body'])

        assert body['code'] == 200
        assert type(body['meta']['pagination']['total']) is int
        assert body['meta']['pagination']['limit'] == 20
        assert len(body['data']) <= 20
        assert body['data'][0].keys() >= {'id', 'name', 'email', 'gender', 'status', 'created_at', 'updated_at'}

        resp = httpx.get(SRV_8002 + '/service1', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

    @pytest.mark.parametrize(('config'), [
        'configs/fallback_to.json',
        'configs/fallback_to.yaml'
    ])
    def test_fallback_to_query_string(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8001 + '/service1q?a=b', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'})
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1q?a=b&a=c', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'})
        assert 404 == resp.status_code

        resp = httpx.get(SRV_8001 + '/service1q?a[]=b&a[]=c', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'})
        assert 404 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/fallback_to.json'
    ])
    def test_fallback_to_body_param(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        expected_data = {"code": 401, "meta": None, "data": {"message": "Authentication failed"}}
        resp = httpx.post(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, files={'example': 'example'})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
        assert resp.json() == expected_data

        resp = httpx.post(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, data={'example': 'example'})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
        assert resp.json() == expected_data

        with open(get_config_path('configs/json/hbs/core/image.png'), 'rb') as file:
            image_file = file.read()
            resp = httpx.post(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, files={'example': image_file})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
            assert resp.json() == expected_data

            resp = httpx.post(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'}, data={'example': image_file})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=utf-8'
            assert resp.json() == expected_data

    @pytest.mark.parametrize(('config'), [
        'configs/fallback_to.json'
    ])
    def test_fallback_to_binary_response(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8003 + '/250/250', headers={'Host': SRV_8003_HOST})
        assert 200 == resp.status_code

        resp = httpx.get(SRV_8000 + '/unhandled')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        assert data['services'][0]['endpoints'][0]['response']['headers']['Content-Type'] == 'image/jpeg'

    @pytest.mark.parametrize(('config'), [
        'configs/internal_circular_fallback_to.json'
    ])
    def test_internal_circular_fallback_to(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8002 + '/serviceX', headers={'Host': SRV_8002_HOST}, timeout=30)
        assert 504 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Redirected request to: GET http://service1.example.com:8001/serviceX is timed out!'

    @pytest.mark.parametrize(('config'), [
        'configs/fallback_to.json'
    ])
    def test_fallback_to_unknown_name(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = httpx.get(SRV_8004 + '/serviceX', headers={'Host': SRV_8004_HOST}, timeout=30)
        assert 502 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Name or service not known: http://service4.example.com:8004'


class TestPerformanceProfile():

    def setup_method(self):
        self.mock_server_process = None

    def teardown_method(self):
        if self.mock_server_process is not None:
            self.mock_server_process.terminate()

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/performance/config.json'
    ])
    def test_deterministic_delay(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        start = time.time()
        resp = httpx.get(SRV_8003 + '/service3', headers={'Host': SRV_8003_HOST}, timeout=30)
        end = time.time()
        delta = end - start
        assert 200 == resp.status_code
        assert 'service3' == resp.text
        assert 7.3 < delta

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/performance/config.json'
    ])
    def test_faults_many(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        for _ in range(10):
            try:
                resp = httpx.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
                assert resp.status_code in (200, 201, 400, 500, 503)
            except httpx.ReadError as e:
                assert str(e) == '[Errno 104] Connection reset by peer'
            except httpx.RemoteProtocolError as e:
                assert 'ConnectionClosed' in str(e)

    def test_trigger(self):
        faults = {
            'PASS': 0.25,
            '200': 0.25,
            'RST': 0.25,
            'FIN': 0.25
        }
        profile = PerformanceProfile(1.0, delay=0.0, faults=faults)
        for _ in range(50):
            status_code = profile.trigger(201)
            assert str(status_code) in faults or status_code == 201


class TestKafka():

    mock_server_process = None
    config = 'configs/yaml/hbs/kafka/config.yaml'

    @classmethod
    def setup_class(cls):
        cmd = '%s %s' % (PROGRAM, get_config_path(TestKafka.config))
        if should_cov:
            cmd = 'coverage run --parallel -m %s' % cmd
        this_env = os.environ.copy()
        TestKafka.mock_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
            env=this_env
        )
        time.sleep(KAFKA_CONSUME_WAIT / 2)

    @classmethod
    def teardown_class(cls):
        TestKafka.mock_server_process.kill()
        name = PROGRAM
        if should_cov:
            name = 'coverage'
        os.system('killall -2 %s' % name)

    def test_get_kafka(self):
        for _format in ('json', 'yaml'):
            resp = httpx.get(MGMT + '/async?format=%s' % _format, verify=False)
            assert 200 == resp.status_code
            if _format == 'json':
                assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
            elif _format == 'yaml':
                assert resp.headers['Content-Type'] == 'application/x-yaml'
            data = yaml.safe_load(resp.text)

            with open(get_config_path(TestKafka.config), 'r') as file:
                data2 = yaml.safe_load(file.read())
                for i, service in enumerate(data['services']):
                    service2 = data2['services'][i]
                    new_actors = []
                    for actor in service['actors']:
                        actor.pop('limit', None)
                        new_actors.append(actor)
                    new_actors2 = []
                    for actor2 in service['actors']:
                        actor2.pop('limit', None)
                        new_actors2.append(actor2)
                    assert service['name'] == service2['name']
                    assert service['address'] == service2['address']
                    assert new_actors == new_actors2

    def test_get_kafka_consume(self):
        key = 'key2'
        value = 'value2'
        headers = {'hdr2': 'val2'}

        kafka.produce(
            KAFKA_ADDR,
            'topic2',
            key,
            value,
            headers,
            None,
            PYBARS
        )

        time.sleep(KAFKA_CONSUME_WAIT)

        resp = httpx.get(MGMT + '/async/0/1', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        assert any(row['key'] == key and row['value'] == value and row['headers'] == headers for row in data['log'])

    def test_get_kafka_produce_consume_loop(self):
        key = 'key3'
        value = 'value3'
        headers = {'hdr3': 'val3'}

        time.sleep(KAFKA_CONSUME_WAIT)

        resp = httpx.get(MGMT + '/async/0/3', verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()

        assert any(row['key'] == key and row['value'] == value and row['headers'] == headers for row in data['log'])

    def test_get_kafka_bad_requests(self):
        resp = httpx.get(MGMT + '/async/13/0', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Service not found!'

        resp = httpx.get(MGMT + '/async/0/13', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Actor not found!'

        resp = httpx.get(MGMT + '/async/0/0', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'This actor is not a consumer!'

    def test_post_kafka_produce(self):
        key = 'key1'
        value = 'value1'
        headers = {'hdr1': 'val1'}

        stop = {'val': False}
        log = []
        t = threading.Thread(target=kafka.consume, args=(
            KAFKA_ADDR,
            'topic1'
        ), kwargs={
            'log': log,
            'stop': stop
        })
        t.daemon = True
        t.start()

        time.sleep(KAFKA_CONSUME_WAIT / 2)

        resp = httpx.post(MGMT + '/async/0/0', verify=False)
        assert 200 == resp.status_code

        time.sleep(KAFKA_CONSUME_WAIT)

        stop['val'] = True
        t.join()
        assert any(row[0] == key and row[1] == value and row[2] == headers for row in log)

    def test_post_kafka_produce_by_actor_name(self):
        key = 'key6'
        value = 'value6'
        headers = {'hdr6': 'val6'}

        stop = {'val': False}
        log = []
        t = threading.Thread(target=kafka.consume, args=(
            KAFKA_ADDR,
            'topic6'
        ), kwargs={
            'log': log,
            'stop': stop
        })
        t.daemon = True
        t.start()

        time.sleep(KAFKA_CONSUME_WAIT / 2)

        resp = httpx.post(MGMT + '/async', data={'actor': 'actor6'}, verify=False)
        assert 200 == resp.status_code

        time.sleep(KAFKA_CONSUME_WAIT)

        stop['val'] = True
        t.join()
        assert any(row[0] == key and row[1] == value and row[2] == headers for row in log)

    def test_post_kafka_reactive_consumer(self):
        topic = 'topic5'
        key = 'key5'
        value = 'value5'
        headers = {'hdr5': 'val5'}

        stop = {'val': False}
        log = []
        t = threading.Thread(target=kafka.consume, args=(
            KAFKA_ADDR,
            topic
        ), kwargs={
            'log': log,
            'stop': stop
        })
        t.daemon = True
        t.start()

        time.sleep(KAFKA_CONSUME_WAIT / 2)

        kafka.produce(
            KAFKA_ADDR,
            topic,
            key,
            value,
            {'hdr5': 'val5'},
            None,
            PYBARS
        )

        time.sleep(KAFKA_CONSUME_WAIT)

        stop['val'] = True
        t.join()
        assert any(row[0] == key and row[1] == value and row[2] == headers for row in log)

    def test_post_kafka_bad_requests(self):
        actor13 = 'actor13'
        resp = httpx.post(MGMT + '/async', data={'actor': actor13}, verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'No producer actor is found for: \'%s\'' % actor13

        resp = httpx.post(MGMT + '/async/13/0', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Service not found!'

        resp = httpx.post(MGMT + '/async/0/13', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'Actor not found!'

        resp = httpx.post(MGMT + '/async/0/1', verify=False)
        assert 400 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'This actor is not a producer!'

    def test_post_kafka_producer_templated(self):
        stop = {'val': False}
        log = []
        t = threading.Thread(target=kafka.consume, args=(
            KAFKA_ADDR,
            'templated-producer'
        ), kwargs={
            'log': log,
            'stop': stop
        })
        t.daemon = True
        t.start()

        time.sleep(KAFKA_CONSUME_WAIT / 2)

        resp = httpx.post(MGMT + '/async', data={'actor': 'templated-producer'}, verify=False)
        assert 200 == resp.status_code

        resp = httpx.post(MGMT + '/async', data={'actor': 'templated-producer'}, verify=False)
        assert 200 == resp.status_code

        time.sleep(KAFKA_CONSUME_WAIT)

        stop['val'] = True
        t.join()
        for i in range(2):
            assert any(
                (row[0].startswith('prefix-') and is_valid_uuid(row[0][7:]))
                and  # noqa: W504, W503
                (row[1][0].isupper())
                and  # noqa: W504, W503
                (row[2]['name'] == 'templated')
                and  # noqa: W504, W503
                (row[2]['constant'] == 'constant-value')
                and  # noqa: W504, W503
                (len(row[2]['timestamp']) == 10 and row[2]['timestamp'].isnumeric())
                and  # noqa: W504, W503
                (int(row[2]['counter']) == i + 1)
                and  # noqa: W504, W503
                (int(row[2]['fromFile'][10:11]) < 10 and int(row[2]['fromFile'][28:30]) < 100)
                for row in log
            )
