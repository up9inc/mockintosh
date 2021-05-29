#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config transpiler classes.
"""

import sys
import json
from os import getcwd, path
from collections import OrderedDict
from typing import (
    List
)

import yaml
from prance import ResolvingParser


class OASToConfigTranspiler:

    def __init__(self, source: str, convert_args: List[str]):
        self.source = source
        self.data = None
        self.target_filename, self.format = convert_args
        self.load()

    def load(self) -> None:
        parser = ResolvingParser(self.source)
        self.data = parser.specification

    def transpile(self) -> str:
        service = OrderedDict()
        service['port'] = 8001
        if 'host' in self.data:
            service['hostname'] = self.data['host']
        if 'schemes' in self.data and 'https' in self.data['schemes']:
            service['ssl'] = True
        service['endpoints'] = []

        base_path = ''
        if 'basePath' in self.data:
            base_path = self.data['basePath']

        for _path, _details in self.data['paths'].items():
            _path = _path.replace('{', '{{ ')
            _path = _path.replace('}', ' }}')
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

                # consumes
                if 'consumes' in details and details['consumes']:
                    accept = ''
                    for mime in details['consumes']:
                        accept += '%s, ' % mime
                    endpoint['headers']['Accept'] = accept.strip()[:-1]

                # parameters
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

                # produces
                content_type = None
                if 'produces' in details and details['produces']:
                    content_type = details['produces'][0]

                # responses
                for status, _response in details['responses'].items():
                    response = {
                        'status': 200 if status == 'default' else int(status),
                        'headers': {}
                    }

                    if content_type is not None:
                        response['headers']['Content-Type'] = content_type

                    if 'schema' in _response:
                        body_json = ''
                        schema = _response['schema']
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

                        for field, _details in ref.items():
                            if not isinstance(_details, dict):
                                continue

                            if 'example' in _details:
                                if _details['type'] == 'string':
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

                        response['body'] = '{%s}' % body_json[:-2]

                    endpoint['response'].append(response)

                service['endpoints'].append(endpoint)

        out = {
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
