#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :platform: Unix
    :synopsis: module that contains pre-defined configurations.
.. moduleauthor:: M. Mert Yildiran <mehmet@up9.com>
"""


def get_default():
    return """
    {
        "services": [
            {
            "comment": "Default Mock Service Config",
            "hostname": "localhost",
            "port": 8001,
            "endpoints": [
                {
                "path": "/",
                "method": "GET",
                "response": {
                        "hello": "world"
                    }
                }
            ]
            }
        ]
    }
"""
