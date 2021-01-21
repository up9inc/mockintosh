#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for request parameters.
"""


class PathParam():

    def __init__(self, name, index):
        self.name = name
        self.index = index


class HeaderParam():

    def __init__(self, key, value):
        self.key = key
        self.value = value


class QueryStringParam():

    def __init__(self, key, value):
        self.key = key
        self.value = value


class BodyParam():

    def __init__(self, key, value):
        self.key = key
        self.value = value
