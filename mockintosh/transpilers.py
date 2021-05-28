#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains config transpiler classes.
"""

from os import getcwd, path

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
        service = {
            'port': 8001,
            'endpoints': []
        }

        for _path, details in self.data['paths'].items():
            endpoint = {
                'path': _path
            }
            service['endpoints'].append(endpoint)

        out = {
            'services': [service]
        }

        cwd = getcwd()
        with open(path.join(cwd, self.target_filename), 'w') as file:
            yaml.dump(out, file, sort_keys=False)
