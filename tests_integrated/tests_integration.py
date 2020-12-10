import logging
import os
import time
import unittest

import requests

SRV1 = os.environ.get('SRV1', 'http://localhost:8001')
SRV2 = os.environ.get('SRV2', 'http://localhost:8002')


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        logging.basicConfig(level=logging.DEBUG)

    def test_basic_connect(self):
        resp = requests.get(SRV1 + '/')
        self.assertEqual(200, resp.status_code)

        # since service :8001 does not specify hostname, it should accept any
        resp = requests.get(SRV1 + '/', headers={'Host': 'someservice.domain'})
        self.assertEqual(200, resp.status_code)

    def test_host_header(self):
        resp = requests.get(SRV2 + '/')
        self.assertEqual(404, resp.status_code)

        resp = requests.get(SRV2 + '/', headers={'Host': 'specified.host:8002'})
        self.assertEqual(200, resp.status_code)

    def test_path_parameters(self):
        param = str(int(time.time()))
        resp = requests.get(SRV1 + '/parameterized1/' + param + '/subval')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("intoVar capture: " + param, resp.text)

        resp = requests.get(SRV1 + '/parameterized1/staticVal/subval')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("static path components have priority", resp.text)

        path = '/parameterized2/prefix-' + str(int(time.time())) + '/subval'
        resp = requests.get(SRV1 + path)
        self.assertEqual(200, resp.status_code)
        self.assertEqual("regex capture: " + path, resp.text)

        path = '/parameterized2/wrongprefix-' + str(int(time.time())) + '/subval'
        resp = requests.get(SRV1 + path)
        self.assertEqual(404, resp.status_code)
