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
        super().__init__('%r field is restricted!' % field)


class CommaInTagIsForbidden(Exception):
    """Raised in case of a comma is detected in a tag.
    """

    def __init__(self, tag):
        super().__init__('Using comma is forbidden in tags: %s' % tag)


class AsyncProducerListQueueMismatch(Exception):
    """Raised in case of values in 'queue' field differs in an async producer list.
    """

    def __init__(self, actor_name):
        super().__init__('Producer actor \'%s\' has different queue values!' % actor_name)


class AsyncProducerListHasNoPayloadsMatchingTags(Exception):
    """Raised in case of none of the payloads in an async producer list matches the given tag.
    """

    def __init__(self, actor_name, tags):
        super().__init__('Producer actor \'%s\' has no payloads matching one of the tags: [%s]' % (actor_name, ', '.join(tags)))


class AsyncProducerPayloadLoopEnd(Exception):
    """Raised in case of `multiPayloadsLooped` is `False` and the payload loop ends.
    """

    def __init__(self, actor_name):
        super().__init__('Payload loop for producer actor \'%s\' is ended!' % actor_name)


class AsyncProducerDatasetLoopEnd(Exception):
    """Raised in case of `datasetLooped` is `False` and the dataset loop ends.
    """

    def __init__(self, actor_name):
        super().__init__('Dataset loop for producer actor \'%s\' is ended!' % actor_name)


class InternalResourcePathCheckError(Exception):
    """Raised in case of a resource path check fails in `ManagementResourcesHandler`.
    """

    def __init__(self):
        super().__init__(None)
