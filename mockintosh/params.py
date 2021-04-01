#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for request parameters.
"""


class ParamBase():

    def __init__(self, key, value):
        self.key = key
        self.value = value


class HeaderParam(ParamBase):

    def __init__(self, key, value):
        super().__init__(key, value)


class QueryStringParam(ParamBase):

    def __init__(self, key, value):
        super().__init__(key, value)


class BodyTextParam(ParamBase):

    def __init__(self, key, value):
        super().__init__(key, value)


class BodyUrlencodedParam(ParamBase):

    def __init__(self, key, value):
        super().__init__(key, value)


class BodyMultipartParam(ParamBase):

    def __init__(self, key, value):
        super().__init__(key, value)
