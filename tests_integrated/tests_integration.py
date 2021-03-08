import logging
import os
import re
import time
import unittest
from collections import Counter
from datetime import datetime, timedelta

import requests
import yaml
from jsonschema.validators import validate

import mockintosh

MGMT = os.environ.get('MGMT', 'https://localhost:8000')
SRV1 = os.environ.get('SRV1', 'http://localhost:8001')
SRV2 = os.environ.get('SRV2', 'http://localhost:8002')
SRV3 = os.environ.get('SRV3', 'https://localhost:8003')
SRV4 = os.environ.get('SRV4', 'http://localhost:8004')
SRV5 = os.environ.get('SRV5', 'https://localhost:8005')
SRV6 = os.environ.get('SRV6', 'http://localhost:8006')


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

        resp = requests.get(SRV2 + '/', headers={'Host': 'another.host:8002'})
        self.assertEqual(200, resp.status_code)
        self.assertEqual("some-endpoint-id2", resp.headers['x-mockintosh-endpoint-id'])

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

    def test_urlencoded(self):
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        path = '/body-urlencoded'
        resp = requests.post(SRV1 + path, data={
            "param1": "constant val",
            "param2": param2,
            "param3": "prefix-%s-suffix" % param3
        })
        resp.raise_for_status()
        self.assertEqual("urlencoded match: constant val " + param3 + ' ' + param2, resp.text)

        resp = requests.post(SRV1 + path, data={
            "param1": "constant val",
            "param2": param2,
            "param3": "prefix-%s-suffixz" % param3
        })
        self.assertEqual(400, resp.status_code)

    def test_multipart(self):
        param2 = str(int(time.time()))
        param3 = str(int(time.time() / 2))
        path = '/body-multipart'
        resp = requests.post(SRV1 + path, files={
            "param1": "constant val",
            "param2": param2,
            "param3": "prefix-%s-suffix" % param3
        })
        resp.raise_for_status()
        self.assertEqual("multipart match: constant val " + param3 + ' ' + param2, resp.text)

        resp = requests.post(SRV1 + path, files={
            "param1": "constant val",
            "param2": param2,
            "param3": "prefix-%s-suffixz" % param3
        })
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

        resp = requests.post(MGMT + '/reset-iterators', verify=False)
        resp.raise_for_status()

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

        resp = requests.post(SRV1 + '/__admin/reset-iterators')
        resp.raise_for_status()

        resp = requests.get(SRV1 + '/multi-response-nonlooped')
        self.assertEqual(200, resp.status_code)
        self.assertIn("resp1", resp.text)

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

        resp = requests.post(SRV1 + '/__admin/reset-iterators')
        resp.raise_for_status()

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

        resp = requests.post(MGMT + '/reset-iterators', verify=False)
        resp.raise_for_status()

        resp = requests.get(SRV1 + '/dataset-fromfile')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("dset: val3", resp.text)

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

    def test_templating_date(self):
        resp = requests.get(SRV1 + '/date-tpl')
        now = time.time()  # Too late to get `time.time()` after that
        utcnow = datetime.utcnow()  # Too late to get `datetime.utcnow()` after that

        self.assertEqual(200, resp.status_code)
        resp = resp.text
        logging.info("Resp: %s", resp)

        # {date.timestamp}}
        chunk, resp = resp.split(" ", 1)
        self.assertTrue(abs(now - int(chunk)) < 1)
        self.assertNotIn('.', chunk)

        # {{date.timestamp -10}}
        chunk, resp = resp.split(" ", 1)
        self.assertTrue(abs((now - 10) - int(chunk)) < 1)
        self.assertNotIn('.', chunk)

        #  {{date.timestamp 10}}
        chunk, resp = resp.split(" ", 1)
        self.assertTrue(abs((now + 10) - int(chunk)) < 1)
        self.assertNotIn('.', chunk)

        #  {{date.ftimestamp}}
        chunk, resp = resp.split(" ", 1)
        self.assertTrue(abs(now - float(chunk)) < 1)
        self.assertIn('.', chunk)
        self.assertTrue(len(chunk.split('.')[1]) <= 3)

        #  {{date.ftimestamp 10 5}}
        chunk, resp = resp.split(" ", 1)
        self.assertTrue(abs((now + 10) - float(chunk)) < 1)
        self.assertIn('.', chunk)
        self.assertTrue(len(chunk.split('.')[1]) <= 5)

        #  {{date.date}}
        chunk, resp = resp.split(" ", 1)
        pdate = datetime.strptime(chunk, '%Y-%m-%dT%H:%M:%S.%f')
        delta = utcnow - pdate
        self.assertTrue(delta < timedelta(days=2))

        #  {{date.date '%Y-%m-%d %H:%M:%S'}}
        chunk1, resp = resp.split(" ", 1)
        chunk2, resp = resp.split(" ", 1)
        chunk = ' '.join((chunk1, chunk2))
        pdate = datetime.strptime(chunk, '%Y-%m-%d %H:%M:%S')
        delta = utcnow - pdate
        self.assertTrue(delta < timedelta(days=2))

        #  {{date.date '%Y-%m-%d' 86400}}
        pdate = datetime.strptime(resp, '%Y-%m-%d %H')
        delta = pdate - utcnow
        self.assertTrue(delta > timedelta(seconds=82800))

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

    def test_conn_status(self):
        with self.assertRaises(requests.exceptions.ConnectionError):
            requests.get(SRV1 + '/conn-rst')

        with self.assertRaises(requests.exceptions.ConnectionError):
            requests.get(SRV1 + '/conn-close')

    def test_management_global(self):
        resp = requests.get(MGMT + '/', verify=False)
        self.assertEqual(200, resp.status_code)  # should return a HTML page

        resp = requests.get(MGMT + '/config', verify=False)
        self.assertEqual(200, resp.status_code)

        resp = requests.get(SRV1 + '/__admin/config?format=yaml')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("application/x-yaml", resp.headers.get("content-type"))

        resp = requests.get(SRV1 + '/__admin/config?format=yaml')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("application/x-yaml", resp.headers.get("content-type"))

    def test_management_service(self):
        resp = requests.get(SRV1 + '/__admin/')
        self.assertEqual(200, resp.status_code)  # should return a HTML page

        resp = requests.get(SRV1 + '/__admin/config')
        self.assertEqual(200, resp.status_code)

        resp = requests.get(SRV1 + '/__admin/config?format=yaml')
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.text.startswith("name:"))

    def test_management_autotest_usecase(self):
        resp = requests.get(SRV6 + '/sub/__admin/config')
        self.assertEqual(200, resp.status_code)
        conf = resp.json()

        endps1 = [{
            "path": "/endp1",
            "response": ["1", "2", "3"]
        }]
        conf['endpoints'] = endps1
        resp = requests.post(SRV6 + '/sub/__admin/config', json=conf)
        self.assertEqual(204, resp.status_code)

        resp = requests.get(SRV6 + '/endp1')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("1", resp.text)

        resp = requests.get(SRV6 + '/endp1')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("2", resp.text)

        endps1 = [{
            "path": "/endp1",
            "response": ["11", "22", "33"]
        }]
        conf['endpoints'] = endps1
        resp = requests.post(SRV6 + '/sub/__admin/config', data=yaml.dump(conf),
                             headers={"Content-Type": "application/x-yaml"})
        self.assertEqual(204, resp.status_code)

        resp = requests.get(SRV6 + '/endp1')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("11", resp.text)

        resp = requests.get(SRV6 + '/endp1')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("22", resp.text)

        endps2 = [{
            "path": "/endp2",
            "response": "simple"
        }]
        conf['endpoints'] = endps2
        resp = requests.post(SRV6 + '/sub/__admin/config', json=conf)
        self.assertEqual(204, resp.status_code)

        resp = requests.get(SRV6 + '/endp1')
        self.assertEqual(404, resp.status_code)

        resp = requests.get(SRV6 + '/endp2')
        self.assertEqual(200, resp.status_code)
        self.assertEqual("simple", resp.text)

    def test_1_stats(self):
        requests.get(SRV1 + '/')  # to trigger counter

        resp = requests.get(MGMT + '/stats', verify=False)
        self.assertEqual(200, resp.status_code)
        global_stats = resp.json()

        resp = requests.get(SRV1 + '/__admin/stats')
        self.assertEqual(200, resp.status_code)
        srv_stats = resp.json()
        self.assertGreater(srv_stats['request_counter'], 0)

        self.assertEqual(srv_stats, global_stats['services'][0])
        requests.get(SRV1 + '/')  # to trigger counter
        resp = requests.get(SRV1 + '/__admin/stats')
        srv_stats = resp.json()
        self.assertNotEqual(srv_stats, global_stats['services'][0])

        resp = requests.delete(SRV1 + '/__admin/stats')
        resp.raise_for_status()
        resp = requests.get(SRV1 + '/__admin/stats')
        srv_stats = resp.json()
        self.assertEqual(0, srv_stats['request_counter'])

    def test_unhandled(self):
        path = '/unhandled-%s' % time.time()
        resp = requests.get(SRV1 + path, headers={"hdr1": "val1", "hdr2": "val2", "hdr3": "val3"})
        self.assertEqual(404, resp.status_code)

        resp = requests.get(MGMT + '/unhandled?format=yaml', verify=False)
        resp.raise_for_status()
        self.assertTrue(resp.text.startswith('services:'))

        resp = requests.get(MGMT + '/unhandled', verify=False)
        resp.raise_for_status()
        self.assertEqual('{', resp.text[0])
        config = resp.json()
        self.assertFalse([x for x in config['services'] if not x['endpoints']])

        for endp in config['services'][0]['endpoints']:
            if endp['path'] == path:
                hdrs = [x.lower() for x in endp.get('headers', {}).keys()]
                self.assertNotIn('host', hdrs)
                self.assertNotIn('user-agent', hdrs)
                self.assertNotIn('connection', hdrs)
                self.assertIn('hdr1', hdrs)
                self.assertIn('hdr2', hdrs)
                self.assertIn('hdr3', hdrs)
                break
        else:
            self.fail("Did not find endpoint")

        resp = requests.get(SRV1 + path, headers={"hdr1": "val1", "hdr2": "val22"})
        self.assertEqual(404, resp.status_code)

        resp = requests.get(SRV1 + '/__admin/unhandled')
        resp.raise_for_status()
        config = resp.json()
        for endp in config['services'][0]['endpoints']:
            if endp['path'] == path:
                hdrs = [x.lower() for x in endp.get('headers', {}).keys()]
                self.assertIn('hdr1', hdrs)
                self.assertNotIn('hdr2', hdrs)
                self.assertNotIn('hdr3', hdrs)
                break
        else:
            self.fail("Did not find endpoint")

        resp = requests.get(SRV1 + path, headers={"hdr1": "val1", "hdr2": "val2", "hdr3": "val3"})
        self.assertEqual(404, resp.status_code)

        resp = requests.get(SRV1 + '/__admin/unhandled')
        resp.raise_for_status()
        config = resp.json()
        for endp in config['services'][0]['endpoints']:
            if endp['path'] == path:
                hdrs = [x.lower() for x in endp.get('headers', {}).keys()]
                self.assertIn('hdr1', hdrs)
                self.assertNotIn('hdr2', hdrs)
                self.assertNotIn('hdr3', hdrs)
                break
        else:
            self.fail("Did not find endpoint")

    def test_oas(self):
        resp = requests.get(MGMT + '/oas', verify=False)
        resp.raise_for_status()
        docs = resp.json()
        self.assertEqual(7, len(docs['documents']))
        self.assertEqual('http://localhost:8006', docs['documents'][6]['servers'][0]['url'])

        resp = requests.get(SRV1 + '/__admin/oas')
        resp.raise_for_status()
        oas = resp.json()
        self.assertGreater(len(oas['paths']), 30)
        self.assertEqual(3, len(oas['paths']['/qstr-matching1']['get']['parameters']))
        self.assertEqual(3, len(oas['paths']['/header-matching1']['get']['parameters']))

        resp = requests.get(SRV6 + '/sub/__admin/oas')
        resp.raise_for_status()
        oas = resp.json()
        self.assertEqual('http://localhost:8006', oas['servers'][0]['url'])

    def test_perf_profiles(self):
        accum = 0
        for _ in range(10):
            start = time.perf_counter()
            resp = requests.get(SRV1 + '/')
            resp.raise_for_status()
            accum += time.perf_counter() - start
        self.assertGreater(accum / 10, 0.4)

        stats = Counter()
        for _ in range(100):
            try:
                resp = requests.get(SRV1 + '/perf-profile-faults')
                stats[resp.status_code] += 1
            except BaseException:
                stats['RST'] += 1

        self.assertGreater(stats[200], stats['RST'])
        self.assertGreater(stats[200], stats[503])

    def test_tagged_responses(self):
        resp = requests.post(SRV1 + '/__admin/reset-iterators')
        resp.raise_for_status()

        # no tag set - only untagged responses
        resp = requests.post(SRV1 + '/__admin/tag', data="")
        resp.raise_for_status()

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.1", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.2", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.3", resp.text)

        # first tag set - "first" + untagged responses
        resp = requests.post(SRV1 + '/__admin/tag', data="first")
        resp.raise_for_status()

        resp = requests.get(SRV1 + '/__admin/tag')
        resp.raise_for_status()
        self.assertEqual("first", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.1", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("1.1", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("1.2", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.2", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.3", resp.text)

        # first tag set - "second" + untagged responses
        resp = requests.post(SRV1 + '/__admin/tag', data="second")
        resp.raise_for_status()

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.1", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("2.1", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.2", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("2.2", resp.text)

        resp = requests.get(SRV1 + '/tagged')
        self.assertEqual("3.3", resp.text)

        # case of no valid response
        resp = requests.get(SRV1 + '/tagged-confusing')
        self.assertEqual(410, resp.status_code)

    def test_resources_global(self):
        resp = requests.get(MGMT + '/resources', verify=False)
        resp.raise_for_status()
        files = resp.json()['files']
        logging.info("Files: %s", files)
        self.assertIn('subdir/empty_schema.json', files)
        self.assertIn('cors.html', files)
        self.assertIn('subdir/image.png', files)
        self.assertNotIn('/etc/hosts', files)
        self.assertEqual(len(files), len(set(files)))

        for file in files:  # test that all files reported can be read and written
            resp = requests.get(MGMT + '/resources?path=%s' % file, verify=False)
            resp.raise_for_status()

            resp = requests.post(MGMT + '/resources', files={file: resp.content}, verify=False)
            resp.raise_for_status()

        resp = requests.get(MGMT + '/resources?path=cors.html', verify=False)
        resp.raise_for_status()
        self.assertIn('<html ', resp.text)
        orig_content = resp.text

        resp = requests.delete(MGMT + '/resources?path=cors.html', verify=False)
        resp.raise_for_status()
        with self.assertRaises(requests.exceptions.HTTPError):
            resp = requests.get(MGMT + '/resources?path=cors.html', verify=False)
            resp.raise_for_status()

        marker = "<!-- %s -->" % time.time()
        resp = requests.post(MGMT + '/resources', files={"cors.html": orig_content + marker}, verify=False)
        resp.raise_for_status()

        resp = requests.get(MGMT + '/resources?path=cors.html', verify=False)
        resp.raise_for_status()
        self.assertTrue(resp.text.endswith(marker))

        with self.assertRaises(requests.exceptions.HTTPError):
            resp = requests.get(MGMT + '/resources?path=/etc/hosts', verify=False)
            resp.raise_for_status()

        with self.assertRaises(requests.exceptions.HTTPError):
            resp = requests.get(MGMT + '/resources?path=__init__.py', verify=False)
            resp.raise_for_status()

    def test_resources_service(self):
        resp = requests.get(SRV1 + '/__admin/resources', verify=False)
        resp.raise_for_status()
        files = resp.json()['files']
        self.assertIn('cors.html', files)

    def test_traffic_log(self):
        self.test_urlencoded()
        self.test_multipart()

        resp = requests.get(MGMT + '/traffic-log', verify=False)
        resp.raise_for_status()
        json = resp.json()
        validate(json, {"$schema": "https://raw.githubusercontent.com/undera/har-jsonschema/master/har-schema.json"})
