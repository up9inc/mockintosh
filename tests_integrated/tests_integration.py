import logging
import os
import re
import time
import unittest

import requests

import mockintosh

SRV1 = os.environ.get('SRV1', 'http://localhost:8001')
SRV2 = os.environ.get('SRV2', 'http://localhost:8002')
SRV3 = os.environ.get('SRV3', 'https://localhost:8003')
SRV4 = os.environ.get('SRV4', 'http://localhost:8004')
SRV5 = os.environ.get('SRV5', 'https://localhost:8005')


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

        resp = requests.get(SRV1 + '/response-not-required')
        self.assertEqual(200, resp.status_code)

        # since service :8001 does not specify hostname, it should accept any
        resp = requests.get(SRV1 + '/', headers={'Host': 'someservice.domain'})
        self.assertEqual(200, resp.status_code)

        resp = requests.get(SRV1 + '/404-img.png')
        self.assertEqual(404, resp.status_code)
        self.assertEqual(b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A", resp.content[:8])
        self.assertEqual("image/png", resp.headers.get("content-type"))

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
        self.assertEqual(400, resp.status_code)

        path = '/qstr-matching1?param1=constant%%20val&param22=%s&param3=prefix-%s-suffix' % (param2, param3)
        resp = requests.get(SRV1 + path)
        self.assertEqual(400, resp.status_code)

        path = '/qstr-matching1?param1=constant%%20val&param2=%s&param3=prefix-%s-sufix' % (param2, param3)
        resp = requests.get(SRV1 + path)
        self.assertEqual(400, resp.status_code)

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
        self.assertEqual(400, resp.status_code)

        resp = requests.get(SRV1 + path,
                            headers={"hdr1": "constant val", "hdr2": param2, "hdr3": "prefics-%s-suffix" % param3})
        self.assertEqual(400, resp.status_code)

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
        self.assertEqual(400, resp.status_code)

    def test_status_templated(self):
        path = '/status-template1'
        resp = requests.get(SRV1 + path + "?rc=303")
        self.assertEqual(303, resp.status_code)

    def test_interceptor(self):
        path = '/interceptor-modified'
        resp = requests.get(SRV3 + path, verify=False)
        self.assertEqual(202, resp.status_code)
        self.assertEqual("intercepted", resp.text)
        self.assertEqual("some-i-val", resp.headers.get("someheader"))

        with open("tests_integrated/server.log") as fp:
            self.assertTrue(any('Processed intercepted request' in line for line in fp))

    def test_files_locating(self):
        resp = requests.get(SRV4 + '/cors2')
        self.assertEqual(200, resp.status_code)
        self.assertIn("<title>CORS Example</title>", resp.text)

        resp = requests.get(SRV1 + '/parameterized3/image.png')
        self.assertEqual(200, resp.status_code)

        resp = requests.get(SRV1 + '/insecure-configuration1')
        self.assertEqual(403, resp.status_code)

        resp = requests.get(SRV1 + '/insecure-configuration2')
        self.assertEqual(403, resp.status_code)

    def test_cors(self):
        hdr = {
            "origin": "http://someorigin",
            "Access-Control-Request-Headers": "authorization, x-api-key"
        }
        resp = requests.options(SRV1 + '/cors-request', headers=hdr)
        self.assertEqual(204, resp.status_code)
        self.assertEqual(hdr['origin'], resp.headers.get("access-control-allow-origin"))
        self.assertEqual(hdr['Access-Control-Request-Headers'], resp.headers.get("Access-Control-Allow-Headers"))
        self.assertEqual("DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
                         resp.headers.get("access-control-allow-methods"))

        resp = requests.post(SRV1 + '/cors-request', json={}, headers=hdr)
        self.assertEqual(hdr['origin'], resp.headers.get("access-control-allow-origin"))
        self.assertEqual(hdr['Access-Control-Request-Headers'], resp.headers.get("Access-Control-Allow-Headers"))
        self.assertEqual("DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
                         resp.headers.get("access-control-allow-methods"))
        self.assertEqual(201, resp.status_code)

        resp = requests.options(SRV1 + '/cors-request-overridden', headers=hdr)
        self.assertEqual(401, resp.status_code)

        resp = requests.options(SRV1 + '/nonexistent', headers=hdr)
        self.assertEqual(404, resp.status_code)

        resp = requests.options(SRV1 + '/cors-request')
        self.assertEqual(404, resp.status_code)  # maybe it should be 400

    def test_multiresponse(self):
        resp = requests.get(SRV1 + '/multi-response-looped')
        self.assertEqual(200, resp.status_code)
        self.assertIn("<title>CORS Example</title>", resp.text)

        resp = requests.get(SRV1 + '/multi-response-looped')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("image/png", resp.headers.get("content-type"))

        resp = requests.get(SRV1 + '/multi-response-looped')
        self.assertEqual(200, resp.status_code)
        self.assertIn("just some text", resp.text)

        resp = requests.get(SRV1 + '/multi-response-looped')
        self.assertEqual(200, resp.status_code)
        self.assertIn("<title>CORS Example</title>", resp.text)

    def test_multiresponse_noloop(self):
        resp = requests.get(SRV1 + '/multi-response-nonlooped')
        self.assertEqual(200, resp.status_code)
        self.assertIn("resp1", resp.text)

        resp = requests.get(SRV1 + '/multi-response-nonlooped')
        self.assertEqual(200, resp.status_code)
        self.assertIn("resp2", resp.text)

        resp = requests.get(SRV1 + '/multi-response-nonlooped')
        self.assertEqual(410, resp.status_code)

    def test_dataset(self):
        resp = requests.get(SRV1 + '/dataset-inline')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("dset: val1", resp.text)

        resp = requests.get(SRV1 + '/dataset-inline')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("dset: val2", resp.text)

        resp = requests.get(SRV1 + '/dataset-inline')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("dset: val1", resp.text)

    def test_dataset_fromfile(self):
        resp = requests.get(SRV1 + '/dataset-fromfile')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("dset: val3", resp.text)

        resp = requests.get(SRV1 + '/dataset-fromfile')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("dset: val4", resp.text)

        resp = requests.get(SRV1 + '/dataset-fromfile')
        self.assertEqual(410, resp.status_code)

    def test_ssl(self):
        resp = requests.get(SRV5 + '/', verify=False)
        self.assertEqual(200, resp.status_code)

    def test_templating_random(self):
        resp = requests.get(SRV1 + '/templating-random')
        self.assertEqual(200, resp.status_code)
        resp = resp.text

        rint, resp = resp.split("\n", 1)
        self.assertTrue(10 <= int(rint) <= 20)

        rfloat, resp = resp.split("\n", 1)
        self.assertTrue(-0.5 <= float(rfloat) <= 20.7)
        self.assertTrue(1 <= len(rfloat.split('.')[1]) <= 3)

        alphanum, resp = resp.split("\n", 1)
        self.assertEqual(5, len(alphanum))
        self.assertTrue(alphanum.isalnum())

        fhex, resp = resp.split("\n", 1)
        self.assertEqual(16, len(fhex))
        self.assertTrue(re.match("[0-9a-f]+", fhex))

        fuuid, resp = resp.split("\n", 1)
        self.assertTrue(re.match(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', fuuid))

        self.assertEqual(5, len(resp))  # random ascii

    def test_body_regex(self):
        resp = requests.post(SRV1 + '/body-regex', data="somewhere 1-required-2 is present")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("body regex matched: 1 2", resp.text)

        resp = requests.post(SRV1 + '/body-regex', data="somewhere a-required-b is not present")
        self.assertEqual(400, resp.status_code)

    def test_body_jsonpath(self):
        resp = requests.post(SRV1 + '/body-jsonpath-tpl', json={"key": "val", "key2": 123})
        self.assertEqual(200, resp.status_code)
        self.assertEqual('body jsonpath matched: val 123', resp.text)

        resp = requests.post(SRV1 + '/body-jsonpath-tpl', json={"key": None})
        self.assertEqual(200, resp.status_code)
        self.assertEqual('body jsonpath matched: null ', resp.text)

        resp = requests.post(SRV1 + '/body-jsonpath-tpl', data="not json")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("body jsonpath matched: {{jsonPath request.json '$.key'}} {{jsonPath request.json '$.key2'}}",
                         resp.text)

    def test_counter(self):
        resp = requests.get(SRV1 + '/counter1')
        self.assertEqual("variant1: 1 1", resp.text)

        resp = requests.get(SRV1 + '/counter1')
        self.assertEqual("variant2: 2 1", resp.text)

        resp = requests.get(SRV1 + '/counter1')
        self.assertEqual("variant1: 3 2", resp.text)

        resp = requests.get(SRV1 + '/counter1')
        self.assertEqual("variant2: 4 2", resp.text)

        resp = requests.get(SRV1 + '/counter2')
        self.assertEqual("variant3: 5 3 3", resp.headers.get('X-Counter'))

        resp = requests.get(SRV1 + '/counter3')
        self.assertEqual("variant3: 5 3 3", resp.text)

    def test_unprocessed_templates(self):
        resp = requests.get(SRV1 + '/undefined-templates')
        self.assertEqual("here goes {{unknownUndefined}} var", resp.text)
        self.assertEqual("also {{random.intt 10 20}} can happen", resp.headers.get('X-header'))
