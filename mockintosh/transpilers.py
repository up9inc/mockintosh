#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config transpiler classes.
"""

from os import getcwd, path
from collections import OrderedDict

import yaml
from prance import ResolvingParser


class OASToConfigTranspiler:

    def __init__(self, source: str, target_filename: str):
        self.source = source
        self.data = None
        self.target_filename = target_filename
        self.load()

    def load(self) -> None:
        parser = ResolvingParser(self.source)
        # print(dir(parser))
        # print(parser.semver)
        # print(parser.backend)
        # print(parser.options)
        # print(parser.version)
        self.data = parser.specification

    def transpile(self) -> None:
        service = OrderedDict()
        service['port'] = 8001
        service['hostname'] = self.data['host']
        if 'https' in self.data['schemes']:
            service['ssl'] = True
        service['endpoints'] = []

        base_path = self.data['basePath']

        for _path, _details in self.data['paths'].items():
            _path = _path.replace('{', '{{ ')
            _path = _path.replace('}', ' }}')
            _path = base_path + _path
            for method, details in _details.items():
                endpoint = {
                    'path': _path,
                    'method': method.upper(),
                    'headers': {},
                    'queryString': {},
                    'body': {}
                }

                # consumes
                if 'consumes' in details and details['consumes']:
                    accept = ''
                    for mime in details['consumes']:
                        accept += '%s, ' % mime
                    endpoint['headers']['Accept'] = accept.strip()[:-1]

                # parameters
                for parameter in details['parameters']:
                    if not parameter['required']:
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

                service['endpoints'].append(endpoint)

        out = {
            'services': [service]
        }

        cwd = getcwd()
        with open(path.join(cwd, self.target_filename), 'w') as file:
            yaml.dump(out, file, sort_keys=False)
