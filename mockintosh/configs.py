#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains pre-defined configurations.
"""


def get_default():
    return {
        'services': [
            {
                'name': 'Default Mock Service Config',
                'port': 8001,
                'endpoints': [
                    {
                        'path': '/',
                        'method': 'GET',
                        'response': 'hello world'
                    }
                ]
            }
        ]
    }
