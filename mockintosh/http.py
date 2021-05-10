#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains HTTP related classes.
"""

from os import environ

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
        comment: Union[str, None],
        method: Union[str, None],
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
        self.comment = comment
        self.method = method
        self.query_string = query_string
        self.headers = headers
        self.body = body


class HttpService:

    def __init__(
        self,
        port: int,
        name: Union[str, None],
        hostname: Union[str, None],
        ssl: bool,
        ssl_cert_file: Union[str, None],
        ssl_key_file: Union[str, None],
        management_root: Union[str, None],
        oas: Union[str, None],
        performance_profile: Union[str, None],
        fallback_to: Union[str, None],
        internal_service_id
    ):
        port_override = environ.get('MOCKINTOSH_FORCE_PORT', None)
        self.port = port
        self.name = name
        self.hostname = hostname
        self.ssl = ssl
        self.ssl_cert_file = ssl_cert_file
        self.ssl_key_file = ssl_key_file
        self.management_root = management_root
        self.oas = oas
        self.performance_profile = performance_profile
        self.fallback_to = fallback_to
        self.internal_service_id = internal_service_id

        if port_override is not None:
            self.port = int(port_override)
        self.endpoints = []

    def add_endpoint(self, endpoint: HttpEndpoint) -> None:
        self.endpoints.append(endpoint)

    def get_name_or_empty(self) -> str:
        return self.name if self.name is not None else ''


class HttpAlternative:

    def __init__(self):
        self.path = None
        self.priority = None
        self.methods = {}

    def __repr__(self):
        return 'priority: %s, methods: %s' % (self.priority, self.methods)
