#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains the exceptions.
"""


class UnrecognizedConfigFileFormat(Exception):
    """Raised in case of both JSON and YAML parser is failed for the configuration file.
    """

    def __init__(self, message, filepath, yaml_error_msg):
        message += '\nFile path: %s' % filepath
        message += '\nYAML load error: %s' % yaml_error_msg
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


class CertificateLoadingError(Exception):
    """Raised in case of a certificate file is not found or in a forbidden path.
    """

    def __init__(self, reason):
        super().__init__('\nCertificate loading error: %s' % reason)


class RestrictedFieldError(Exception):
    """Raised in case of a restricted field is tried to be changed during config update.
    """

    def __init__(self, field):
        super().__init__('\'%s\' field is restricted!' % field)
