#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes for request parameters.
"""

from typing import (
    Union
)


class ParamBase:

    def __init__(self, key: str, value: Union[dict, str]):
        self.key = key
        self.value = value


class HeaderParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class QueryStringParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class BodyTextParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class BodyUrlencodedParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class BodyMultipartParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class BodyGraphQLVariablesParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class AsyncValueParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class AsyncKeyParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class AsyncHeadersParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)


class AsyncAmqpPropertiesParam(ParamBase):

    def __init__(self, key: str, value: Union[dict, str]):
        super().__init__(key, value)
