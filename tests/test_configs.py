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

SRV1 = os.environ.get('SRV1', 'http://localhost:8001')
SRV2 = os.environ.get('SRV2', 'http://localhost:8002')


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
        resp = requests.get(SRV1 + '/users', headers={'Host': 'service1.example.com'})
        assert 200 == resp.status_code
