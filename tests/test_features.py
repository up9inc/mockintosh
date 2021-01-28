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
from datetime import datetime, timedelta

import pytest
import requests
from requests.exceptions import ConnectionError

from mockintosh.constants import PROGRAM
from utilities import (
    tcping,
    run_mock_server,
    get_config_path,
    nostdout,
    nostderr
)

configs = [
    'configs/json/hbs/common/config.json',
    'configs/json/j2/common/config.json',
    'configs/yaml/hbs/common/config.yaml',
    'configs/yaml/j2/common/config.yaml'
]

SRV_8001 = os.environ.get('SRV1', 'http://localhost:8001')
SRV_8002 = os.environ.get('SRV2', 'http://localhost:8002')
SRV_8003 = os.environ.get('SRV2', 'http://localhost:8003')
SRV_9000 = os.environ.get('SRV2', 'http://localhost:9000')

SRV_8001_HOST = 'service1.example.com'
SRV_8002_HOST = 'service2.example.com'
SRV_8003_HOST = 'service3.example.com'

SRV_8001_SSL = SRV_8001[:4] + 's' + SRV_8001[4:]
SRV_8002_SSL = SRV_8002[:4] + 's' + SRV_8002[4:]
SRV_8003_SSL = SRV_8003[:4] + 's' + SRV_8003[4:]


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
        resp = requests.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
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
        resp = requests.get(SRV_8001 + '/users/%s' % user_id, headers={'Host': SRV_8001_HOST})
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
        resp = requests.post(SRV_8002 + '/companies', headers={'Host': SRV_8002_HOST})
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
        self.mock_server_process = run_mock_server()
        resp = requests.get(SRV_8001 + '/')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'hello world'

    @pytest.mark.parametrize(('config'), configs)
    def test_quiet(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--quiet')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_verbose(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--verbose')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_interceptor_single(self, config):
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.dummy1'
        )
        resp = requests.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
        assert 414 == resp.status_code

    @pytest.mark.parametrize(('config'), configs)
    def test_interceptor_multiple(self, config):
        self.mock_server_process = run_mock_server(
            get_config_path(config),
            '--interceptor=interceptingpackage.interceptors.dummy1',
            '--interceptor=interceptingpackage.interceptors.dummy2'
        )
        resp = requests.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
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
        config = 'configs/json/hbs/core/multiple_services.json'
        self.mock_server_process = run_mock_server(get_config_path(config), 'Mock for Service1')

        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8001 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 404 == resp.status_code

    def test_port_override(self):
        os.environ['MOCKINTOSH_FORCE_PORT'] = '8002'
        config = 'configs/json/hbs/core/multiple_services.json'
        self.mock_server_process = run_mock_server(get_config_path(config), 'Mock for Service1')

        resp = requests.get(SRV_8002 + '/service1', headers={'Host': SRV_8001_HOST})
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
        resp = requests.get(SRV_8003 + '/interceptor-modified')
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
        resp = requests.get(SRV_8001 + '/users', headers={'Host': SRV_8001_HOST})
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
        resp = requests.get(
            SRV_8003 + '/request1?a=hello%20world&b=3',
            headers={'Cache-Control': 'no-cache'},
            data='hello world'
        )
        assert 200 == resp.status_code

        resp = requests.post(
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
        resp = requests.get(SRV_8001 + '/%s' % var, headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        if 'j2' in config:
            assert resp.text == '{{varname}}'
        else:
            assert resp.text == var

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/templating_engine_in_response.json',
        'configs/json/j2/core/templating_engine_in_response.json',
        'configs/yaml/hbs/core/templating_engine_in_response.yaml',
        'configs/yaml/j2/core/templating_engine_in_response.yaml'
    ])
    def test_correct_templating_engine_in_response_should_render_correctly(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})
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
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})

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
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})

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
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})

        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'

    def test_two_services_one_with_hostname_one_without(self):
        config = 'configs/json/hbs/core/two_services_one_with_hostname_one_without.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        # Service 1 (the one without the hostname) should accept any `Host` header
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        # Service 2 (the one with the hostname) should require a correct `Host` header
        resp = requests.get(SRV_8002 + '/')
        assert 404 == resp.status_code

        resp = requests.get(SRV_8002 + '/', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

    def test_endpoint_id_header(self):
        config = 'configs/json/hbs/core/endpoint_id_header.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['X-%s-Endpoint-Id' % PROGRAM] == 'endpoint-id-1'

        resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['X-%s-Endpoint-Id' % PROGRAM] == 'endpoint-id-2'

    def test_body_json_schema(self):
        config = 'configs/json/hbs/core/body_json_schema.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.post(SRV_8001 + '/endpoint1', json={"somekey": "valid"})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'endpoint1: body json schema matched'

        resp = requests.post(SRV_8001 + '/endpoint1', json={"somekey2": "invalid"})
        assert 400 == resp.status_code

        resp = requests.post(SRV_8001 + '/endpoint2')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'endpoint2'

    def test_http_verbs(self):
        config = 'configs/json/hbs/core/http_verbs.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'GET request'

        resp = requests.get(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'GET request'

        resp = requests.post(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'POST request'

        resp = requests.head(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == ''

        resp = requests.delete(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'DELETE request'

        resp = requests.patch(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'PATCH request'

        resp = requests.put(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'PUT request'

        resp = requests.options(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'OPTIONS request'

    def test_http_verb_not_allowed(self):
        config = 'configs/json/hbs/core/http_verbs.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/method-not-allowed-unless-post')
        assert 405 == resp.status_code

        resp = requests.post(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code

        resp = requests.head(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code

        resp = requests.delete(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code

        resp = requests.patch(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code

        resp = requests.put(SRV_8001 + '/method-not-allowed-unless-get')
        assert 405 == resp.status_code

        resp = requests.options(SRV_8001 + '/method-not-allowed-unless-get')
        assert 404 == resp.status_code

    def test_no_response_body_204(self):
        config = 'configs/json/hbs/core/no_response_body_204.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/endpoint1')
        assert 204 == resp.status_code

    def test_empty_response_body(self):
        config = 'configs/json/hbs/core/empty_response_body.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/endpoint1')
        assert 200 == resp.status_code
        assert resp.text == ''

    def test_binary_response(self):
        config = 'configs/json/hbs/core/binary_response.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/hello')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['hello'], str)

        resp = requests.get(SRV_8001 + '/image')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'image/png'
        with open(get_config_path('configs/json/hbs/core/image.png'), 'rb') as file:
            assert resp.content == file.read()

    def test_ssl_true(self):
        config = 'configs/json/hbs/core/ssl_true.json'
        self.mock_server_process = run_mock_server(get_config_path(config), wait=20)

        resp = requests.get(SRV_8001_SSL + '/service1', headers={'Host': SRV_8001_HOST}, verify=False)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

        resp = requests.get(SRV_8003_SSL + '/service3', headers={'Host': SRV_8003_HOST}, verify=False)
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
        resp = requests.get(SRV_8001 + '/undefined')
        assert 200 == resp.status_code
        assert resp.text == 'Hello {{undefined_var}} world'

        assert os.path.isfile(logfile_name)
        with open(logfile_name, 'r') as file:
            server_log = file.read()
            if 'j2' in config:
                assert "WARNING] Jinja2: Could not find variable `undefined_var`" in server_log
            else:
                assert "WARNING] Handlebars: Could not find variable 'undefined_var'" in server_log

        resp = requests.get(SRV_8001 + '/undefined2')
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

        resp = requests.get(SRV_8001 + '/undefined3')
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

        resp = requests.get(SRV_8001 + '/undefined4')
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

        resp = requests.get(SRV_8001 + '/undefined5')
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
            resp = requests.get(SRV_8001 + '/counter', headers={'Host': SRV_8001_HOST})
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
            assert resp.text == 'Hello %d world' % i

    @pytest.mark.parametrize(('config'), [
        'configs/yaml/hbs/core/subexpression.yaml',
        'configs/yaml/j2/core/subexpression.yaml'
    ])
    def test_subexpression(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/subexpression')
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

        resp = requests.get(SRV_8001 + '/timestamp')
        utcnow = datetime.utcnow()
        now = time.time()

        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        resp_int = int(resp.text)
        diff = now - resp_int
        assert diff < 1

        resp = requests.get(SRV_8001 + '/timestamp-shift')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        assert int(segments[0]) < int(segments[1])
        assert int(segments[0]) > int(segments[2])

        resp = requests.get(SRV_8001 + '/ftimestamp')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        diff = now - float(segments[0])
        assert diff < 1
        assert len(segments[0].split('.')[1]) <= 3
        assert len(segments[1].split('.')[1]) <= 7

        resp = requests.get(SRV_8001 + '/ftimestamp-shift')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        assert float(segments[0]) < float(segments[1])
        assert float(segments[0]) > float(segments[2])

        resp = requests.get(SRV_8001 + '/date')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        segments = resp.text.split('<br>')
        pattern = '%Y-%m-%dT%H:%M:%S.%f'
        delta = utcnow - datetime.strptime(segments[0], pattern)
        assert delta.days < 2
        pattern = '%Y-%m-%d %H:%M'
        delta = utcnow - datetime.strptime(segments[1], pattern)
        assert delta.seconds / 60 < 2

        resp = requests.get(SRV_8001 + '/date-shift')
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

        resp = requests.get(SRV_8001 + '/normal')
        assert 200 == resp.status_code
        assert resp.text == 'Hello world'

        try:
            requests.get(SRV_8001 + '/reset')
        except ConnectionError as e:
            assert str(e).split(',')[1].strip().startswith('ConnectionResetError')

        try:
            requests.get(SRV_8001 + '/close')
        except ConnectionError as e:
            assert str(e).split(',')[1].strip().startswith('RemoteDisconnected')

        try:
            requests.get(SRV_8001 + '/reset2')
        except ConnectionError as e:
            assert str(e).split(',')[1].strip().startswith('ConnectionResetError')

        try:
            requests.get(SRV_8001 + '/close2')
        except ConnectionError as e:
            assert str(e).split(',')[1].strip().startswith('RemoteDisconnected')

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/faker.json',
        'configs/json/j2/core/faker.json'
    ])
    def test_faker(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/faker')
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

        resp = requests.get(SRV_8001 + '/endp1')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == '&amp; &lt; &quot; &gt;'


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
        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 202 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 403 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

    def test_status_code_templated(self, config):
        query = '?rc=303'
        resp = requests.get(SRV_8002 + '/service2-endpoint2' + query, headers={'Host': SRV_8002_HOST})
        assert 303 == resp.status_code


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
        resp = requests.get(SRV_8001 + '/parameter', headers={"hdr1": param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with parameter: %s' % param

        resp = requests.get(SRV_8001 + '/parameter/template-file', headers={"hdr1": param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with parameter'] == param

    def test_static_value(self, config):
        static_val = 'myValue'
        resp = requests.get(SRV_8001 + '/static-value', headers={"hdr1": static_val})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with static value: %s' % static_val

        resp = requests.get(SRV_8001 + '/static-value/template-file', headers={"hdr1": static_val})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with static value'] == static_val

    def test_regex_capture_group(self, config):
        param = str(int(time.time()))
        resp = requests.get(SRV_8001 + '/regex-capture-group', headers={"hdr1": 'prefix-%s-suffix' % param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with regex capture group: %s' % param

        resp = requests.get(SRV_8001 + '/regex-capture-group/template-file', headers={"hdr1": 'prefix-%s-suffix' % param})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with regex capture group'] == param

    def test_missing_header_should_400(self, config):
        static_val = 'myValue'
        resp = requests.get(SRV_8001 + '/static-value', headers={"hdrX": static_val})
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/static-value/template-file', headers={"hdrX": static_val})
        assert 400 == resp.status_code

    def test_wrong_static_value_should_400(self, config):
        static_val = 'wrongValue'
        resp = requests.get(SRV_8001 + '/static-value', headers={"hdr1": static_val})
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/static-value/template-file', headers={"hdr1": static_val})
        assert 400 == resp.status_code

    def test_wrong_regex_pattern_should_400(self, config):
        param = str(int(time.time()))
        resp = requests.get(SRV_8001 + '/regex-capture-group', headers={"hdr1": 'idefix-%s-suffix' % param})
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/regex-capture-group/template-file', headers={"hdr1": 'idefix-%s-suffix' % param})
        assert 400 == resp.status_code

    def test_first_alternative(self, config):
        static_val = 'myValue'
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        resp = requests.get(SRV_8001 + '/alternative', headers={
            "hdr1": static_val,
            "hdr2": param2,
            "hdr3": 'prefix-%s-suffix' % param3
        })
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'headers match: %s %s %s' % (static_val, param2, param3)

        resp = requests.get(SRV_8001 + '/alternative/template-file', headers={
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
        resp = requests.get(SRV_8001 + '/alternative', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'hdr4 request header: %s' % static_val

        resp = requests.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['hdr4 request header'] == static_val

    def test_nonexisting_alternative_should_400(self, config):
        static_val = 'another header'
        resp = requests.get(SRV_8001 + '/alternative', headers={
            "hdr5": static_val
        })
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr5": static_val
        })
        assert 400 == resp.status_code

    def test_response_headers_in_first_alternative(self, config):
        static_val = 'myValue'
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        resp = requests.get(SRV_8001 + '/alternative', headers={
            "hdr1": static_val,
            "hdr2": param2,
            "hdr3": 'prefix-%s-suffix' % param3
        })
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.cookies['name1'] == param2
        assert resp.cookies['name2'] == 'prefix-%s-suffix' % param3

        resp = requests.get(SRV_8001 + '/alternative/template-file', headers={
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
        resp = requests.get(SRV_8001 + '/alternative', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['Hdr4'] == 'hdr4 request header: %s' % static_val

        resp = requests.get(SRV_8001 + '/alternative/template-file', headers={
            "hdr4": static_val
        })
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.headers['Hdr4'] == 'hdr4 request header: %s' % static_val

    def test_global_headers(self, config):
        resp = requests.get(SRV_8001 + '/global-headers')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.headers['global-hdr1'] == 'globalval1'
        assert resp.headers['global-hdr2'] == 'globalval2'

        resp = requests.get(SRV_8001 + '/global-headers-modified')
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
        resp = requests.get(SRV_8001 + '/parameterized1/text/%s/subval' % param)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'intoVar capture: %s' % param

        resp = requests.get(SRV_8001 + '/parameterized1/template-file/%s/subval' % param)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['var'] == param

    def test_static_value_priority(self, config):
        resp = requests.get(SRV_8001 + '/parameterized1/text/staticVal/subval')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'static path components have priority'

    def test_regex_match(self, config):
        path = '/parameterized2/text/prefix-%s/subval' % str(int(time.time()))
        resp = requests.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'regex match: %s' % path

        path = '/parameterized2/template-file/prefix-%s/subval' % str(int(time.time()))
        resp = requests.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['request']['path'] == path

        path = '/parameterized2/text/wrongprefix-%s/subval' % str(int(time.time()))
        resp = requests.get(SRV_8001 + path)
        assert 404 == resp.status_code

    def test_regex_capture_group(self, config):
        param = str(int(time.time()))
        path = '/parameterized1/text/prefix2-%s/subval2' % param
        resp = requests.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'regex capture group: %s' % param

        path = '/parameterized1/template-file/prefix2-%s/subval2' % param
        resp = requests.get(SRV_8001 + path)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['capture'] == param

    def test_multiple_parameters(self, config):
        param1 = str(int(time.time()))
        param2 = str(int(time.time()))
        param3 = str(int(time.time()))
        resp = requests.get(SRV_8001 + '/parameterized3/text/%s/%s/%s' % (param1, param2, param3))
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'var1: %s, var2: %s, var3: %s' % (param1, param2, param3)

        resp = requests.get(SRV_8001 + '/parameterized3/template-file/%s/%s/%s' % (param1, param2, param3))
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
        resp = requests.get(SRV_8001 + path)
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
        resp = requests.get(SRV_8001 + path)
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
        resp = requests.get(SRV_8001 + path)
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
        resp = requests.get(SRV_8001 + path)
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
        resp = requests.delete(SRV_8001 + '/carts/%s' % param1)
        assert 202 == resp.status_code

        resp = requests.post(SRV_8001 + '/carts/%s/items' % param1)
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json'
        data = resp.json()
        assert data['id'] == 'L8VEqJRB4R'

        resp = requests.get(SRV_8001 + '/carts/%s/merge' % param1)
        assert 202 == resp.status_code

        resp = requests.get(SRV_8001 + '/carts/%s/items' % param1)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json'
        data = resp.json()
        assert isinstance(data, list) and not data

        resp = requests.patch(SRV_8001 + '/carts/%s/items' % param1)
        assert 202 == resp.status_code

        resp = requests.delete(SRV_8001 + '/carts/%s/items/%s' % (param1, param2))
        assert 202 == resp.status_code


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
        resp = requests.get(SRV_8001 + '/parameter' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with parameter: %s' % param

        resp = requests.get(SRV_8001 + '/parameter/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with parameter'] == param

    def test_static_value(self, config):
        static_val = 'my Value'
        query = '?param1=%s' % static_val
        resp = requests.get(SRV_8001 + '/static-value' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with static value: %s' % static_val

        resp = requests.get(SRV_8001 + '/static-value/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with static value'] == static_val

    def test_regex_capture_group(self, config):
        param = str(int(time.time()))
        query = '?param1=prefix-%s-suffix' % param
        resp = requests.get(SRV_8001 + '/regex-capture-group' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'matched with regex capture group: %s' % param

        resp = requests.get(SRV_8001 + '/regex-capture-group/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['matched with regex capture group'] == param

    def test_missing_query_param_should_400(self, config):
        static_val = 'myValue'
        query = '?paramX=%s' % static_val
        resp = requests.get(SRV_8001 + '/static-value' + query)
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/static-value/template-file' + query)
        assert 400 == resp.status_code

    def test_wrong_static_value_should_400(self, config):
        static_val = 'wrong Value'
        query = '?param1=%s' % static_val
        resp = requests.get(SRV_8001 + '/static-value' + query)
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/static-value/template-file' + query)
        assert 400 == resp.status_code

    def test_wrong_regex_pattern_should_400(self, config):
        param = str(int(time.time()))
        query = '?param1=idefix-%s-suffix' % param
        resp = requests.get(SRV_8001 + '/regex-capture-group' + query)
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/regex-capture-group/template-file' + query)
        assert 400 == resp.status_code

    def test_first_alternative(self, config):
        static_val = 'my Value'
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        query = '?param1=%s&param2=%s&param3=prefix-%s-suffix' % (static_val, param2, param3)
        resp = requests.get(SRV_8001 + '/alternative' + query)
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'query string match: %s %s %s' % (static_val, param2, param3)

        resp = requests.get(SRV_8001 + '/alternative/template-file' + query)
        assert 201 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['request.queryString.param1'] == static_val
        assert data['anyValIntoVar'] == param2
        assert data['capturedVar'] == param3

    def test_second_alternative(self, config):
        static_val = 'another query string'
        query = '?param4=%s' % static_val
        resp = requests.get(SRV_8001 + '/alternative' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'param4 request query string: %s' % static_val

        resp = requests.get(SRV_8001 + '/alternative/template-file' + query)
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        data = resp.json()
        assert data['param4 request query string'] == static_val

    def test_nonexisting_alternative_should_400(self, config):
        static_val = 'another query string'
        query = '?param5=%s' % static_val
        resp = requests.get(SRV_8001 + '/alternative' + query)
        assert 400 == resp.status_code

        resp = requests.get(SRV_8001 + '/alternative/template-file' + query)
        assert 400 == resp.status_code


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
        resp = requests.post(SRV_8001 + '/body-jsonpath-tpl', json={"key": "val", "key2": 123})
        assert 200 == resp.status_code
        assert 'body jsonpath matched: val 123' == resp.text

        resp = requests.post(SRV_8001 + '/body-jsonpath-tpl', json={"key": None})
        assert 200 == resp.status_code
        assert 'body jsonpath matched: null ' == resp.text

        resp = requests.post(SRV_8001 + '/body-jsonpath-tpl', data="not json")
        assert 200 == resp.status_code
        if 'j2' in config:
            assert "body jsonpath matched: {{jsonPath(request.json, '$.key')}} {{jsonPath(request.json, '$.key2')}}" == resp.text
        else:
            assert "body jsonpath matched: {{jsonPath request.json '$.key'}} {{jsonPath request.json '$.key2'}}" == resp.text


class TestManagement():

    def setup_method(self):
        self.mock_server_process = None

    def teardown_method(self):
        if self.mock_server_process is not None:
            self.mock_server_process.terminate()

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_root(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_9000 + '/')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'

        resp = requests.get(SRV_8001 + '/__admin/', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_config(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_9000 + '/config')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_config.json'), 'r').read()[:-1]

        resp = requests.get(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_config_service1.json'), 'r').read()[:-1]

        resp = requests.get(SRV_8002 + '/__admin/config', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        assert resp.text == open(get_config_path('configs/stats_config_service2.json'), 'r').read()[:-1]

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_post_config(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        with open(get_config_path('configs/json/hbs/management/new_config.json'), 'r') as file:
            data = json.load(file)
            resp = requests.post(SRV_9000 + '/config', json=data)
            assert 204 == resp.status_code

        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8001 + '/service1-new-config', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-config'

        resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

        resp = requests.get(SRV_9000 + '/config')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        with open(get_config_path('configs/json/hbs/management/new_config.json'), 'r') as file:
            data = json.load(file)
            assert data == resp.json()

        with open(get_config_path('configs/json/hbs/management/new_service1.json'), 'r') as file:
            data = json.load(file)
            resp = requests.post(SRV_8001 + '/__admin/config', headers={'Host': SRV_8001_HOST}, json=data)
            assert 204 == resp.status_code

        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8001 + '/service1-new-service', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-service'

        resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

        with open(get_config_path('configs/json/hbs/management/new_service2.json'), 'r') as file:
            data = json.load(file)
            resp = requests.post(SRV_8002 + '/__admin/config', headers={'Host': SRV_8002_HOST}, json=data)
            assert 204 == resp.status_code

        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8001 + '/service1-new-service', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1-new-service'

        param = str(int(time.time()))
        resp = requests.get(SRV_8002 + '/changed-endpoint/%s' % param, headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'var: %s' % param

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_stats(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        param = str(int(time.time()))

        for _ in range(2):
            resp = requests.get(SRV_9000 + '/stats')
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
                resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code

            for _ in range(3):
                resp = requests.get(SRV_8001 + '/service1-second/%s' % param, headers={'Host': SRV_8001_HOST})
                assert 201 == resp.status_code
                assert resp.text == 'service1-second: %s' % param

            for _ in range(2):
                resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = requests.get(SRV_8002 + '/service2-rst', headers={'Host': SRV_8002_HOST})
                except ConnectionError as e:
                    assert str(e).split(',')[1].strip().startswith('ConnectionResetError')
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = requests.get(SRV_8002 + '/service2-fin', headers={'Host': SRV_8002_HOST})
                except ConnectionError as e:
                    assert str(e).split(',')[1].strip().startswith('RemoteDisconnected')
                assert 200 == resp.status_code

            resp = requests.get(SRV_9000 + '/stats')
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

            resp = requests.delete(SRV_9000 + '/stats')
            assert 204 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_stats_service(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        param = str(int(time.time()))

        for _ in range(2):
            resp = requests.get(SRV_8001 + '/__admin/stats', headers={'Host': SRV_8001_HOST})
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
                resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code

            for _ in range(3):
                resp = requests.get(SRV_8001 + '/service1-second/%s' % param, headers={'Host': SRV_8001_HOST})
                assert 201 == resp.status_code
                assert resp.text == 'service1-second: %s' % param

            resp = requests.get(SRV_8001 + '/__admin/stats', headers={'Host': SRV_8001_HOST})
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

            resp = requests.delete(SRV_8001 + '/__admin/stats', headers={'Host': SRV_8001_HOST})
            assert 204 == resp.status_code

        for _ in range(2):
            resp = requests.get(SRV_8002 + '/__admin/stats', headers={'Host': SRV_8002_HOST})
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
                resp = requests.get(SRV_8002 + '/service2', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = requests.get(SRV_8002 + '/service2-rst', headers={'Host': SRV_8002_HOST})
                except ConnectionError as e:
                    assert str(e).split(',')[1].strip().startswith('ConnectionResetError')
                assert 200 == resp.status_code

            for _ in range(2):
                try:
                    resp = requests.get(SRV_8002 + '/service2-fin', headers={'Host': SRV_8002_HOST})
                except ConnectionError as e:
                    assert str(e).split(',')[1].strip().startswith('RemoteDisconnected')
                assert 200 == resp.status_code

            resp = requests.get(SRV_8002 + '/__admin/stats', headers={'Host': SRV_8002_HOST})
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

            resp = requests.delete(SRV_8002 + '/__admin/stats', headers={'Host': SRV_8002_HOST})
            assert 204 == resp.status_code

    @pytest.mark.parametrize(('config, level'), [
        ('configs/json/hbs/management/multiresponse.json', 'global'),
        ('configs/json/hbs/management/multiresponse.json', 'service'),
    ])
    def test_post_reset_iterators(self, config, level):
        self.mock_server_process = run_mock_server(get_config_path(config))

        for _ in range(3):
            for i in range(2):
                resp = requests.get(SRV_8001 + '/service1-multi-response-looped', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = requests.get(SRV_8001 + '/service1-multi-response-nonlooped', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = requests.get(SRV_8001 + '/service1-dataset-inline', headers={'Host': SRV_8001_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'dset: val%d' % (i + 1)

            if level == 'service':
                resp = requests.post(SRV_8001 + '/__admin/reset-iterators', headers={'Host': SRV_8001_HOST})
                assert 204 == resp.status_code

            for i in range(2):
                resp = requests.get(SRV_8002 + '/service2-multi-response-looped', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = requests.get(SRV_8002 + '/service2-multi-response-nonlooped', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'resp%d' % (i + 1)

                resp = requests.get(SRV_8002 + '/service2-dataset-inline', headers={'Host': SRV_8002_HOST})
                assert 200 == resp.status_code
                assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
                assert resp.text == 'dset: val%d' % (i + 1)

            if level == 'service':
                resp = requests.post(SRV_8002 + '/__admin/reset-iterators', headers={'Host': SRV_8002_HOST})
                assert 204 == resp.status_code

            if level == 'global':
                resp = requests.post(SRV_9000 + '/reset-iterators')
                assert 204 == resp.status_code

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/management/config.json',
        'configs/yaml/hbs/management/config.yaml'
    ])
    def test_get_unhandled(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_9000 + '/unhandled')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert data == requests.get(SRV_9000 + '/config').json()

        resp = requests.get(SRV_8001 + '/service1x', headers={'Host': SRV_8001_HOST, 'User-Agent': 'mockintosh-test'})
        assert 404 == resp.status_code

        resp = requests.get(SRV_8001 + '/service1y?a=b&c=d', headers={'Host': SRV_8001_HOST, 'Example-Header': 'Example-Value', 'User-Agent': 'mockintosh-test'})
        assert 404 == resp.status_code

        resp = requests.get(SRV_8002 + '/service2z', headers={'Host': SRV_8002_HOST, 'User-Agent': 'mockintosh-test'})
        assert 404 == resp.status_code

        resp = requests.get(SRV_9000 + '/unhandled')
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'management': {'port': 9000}, 'templatingEngine': 'Handlebars', 'services': [{'name': 'Mock for Service1', 'hostname': 'service1.example.com', 'port': 8001, 'managementRoot': '__admin', 'endpoints': [{'path': '/service1', 'method': 'GET', 'response': 'service1'}, {'path': '/service1-second/{{var}}', 'method': 'GET', 'response': {'status': 201, 'body': 'service1-second: {{var}}'}}, {'path': '/service1x', 'method': 'GET', 'headers': {'User-Agent': 'mockintosh-test', 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive', 'Host': 'service1.example.com'}, 'response': ''}, {'path': '/service1y', 'method': 'GET', 'headers': {'User-Agent': 'mockintosh-test', 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive', 'Host': 'service1.example.com', 'Example-Header': 'Example-Value'}, 'queryString': {'a': 'b', 'c': 'd'}, 'response': ''}]}, {'name': 'Mock for Service2', 'hostname': 'service2.example.com', 'port': 8002, 'managementRoot': '__admin', 'endpoints': [{'path': '/service2', 'method': 'GET', 'response': 'service2'}, {'path': '/service2-rst', 'method': 'GET', 'response': {'status': 'RST', 'body': 'service2-rst'}}, {'path': '/service2-fin', 'method': 'GET', 'response': {'status': 'FIN', 'body': 'service2-fin'}}, {'path': '/service2z', 'method': 'GET', 'headers': {'User-Agent': 'mockintosh-test', 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive', 'Host': 'service2.example.com'}, 'response': ''}]}]}
        assert expected_data == resp.json()

        resp = requests.get(SRV_8001 + '/__admin/unhandled', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'name': 'Mock for Service1', 'hostname': 'service1.example.com', 'port': 8001, 'managementRoot': '__admin', 'endpoints': [{'path': '/service1', 'method': 'GET', 'response': 'service1'}, {'path': '/service1-second/{{var}}', 'method': 'GET', 'response': {'status': 201, 'body': 'service1-second: {{var}}'}}, {'path': '/service1x', 'method': 'GET', 'headers': {'User-Agent': 'mockintosh-test', 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive', 'Host': 'service1.example.com'}, 'response': ''}, {'path': '/service1y', 'method': 'GET', 'headers': {'User-Agent': 'mockintosh-test', 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive', 'Host': 'service1.example.com', 'Example-Header': 'Example-Value'}, 'queryString': {'a': 'b', 'c': 'd'}, 'response': ''}]}
        assert expected_data == resp.json()

        resp = requests.get(SRV_8002 + '/__admin/unhandled', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'
        expected_data = {'name': 'Mock for Service2', 'hostname': 'service2.example.com', 'port': 8002, 'managementRoot': '__admin', 'endpoints': [{'path': '/service2', 'method': 'GET', 'response': 'service2'}, {'path': '/service2-rst', 'method': 'GET', 'response': {'status': 'RST', 'body': 'service2-rst'}}, {'path': '/service2-fin', 'method': 'GET', 'response': {'status': 'FIN', 'body': 'service2-fin'}}, {'path': '/service2z', 'method': 'GET', 'headers': {'User-Agent': 'mockintosh-test', 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive', 'Host': 'service2.example.com'}, 'response': ''}]}
        assert expected_data == resp.json()
