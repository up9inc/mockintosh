#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests mock server's features.
"""

import os
import random
import time

import pytest
import requests

from utilities import tcping, run_mock_server, get_config_path, nostdout, nostderr

configs = [
    'configs/json/hbs/common/config.json',
    'configs/json/j2/common/config.json',
    'configs/yaml/hbs/common/config.yaml',
    'configs/yaml/j2/common/config.yaml'
]

SRV_8001 = os.environ.get('SRV1', 'http://localhost:8001')
SRV_8002 = os.environ.get('SRV2', 'http://localhost:8002')

SRV_8001_HOST = 'service1.example.com'
SRV_8002_HOST = 'service2.example.com'


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

    def test_pipe_stdin(self):
        config = 'configs/json/hbs/common/config.json'
        with open(get_config_path(config), 'r') as file:
            self.mock_server_process = run_mock_server(stdin=file)
            TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_debug(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--debug')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_quiet(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--quiet')
        TestCommon.test_users(TestCommon, config)

    @pytest.mark.parametrize(('config'), configs)
    def test_verbose(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config), '--verbose')
        TestCommon.test_users(TestCommon, config)


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
        if 'j2' in config:
            assert self.mock_server_process.is_alive() is False
        else:
            resp = requests.get(SRV_8001 + '/%s' % var, headers={'Host': SRV_8001_HOST})
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
        if 'j2' in config:
            assert 500 == resp.status_code
        else:
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/no_use_templating_no_templating_engine_in_response.json',
        'configs/json/j2/core/no_use_templating_no_templating_engine_in_response.json',
        'configs/yaml/hbs/core/no_use_templating_no_templating_engine_in_response.yaml',
        'configs/yaml/j2/core/no_use_templating_no_templating_engine_in_response.yaml'
    ])
    def test_no_use_templating_no_templating_engine_in_response_should_default_to_handlebars(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})
        if 'j2' in config:
            assert 500 == resp.status_code
        else:
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

    @pytest.mark.parametrize(('config'), [
        'configs/json/hbs/core/use_templating_false_in_response.json',
        'configs/json/j2/core/use_templating_false_in_response.json',
        'configs/yaml/hbs/core/use_templating_false_in_response.yaml',
        'configs/yaml/j2/core/use_templating_false_in_response.yaml'
    ])
    def test_use_templating_false_should_not_render(self, config):
        self.mock_server_process = run_mock_server(get_config_path(config))
        resp = requests.get(SRV_8001 + '/', headers={'Host': SRV_8001_HOST})
        if 'json' in config and 'hbs' in config:
            assert 500 == resp.status_code
        else:
            assert 200 == resp.status_code
            assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

            data = resp.json()
            if 'j2' in config:
                assert data['hello'] == "{{ fake.first_name() }}"
            else:
                assert data['hello'] == "{{ fake \"first_name\" }}"

    def test_multiple_services_on_same_port(self):
        config = 'configs/json/hbs/core/multiple_services_on_same_port.json'
        self.mock_server_process = run_mock_server(get_config_path(config))

        resp = requests.get(SRV_8001 + '/service1', headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service1'

        resp = requests.get(SRV_8001 + '/service2', headers={'Host': SRV_8002_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'text/html; charset=UTF-8'
        assert resp.text == 'service2'

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
