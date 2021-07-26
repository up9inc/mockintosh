#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config transpiler classes.
"""

import re
import sys
import json
import tempfile
import logging
from os import getcwd, path
from urllib.parse import urlparse
from collections import OrderedDict
from typing import (
    List,
    Union,
    Tuple
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

    def path_oas_to_handlebars(self, path: str) -> Tuple[str, Union[int, None]]:
        segments = _safe_path_split(path)
        new_segments = []
        last_param_index = None
        for i, segment in enumerate(segments):
            match = re.search(r'{(.*)}', segment)
            if match is not None:
                name = match.group(1).strip()
                new_segments.append('{{ %s }}' % name)
                last_param_index = i + 1
            else:
                new_segments.append(segment)
        return '/'.join(new_segments), last_param_index

    def _transpile_consumes(self, details: dict, endpoint: dict) -> dict:
        if 'consumes' in details and details['consumes']:
            endpoint['headers']['Accept'] = '{{ headers_accept_%s }}' % re.sub(r'[^a-zA-Z0-9 \n\.]', '_', details['consumes'][0])
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
            # This means that there could be arbitrarily appearing additional fields in the JSON response
            # and there is no equivalent of this in Mockintosh.
            # if 'additionalProperties' in schema and isinstance(schema['additionalProperties'], dict):
            #     ref.update(schema['additionalProperties'])
        elif schema['type'] == 'array':
            if 'allOf' in schema['items']:
                ref = schema['items']['allOf'][0]['properties']
            elif isinstance(schema['items'], list):
                ref = schema['items'][0]['properties']
            else:
                try:
                    ref = schema['items']['properties']
                except KeyError:
                    ref = schema['items']
        return ref

    def _transpile_body_json_object(self, properties: dict, last_path_param_index: Union[int, None] = None) -> str:
        body_json = ''
        for field, _details in properties.items():
            if not isinstance(_details, dict):
                continue

            if 'example' in _details:
                if 'type' in _details and _details['type'] == 'string':
                    body_json += '"%s": "%s", ' % (field, _details['example'])
                else:
                    body_json += '"%s": %s, ' % (field, str(_details['example']))
            else:
                if 'type' not in _details:
                    continue

                if field == 'id' and _details['type'] in ('integer', 'number') and last_path_param_index is not None:
                    body_json += '"%s": {{ request.path.%s }}, ' % (
                        field,
                        str(last_path_param_index)
                    )
                    last_path_param_index = None
                else:
                    body_json += '"%s": %s, ' % (
                        field,
                        self._transpile_body_json_value(_details, last_path_param_index=last_path_param_index)
                    )

        return '{%s}' % body_json[:-2]

    def _transpile_body_json_value(
        self,
        _details: str,
        last_path_param_index: Union[int, None] = None,
        future: bool = False
    ) -> str:
        result = ''
        if _details['type'] == 'string':
            result += self._transpile_body_json_string(_format=_details.get('format', None), future=future)
        elif _details['type'] == 'number':
            result += self._transpile_body_json_number(_format=_details.get('format', None))
        elif _details['type'] == 'integer':
            result += self._transpile_body_json_integer(_format=_details.get('format', None))
        elif _details['type'] == 'boolean':
            result += self._transpile_body_json_boolean()
        elif _details['type'] == 'array':
            result += self._transpile_body_json_array(_details, last_path_param_index=last_path_param_index)
        elif _details['type'] == 'object':
            result += self._transpile_body_json_object(_details['properties'], last_path_param_index=last_path_param_index)
        return result

    def _transpile_body_json_string(
        self,
        _format: Union[str, None] = None,
        future: bool = False
    ) -> str:
        if _format == 'date-time':
            if future:
                return '"{{ fake.future_datetime() }}"'
            else:
                return '"{{ fake.date_time() }}"'
        else:
            return '"{{ fake.sentence(nb_words=random.int(0, 20)) }}"'

    def _transpile_body_json_number(self, _format: Union[str, None] = None) -> str:
        _min = sys.float_info.min
        _max = sys.float_info.max
        if _format == 'float':
            _min /= 2
            _max /= 2
        return '{{ random.float(%f, %f, (random.int(1, 5))) }}' % (
            _min,
            _max
        )

    def _transpile_body_json_integer(self, _format: Union[str, None] = None) -> str:
        _min = - sys.maxsize - 1
        _max = sys.maxsize
        if _format == 'int32':
            _min /= 2
            _max /= 2
        return '{{ random.int(%d, %d) }}' % (
            _min,
            _max
        )

    def _transpile_body_json_boolean(self) -> str:
        return '{{ fake.boolean(chance_of_getting_true=50) | lower }}'

    def _transpile_body_json_array(
        self,
        _details: dict,
        last_path_param_index: Union[int, None] = None
    ) -> str:
        return '[{%% for n in range(range(100) | random) %%} %s {%% if not loop.last %%},{%% endif %%}{%% endfor %%}]' % (
            self._transpile_body_json_value(_details['items'], last_path_param_index=last_path_param_index)
        )

    def _transpile_responses(
        self,
        details: dict,
        endpoint: dict,
        content_type: Union[str, None],
        last_path_param_index: Union[int, None]
    ) -> dict:
        if not isinstance(details, dict) or 'responses' not in details:
            return endpoint

        for status, _response in details['responses'].items():
            status = 200 if status == 'default' else status

            if isinstance(status, str) and len(status) == 3 and status.endswith('XX'):
                status = '%s%s' % (status[0], '00')

            try:
                status = int(status)
            except ValueError:
                status = 200

            response = {
                'status': status,
                'headers': {}
            }

            if content_type is not None:
                response['headers']['Content-Type'] = content_type

            if 'schema' in _response:
                ref = self._transpile_schema(_response['schema'])
                response['body'] = self._transpile_body_json_object(ref, last_path_param_index=last_path_param_index)

            if 'headers' in _response:
                response['headers'].update(self._transpile_headers(_response['headers']))

            self._delete_key_if_empty(response, 'headers')

            endpoint['response'].append(response)

        return endpoint

    def _transpile_headers(self, headers: dict) -> dict:
        result = {}
        for key, value in headers.items():
            future = True if 'expire' in key.lower() else False
            result[key] = self._transpile_body_json_value(value, future=future)
        return result

    def _determine_management_port(self, service_port: int) -> int:
        port = 8000
        while port == service_port and port < 9001:
            port += 1
        return port

    def _delete_key_if_empty(self, endpoint, key):
        if not endpoint[key]:
            del endpoint[key]

    def transpile(self, direct: bool = False) -> Union[str, dict]:
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
            _path, last_path_param_index = self.path_oas_to_handlebars(_path)
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
                endpoint = self._transpile_responses(details, endpoint, content_type, last_path_param_index)

                self._delete_key_if_empty(endpoint, 'headers')
                self._delete_key_if_empty(endpoint, 'queryString')
                self._delete_key_if_empty(endpoint, 'body')
                self._delete_key_if_empty(endpoint, 'response')

                service['endpoints'].append(endpoint)

        out = {
            'templatingEngine': 'Jinja2',
            'management': {
                'port': self._determine_management_port(service['port'])
            },
            'services': [service]
        }

        if direct:
            return out

        cwd = getcwd()
        target_path = path.join(cwd, self.target_filename)
        file = None
        try:
            file = open(target_path, 'w')
        except PermissionError:
            logging.warning('The current working directory \'%s\' is not writable!', cwd)
            file = tempfile.NamedTemporaryFile(mode='w', delete=False)
            target_path = file.name

        if self.format == 'yaml':
            yaml.dump(out, file, sort_keys=False)
        else:
            json.dump(out, file, indent=2, default=str)

        file.close()

        return target_path
