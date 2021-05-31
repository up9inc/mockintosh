#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config transpiler classes.
"""

import re
import sys
import json
from os import getcwd, path
from urllib.parse import urlparse
from collections import OrderedDict
from typing import (
    List,
    Union
)

import yaml
from prance import ResolvingParser

from mockintosh.helpers import _safe_path_split


class OASToConfigTranspiler:

    def __init__(self, source: str, convert_args: List[str]):
        self.source = source
        self.data = None
        self.target_filename, self.format = convert_args
        self.load()

    def load(self) -> None:
        parser = ResolvingParser(self.source)
        self.data = parser.specification

    def path_oas_to_handlebars(self, path: str) -> str:
        segments = _safe_path_split(path)
        new_segments = []
        for segment in segments:
            match = re.search(r'{(.*)}', segment)
            if match is not None:
                name = match.group(1).strip()
                new_segments.append('{{ %s }}' % name)
            else:
                new_segments.append(segment)
        return '/'.join(new_segments)

    def _transpile_consumes(self, details: dict, endpoint: dict) -> dict:
        if 'consumes' in details and details['consumes']:
            accept = ''
            for mime in details['consumes']:
                accept += '%s, ' % mime
            endpoint['headers']['Accept'] = accept.strip()[:-1]
        return endpoint

    def _transpile_parameters(self, details: dict, endpoint: dict) -> dict:
        if 'parameters' in details:
            for parameter in details['parameters']:
                if 'required' not in parameter or not parameter['required']:
                    continue

                if parameter['in'] == 'header':
                    endpoint['headers'][parameter['name']] = '{{ %s }}' % parameter['name']
                elif parameter['in'] == 'query':
                    endpoint['queryString'][parameter['name']] = '{{ %s }}' % parameter['name']
                elif parameter['in'] == 'formData':
                    if 'urlencoded' not in endpoint['body']:
                        endpoint['body']['urlencoded'] = {}

                    endpoint['body']['urlencoded'][parameter['name']] = '{{ %s }}' % parameter['name']
                elif parameter['in'] == 'body':
                    endpoint['body']['schema'] = parameter['schema']
        return endpoint

    def _transpile_produces(self, details: dict) -> Union[str, None]:
        content_type = None
        if 'produces' in details and details['produces']:
            content_type = details['produces'][0]
        return content_type

    def _transpile_schema(self, schema: dict) -> dict:
        ref = {}
        if 'type' not in schema or schema['type'] == 'object':
            if 'properties' in schema:
                ref = schema['properties']
            if 'additionalProperties' in schema and isinstance(schema['additionalProperties'], dict):
                ref.update(schema['additionalProperties'])
        elif schema['type'] == 'array':
            if 'allOf' in schema['items']:
                ref = schema['items']['allOf'][0]['properties']
            else:
                ref = schema['items']['properties']
        return ref

    def _transpile_body_json(self, ref: dict) -> str:
        body_json = ''
        for field, _details in ref.items():
            if not isinstance(_details, dict):
                continue

            if 'example' in _details:
                if 'type' in _details and _details['type'] == 'string':
                    body_json += '"%s": "%s", ' % (field, _details['example'])
                else:
                    body_json += '"%s": %s, ' % (field, _details['example'])
            else:
                if 'type' not in _details:
                    continue

                if _details['type'] == 'integer':
                    body_json += '"%s": {{ random.int %d %d }}, ' % (
                        field,
                        - sys.maxsize - 1,
                        sys.maxsize
                    )
                elif _details['type'] == 'float':
                    body_json += '"%s": {{ random.float %f %f (random.int 1 5) }}, ' % (
                        field,
                        sys.float_info.min,
                        sys.float_info.max
                    )
                else:
                    body_json += '"%s": "{{ fake.sentence nb_words=10 }}", ' % field
        return body_json

    def _transpile_responses(self, details: dict, endpoint: dict, content_type: Union[str, None]) -> dict:
        if isinstance(details, list):
            return endpoint

        for status, _response in details['responses'].items():
            response = {
                'status': 200 if status == 'default' else int(status),
                'headers': {}
            }

            if content_type is not None:
                response['headers']['Content-Type'] = content_type

            if 'schema' in _response:
                ref = self._transpile_schema(_response['schema'])
                body_json = self._transpile_body_json(ref)
                response['body'] = '{%s}' % body_json[:-2]

            endpoint['response'].append(response)

        return endpoint

    def _determine_management_port(self, service_port: int) -> int:
        port = 8000
        while port == service_port and port < 9001:
            port += 1
        return port

    def transpile(self) -> str:
        service = OrderedDict()
        service['port'] = 8001
        if 'host' in self.data:
            host_parsed = urlparse('http://%s' % self.data['host'])
            service['hostname'] = host_parsed.hostname
            service['port'] = host_parsed.port if host_parsed.port is not None else service['port']
        if 'schemes' in self.data and 'https' in self.data['schemes']:
            service['ssl'] = True
        service['endpoints'] = []

        base_path = ''
        if 'basePath' in self.data:
            base_path = self.data['basePath']

        for _path, _details in self.data['paths'].items():
            _path = self.path_oas_to_handlebars(_path)
            _path = base_path + _path
            for method, details in _details.items():
                if method == 'parameters':
                    continue

                endpoint = {
                    'path': _path,
                    'method': method.upper(),
                    'headers': {},
                    'queryString': {},
                    'body': {},
                    'response': []
                }

                endpoint = self._transpile_consumes(details, endpoint)
                endpoint = self._transpile_parameters(details, endpoint)
                content_type = self._transpile_produces(details)
                endpoint = self._transpile_responses(details, endpoint, content_type)

                service['endpoints'].append(endpoint)

        out = {
            'management': {
                'port': self._determine_management_port(service['port'])
            },
            'services': [service]
        }

        cwd = getcwd()
        target_path = path.join(cwd, self.target_filename)
        with open(target_path, 'w') as file:
            if self.format == 'yaml':
                yaml.dump(out, file, sort_keys=False)
            else:
                json.dump(out, file, indent=2)

        return target_path
