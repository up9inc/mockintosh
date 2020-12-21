#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains dummy interceptors for testing.
"""


def dummy1(request_handler):
    request_handler.set_status(414)


def dummy2(request_handler):
    request_handler.set_status(417)
