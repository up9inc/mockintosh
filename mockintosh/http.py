#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains HTTP related classes.
"""

from collections import OrderedDict
from typing import (
    Dict,
    Union
)


class HttpBody:

    def __init__(
        self,
        text,
        urlencoded,
        multipart
    ):
        self.text = text
        self.urlencoded = urlencoded
        self.multipart = multipart


class HttpEndpoint:

    def __init__(
        self,
        orig_path: str,
        params: dict,
        context: OrderedDict,
        performance_profile: str,
        priority: int,
        path: str,
        query_string: Dict[str, str],
        headers: Dict[str, str],
        body: Union[HttpBody, None]
    ):
        self.orig_path = orig_path
        self.params = params
        self.context = context
        self.performance_profile = performance_profile
        self.priority = priority
        self.path = path
        self.query_string = query_string
        self.headers = headers
        self.body = body


class HttpService:

    def __init__(self):
        self.endpoints = []

    def add_endpoint(self, endpoint: HttpEndpoint):
        self.endpoints.append(endpoint)
