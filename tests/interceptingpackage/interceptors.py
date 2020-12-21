#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains dummy interceptors for testing.
"""

from mockintosh import Request, Response


def dummy1(req: Request, resp: Response):
    resp.status_code = 414


def dummy2(req: Request, resp: Response):
    resp.status_code = 417
