#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :platform: Unix
    :synopsis: module that contains the exceptions.
"""


class UnrecognizedConfigFileFormat(Exception):
    """Raised in case of both JSON and YAML parser is failed for the configuration file.
    """

    def __init__(self, message, filepath, json_error_msg, yaml_error_msg):
        message += '\nFile path: %s' % filepath
        message += '\nJSON load error: %s' % json_error_msg
        message += '\nYAML load error: %s' % yaml_error_msg
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
