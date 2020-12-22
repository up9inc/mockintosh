import logging
import os
import time
import unittest

import requests

import mockintosh

SRV1 = os.environ.get('SRV1', 'http://localhost:8001')
SRV2 = os.environ.get('SRV2', 'http://localhost:8002')
SRV3 = os.environ.get('SRV2', 'http://localhost:8003')


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        logging.basicConfig(level=logging.DEBUG)
        # test for release version consistency
        ttag = os.getenv("TRAVIS_TAG")
        ver = mockintosh.__version__
        logging.info("Travis tag: %s, src version: %s", ttag, ver)
        assert not ttag or ttag == ver, "Git tag/version mismatch"

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
        self.assertEqual("some-endpoint-id", resp.headers['x-mockintosh-endpoint-id'])

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

        param = str(int(time.time()))
        path = '/parameterized1/prefix2-' + param + '/subval2'
        resp = requests.get(SRV1 + path)
        self.assertEqual(200, resp.status_code)
        self.assertEqual("tricky regex capture: " + param, resp.text)

    def test_query_string(self):
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        path = '/qstr-matching1?param1=constant%%20val&param2=%s&param3=prefix-%s-suffix' % (param2, param3)
        resp = requests.get(SRV1 + path)
        self.assertEqual(202, resp.status_code)
        self.assertEqual("qstr match 1: constant val " + param3 + ' ' + param2, resp.text)
        self.assertEqual("application/x-my-own", resp.headers.get("content-type"))
        self.assertEqual("%s prefix-%s-suffix" % (param2, param3), resp.headers.get("param2"))
        self.assertEqual("overridden", resp.headers.get("global-hdr1"))
        self.assertEqual("globalval2", resp.headers.get("global-hdr2"))

        path = '/qstr-matching1?param1=constantval&param2=%s&param3=prefix-%s-suffix' % (param2, param3)
        resp = requests.get(SRV1 + path)
        self.assertEqual(404, resp.status_code)

        path = '/qstr-matching1?param1=constant%%20val&param22=%s&param3=prefix-%s-suffix' % (param2, param3)
        resp = requests.get(SRV1 + path)
        self.assertEqual(404, resp.status_code)

        path = '/qstr-matching1?param1=constant%%20val&param2=%s&param3=prefix-%s-sufix' % (param2, param3)
        resp = requests.get(SRV1 + path)
        self.assertEqual(404, resp.status_code)

    def test_headers(self):
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        path = '/header-matching1'
        resp = requests.get(SRV1 + path,
                            headers={"hdr1": "constant val", "hdr2": param2, "hdr3": "prefix-%s-suffix" % param3})
        self.assertEqual(201, resp.status_code)
        self.assertEqual(param2, resp.cookies['name1'])
        self.assertEqual("prefix-" + param3 + "-suffix", resp.cookies['name2'])

        resp = requests.get(SRV1 + path,
                            headers={"hdr1": "constant", "hdr2": param2, "hdr3": "prefix-%s-suffix" % param3})
        self.assertEqual(404, resp.status_code)

        resp = requests.get(SRV1 + path,
                            headers={"hdr1": "constant val", "hdr2": param2, "hdr3": "prefics-%s-suffix" % param3})
        self.assertEqual(404, resp.status_code)

        resp = requests.get(SRV1 + path,
                            headers={"hdr4": "another header"})
        self.assertEqual(200, resp.status_code)
        self.assertEqual("alternative header", resp.text)

    def test_body_jsonschema(self):
        path = '/body-jsonschema1'
        resp = requests.post(SRV1 + path, json={"somekey": "valid"})
        self.assertEqual(200, resp.status_code)

        path = '/body-jsonschema1'
        resp = requests.post(SRV1 + path, json={"somekey2": "invalid"})
        self.assertEqual(404, resp.status_code)

    def test_status_templated(self):
        path = '/status-template1'
        resp = requests.get(SRV1 + path + "?rc=303")
        self.assertEqual(303, resp.status_code)

    def test_interceptor(self):
        path = '/interceptor-modified'
        resp = requests.get(SRV3 + path)
        self.assertEqual(202, resp.status_code)
        self.assertEqual("intercepted", resp.text)
        self.assertEqual("some-i-val", resp.headers.get("someheader"))

        with open("tests_integrated/server.log") as fp:
            self.assertTrue(any('Processed intercepted request' in line for line in fp))
