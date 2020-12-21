#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains dummy interceptors for testing.
"""

import logging

from mockintosh import Request, Response


def dummy1(req: Request, resp: Response):
    resp.status_code = 414


def dummy2(req: Request, resp: Response):
    resp.status_code = 417


def not_existing_path(req: Request, resp: Response):
    if req.path == '/interceptor-modified':
        # should allow reading and modifying response status code, headers, body
        resp.force_update = True
        resp.status_code = 201
        resp.header['someheader'] = 'some-i-val'
        resp.body = 'intercepted'


def intercept_logging(req: Request, resp: Response):
    logging.info("Processed intercepted request: %r, produced response: %r", req, resp)
