#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains HTTP related classes.
"""

import json
from collections import OrderedDict
from os import environ
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
        multipart: Union[Dict[str, str], None],
        graphql_variables: Union[Dict[str, str], None],
        is_grapql_query: bool = False
    ):
        self.schema = schema
        self.text = text
        self.urlencoded = urlencoded
        self.multipart = multipart
        self.graphql_variables = graphql_variables
        self.is_graphql_query = is_grapql_query

    def oas(self, handler) -> Union[dict, None]:
        request_body = None

        # schema
        if self.schema is not None:
            json_schema = self.schema.payload
            if isinstance(json_schema, ConfigExternalFilePath):
                json_schema_path = handler.resolve_relative_path(handler.http_server.definition.source_dir, json_schema.path)
                with open(json_schema_path, 'r') as file:
                    json_schema = json.load(file)
            request_body = {
                'required': True,
                'content': {
                    'application/json': {
                        'schema': json_schema
                    }
                }
            }

        # text
        if self.text is not None:
            request_body = {
                'required': True,
                'content': {
                    '*/*': {
                        'schema': {
                            'type': 'string'
                        }
                    }
                }
            }

        return request_body


class HttpAlternativeBase:

    def __init__(
        self,
        _id: Union[str, None],
        orig_path: str,
        params: dict,
        context: OrderedDict,
        performance_profile: Union[str, None],
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
        performance_profile: Union[str, None],
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
        internal_service_id: int,
        internal_http_service_id: Union[int, None] = None
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

        if internal_http_service_id is None:
            self.internal_http_service_id = len(HttpService.services)
            HttpService.services.append(self)
        else:
            self.internal_http_service_id = internal_http_service_id
            HttpService.services[self.internal_http_service_id] = self

    def add_endpoint(self, endpoint: HttpEndpoint) -> None:
        self.endpoints.append(endpoint)

    def get_name_or_empty(self) -> str:
        return self.name if self.name is not None else ''


class HttpPath:

    def __init__(self):
        self.path = None
        self.priority = None
        self.methods = {}

    def __repr__(self):  # pragma: no cover
        return 'priority: %s, methods: %s' % (self.priority, self.methods)


class HttpAlternative(HttpAlternativeBase):

    def __init__(
        self,
        _id: Union[str, None],
        orig_path: str,
        params: dict,
        context: OrderedDict,
        performance_profile: Union[str, None],
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

    def oas(self, path_params: list, query_string: dict, handler) -> dict:
        method_data = {'responses': {}}

        # requestBody
        if self.body is not None:
            request_body = self.body.oas(handler)
            if request_body is not None:
                method_data['requestBody'] = request_body

        # path parameters
        if path_params:
            method_data['parameters'] = self.oas_path_params(path_params, method_data.get('parameters', []))

        # header parameters
        if self.headers is not None:
            method_data['parameters'] = self.oas_headers(method_data.get('parameters', []))

        # query string parameters
        if self.query_string is not None:
            method_data['parameters'] = self.oas_query_string(query_string, method_data.get('parameters', []))

        # responses
        if self.response is not None:
            self.oas_responses(method_data)

        return method_data

    def oas_path_params(self, path_params: list, parameters: list) -> list:
        for param in path_params:
            data = {
                'in': 'path',
                'name': param,
                'required': True,
                'schema': {
                    'type': 'string'
                }
            }
            parameters.append(data)
        return parameters

    def oas_headers(self, parameters: list) -> list:
        for key in self.headers.keys():
            data = {
                'in': 'header',
                'name': key,
                'required': True,
                'schema': {
                    'type': 'string'
                }
            }
            parameters.append(data)
        return parameters

    def oas_query_string(self, query_string: dict, parameters: list) -> list:
        query_string.update(self.query_string)
        for key in query_string.keys():
            data = {
                'in': 'query',
                'name': key,
                'required': True,
                'schema': {
                    'type': 'string'
                }
            }
            parameters.append(data)
        return parameters

    def oas_responses(self, method_data: dict) -> None:
        response = self.response
        status = 200
        if isinstance(response, ConfigResponse) and response.status is not None:
            status = str(response.status)
        if status not in ('RST', 'FIN'):
            try:
                int(status)
            except ValueError:
                status = 'default'
            status_data = {}
            if isinstance(response, ConfigResponse) and response.headers is not None:
                response.oas(status_data)
            status_data['description'] = ''
            method_data['responses'][status] = status_data
