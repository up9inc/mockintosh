#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for request parameters.
"""


class PathParam(dict):

    def __init__(self, name, index):
        dict.__init__(self, name=name, index=index)


class HeaderParam(dict):

    def __init__(self, key, value):
        dict.__init__(self, key=key, value=value)


class QueryStringParam(dict):

    def __init__(self, key, value):
        dict.__init__(self, key=key, value=value)


class BodyParam(dict):

    def __init__(self, key, value):
        dict.__init__(self, key=key, value=value)
