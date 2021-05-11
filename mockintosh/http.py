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

from mockintosh.config import (
    ConfigSchema,
    ConfigExternalFilePath,
    ConfigResponse,
    ConfigMultiResponse,
    ConfigDataset
)


class HttpBody:

    def __init__(
        self,
        schema: Union[ConfigSchema, ConfigExternalFilePath, None],
        text: Union[str, None],
        urlencoded: Union[Dict[str, str], None],
        multipart: Union[Dict[str, str], None]
    ):
        self.schema = schema
        self.text = text
        self.urlencoded = urlencoded
        self.multipart = multipart


class HttpAlternativeBase:

    def __init__(
        self,
        _id: Union[str, None],
        orig_path: str,
        params: dict,
        context: OrderedDict,
        performance_profile: str,
        query_string: Dict[str, str],
        headers: Dict[str, str],
        body: Union[HttpBody, None],
        dataset: Union[ConfigDataset, None],
        response: Union[ConfigResponse, ConfigExternalFilePath, str, ConfigMultiResponse, None],
        multi_responses_looped: bool,
        dataset_looped: bool
    ):
        self.id = _id
        self.orig_path = orig_path
        self.params = params
        self.context = context
        self.performance_profile = performance_profile
        self.query_string = query_string
        self.headers = headers
        self.body = body
        self.dataset = dataset
        self.response = response
        self.multi_responses_looped = multi_responses_looped
        self.dataset_looped = dataset_looped


class HttpEndpoint(HttpAlternativeBase):

    def __init__(
        self,
        _id: Union[str, None],
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
        body: Union[HttpBody, None],
        dataset: Union[ConfigDataset, None],
        response: Union[ConfigResponse, ConfigExternalFilePath, str, ConfigMultiResponse, None],
        multi_responses_looped: bool,
        dataset_looped: bool,
    ):
        super().__init__(
            _id,
            orig_path,
            params,
            context,
            performance_profile,
            query_string,
            headers,
            body,
            dataset,
            response,
            multi_responses_looped,
            dataset_looped
        )
        self.priority = priority
        self.path = path
        self.comment = comment
        self.method = method


class HttpService:

    services = []

    def __init__(
        self,
        port: int,
        name: Union[str, None],
        hostname: Union[str, None],
        ssl: bool,
        ssl_cert_file: Union[str, None],
        ssl_key_file: Union[str, None],
        management_root: Union[str, None],
        oas: Union[str, ConfigExternalFilePath, None],
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
        HttpService.services.append(self)

    def add_endpoint(self, endpoint: HttpEndpoint) -> None:
        self.endpoints.append(endpoint)

    def get_name_or_empty(self) -> str:
        return self.name if self.name is not None else ''


class HttpPath:

    def __init__(self):
        self.path = None
        self.priority = None
        self.methods = {}

    def __repr__(self):
        return 'priority: %s, methods: %s' % (self.priority, self.methods)


class HttpAlternative(HttpAlternativeBase):

    def __init__(
        self,
        _id: Union[str, None],
        orig_path: str,
        params: dict,
        context: OrderedDict,
        performance_profile: str,
        query_string: Dict[str, str],
        headers: Dict[str, str],
        body: Union[HttpBody, None],
        dataset: Union[ConfigDataset, None],
        response: Union[ConfigResponse, ConfigExternalFilePath, str, ConfigMultiResponse, None],
        multi_responses_looped: bool,
        dataset_looped: bool,
        internal_endpoint_id: int
    ):
        super().__init__(
            _id,
            orig_path,
            params,
            context,
            performance_profile,
            query_string,
            headers,
            body,
            dataset,
            response,
            multi_responses_looped,
            dataset_looped
        )
        self.multi_responses_index = None
        self.dataset_index = None
        self.internal_endpoint_id = internal_endpoint_id
        self.counters = {}
