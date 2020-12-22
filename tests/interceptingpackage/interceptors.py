#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains dummy interceptors for testing.
"""

import logging

from mockintosh import Request, Response


def dummy1(req: Request, resp: Response):
    resp.status = 414


def dummy2(req: Request, resp: Response):
    resp.status = 417


def not_existing_path(req: Request, resp: Response):
    if req.path == '/interceptor-modified':
        # should allow reading and modifying response status code, headers, body
        resp.status = 201
        resp.headers['someheader'] = 'some-i-val'
        resp.body = 'intercepted'


def intercept_logging(req: Request, resp: Response):
    logging.info("Processed intercepted request: %r, produced response: %r", req, resp)


def request_object(req: Request, resp: Response):
    if req.path == '/request1':
        assert req.version == 'HTTP/1.1'
        assert req.remoteIp == '127.0.0.1'
        assert req.protocol == 'http'
        assert req.host == 'localhost:8003'
        assert req.hostName == 'localhost'
        assert req.uri == '/request1?a=hello%20world&b=3'
        assert req.method == 'GET'
        assert req.path == '/request1'
        assert req.headers['Host'] == 'localhost:8003'
        assert req.headers['Accept'] == '*/*'
        assert req.headers['Connection'] == 'keep-alive'
        assert req.headers['Cache-Control'] == 'no-cache'
        assert req.queryString['a'] == 'hello world'
        assert req.queryString['b'] == '3'
        assert req.body == 'hello world'
    elif req.path == '/request2':
        assert req.method == 'POST'
        assert req.formData['param1'] == 'value1'
        assert req.formData['param2'] == 'value2'

    resp.status = 200
