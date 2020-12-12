#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: End-to-end tests related to mock server's itself.
"""

import os

import pytest
import requests

from utilities import tcping, run_mock_server

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
        self.mock_server_process = run_mock_server(config)

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
        assert isinstance(data['users'][0]['friends'], list) or data['users'][0]['friends'] == None

    def test_user(self, config):
        user_id = 3
        resp = requests.get(SRV_8001 + '/users/%s' % user_id, headers={'Host': SRV_8001_HOST})
        assert 200 == resp.status_code
        assert resp.headers['Content-Type'] == 'application/json; charset=UTF-8'

        data = resp.json()
        assert isinstance(data['id'], int)
        assert data['firstName']
        assert isinstance(data['firstName'], str)
        assert data['lastName']
        assert isinstance(data['lastName'], str)
        assert isinstance(data['friends'], list) or data['friends'] == None

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
