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


class UnsupportedTemplateEngine(Exception):
    """Raised in case of an unsupported template engine is detected.
    """

    def __init__(self, engine, supported_engines):
        super().__init__(
            '\nUnsupported template engine: %s\nSupported template engines: %s' % (
                engine,
                ', '.join(supported_engines)
            )
        )


class CertificateLoadingError(Exception):
    """Raised in case of a certificate file is not found or in a forbidden path.
    """

    def __init__(self, reason):
        super().__init__('\nCertificate loading error: %s' % reason)
