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
