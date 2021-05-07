#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes that mapped to the configuration file.
"""

from typing import (
    List,
    Union,
    Dict
)


class ConfigExternalFilePath:

    def __init__(self, path: str):
        self.path = path


class ConfigDataset:

    def __init__(self, payload: Union[List[dict], str, ConfigExternalFilePath]):
        self.payload = payload


class ConfigHeaders:

    def __init__(self, payload: Dict[str, Union[str, List[str], ConfigExternalFilePath]]):
        self.payload = payload


class ConfigConsume:

    def __init__(
        self,
        queue: str,
        group: Union[str, None] = None,
        key: Union[str, None] = None,
        schema: Union[dict, ConfigExternalFilePath, None] = None,
        value: Union[str, None] = None,
        headers: Union[ConfigHeaders, None] = None,
        capture: Union[int, None] = None
    ):
        self.queue = queue
        self.group = group
        self.key = key
        self.schema = schema
        self.value = value
        self.headers = headers
        self.capture = capture


class ConfigProduce:

    def __init__(
        self,
        queue: str,
        value: Union[str, ConfigExternalFilePath],
        create: bool = False,
        tag: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: Union[ConfigHeaders, None] = None
    ):
        self.queue = queue
        self.value = value
        self.create = create
        self.tag = tag
        self.key = key
        self.headers = headers


class ConfigActor:

    def __init__(
        self,
        name: Union[str, None] = None,
        dataset: Union[ConfigDataset, None] = None,
        produce: Union[List[ConfigProduce], ConfigProduce, None] = None,
        consume: Union[ConfigConsume, None] = None,
        delay: Union[int, float, None] = None,
        limit: Union[int, None] = None,
        multi_payloads_looped: bool = True,
        dataset_looped: bool = True,
    ):
        self.name = name
        self.dataset = dataset
        self.produce = produce
        self.consume = consume
        self.delay = delay
        self.limit = limit
        self.multi_payloads_looped = multi_payloads_looped
        self.dataset_looped = dataset_looped


class ConfigAsync:

    def __init__(
        self,
        _type: str,
        address: str,
        actors: List[ConfigActor],
        name: Union[str, None] = None,
        ssl: bool = False
    ):
        self.type = _type
        self.address = address
        self.actors = actors
        self.name = name
        self.ssl = ssl


class ConfigResponse:

    def __init__(
        self,
        headers: Union[ConfigHeaders, None] = None,
        status: Union[str, int, None] = None,
        body: Union[str, ConfigExternalFilePath, None] = None,
        use_templating: Union[bool, None] = None,
        templating_engine: Union[str, None] = None,
        tag: Union[str, None] = None,
    ):
        self.headers = headers
        self.status = status
        self.body = body
        self.use_templating = use_templating
        self.templating_engine = templating_engine
        self.tag = tag


class ConfigBody:

    def __init__(
        self,
        schema: Union[dict, ConfigExternalFilePath, None] = None,
        text: Union[str, None] = None,
        urlencoded: Dict[str, str] = None,
        multipart: Dict[str, str] = None,
    ):
        self.schema = schema
        self.text = text
        self.urlencoded = urlencoded
        self.multipart = multipart


class ConfigEndpoint:

    def __init__(
        self,
        path: str,
        _id: Union[str, None] = None,
        comment: Union[str, None] = None,
        method: Union[str, None] = None,
        query_string: Dict[str, str] = None,
        headers: Dict[str, str] = None,
        body: Union[ConfigBody, None] = None,
        dataset: Union[ConfigDataset, None] = None,
        response: Union[Union[ConfigResponse, ConfigExternalFilePath, str], List[Union[ConfigResponse, ConfigExternalFilePath, str]], None] = None,
        multi_responses_looped: bool = True,
        dataset_looped: bool = True,
        performance_profile: Union[str, None] = None
    ):
        self.path = path
        self.id = _id
        self.comment = comment
        self.method = method
        self.query_string = query_string
        self.headers = headers
        self.body = body
        self.dataset = dataset
        self.response = response
        self.multi_responses_looped = multi_responses_looped
        self.dataset_looped = dataset_looped
        self.performance_profile = performance_profile


class ConfigService:

    def __init__(
        self,
        port: int,
        name: Union[str, None] = None,
        hostname: Union[str, None] = None,
        ssl: bool = False,
        ssl_cert_file: Union[str, None] = None,
        ssl_key_file: Union[str, None] = None,
        management_root: Union[str, None] = None,
        oas: Union[str, ConfigExternalFilePath, None] = None,
        endpoints: List[ConfigEndpoint] = [],
        performance_profile: Union[str, None] = None,
        fallback_to: Union[str, None] = None
    ):
        self.port = port
        self.name = name
        self.hostname = hostname
        self.ssl = ssl
        self.ssl_cert_file = ssl_cert_file
        self.ssl_key_file = ssl_key_file
        self.management_root = management_root
        self.oas = oas
        self.endpoints = endpoints
        self.performance_profile = performance_profile
        self.fallback_to = fallback_to


class ConfigGlobals:

    def __init__(
        self,
        headers: ConfigHeaders,
        performance_profile: Union[str, None] = None
    ):
        self.headers = headers
        self.performance_profile = performance_profile


class ConfigManagement:

    def __init__(
        self,
        port: str,
        ssl: bool = False,
        ssl_cert_file: Union[str, None] = None,
        ssl_key_file: Union[str, None] = None
    ):
        self.port = port
        self.ssl = ssl
        self.ssl_cert_file = ssl_cert_file
        self.ssl_key_file = ssl_key_file


class ConfigPerformanceProfile:

    def __init__(
        self,
        ratio: Union[int, float, None] = None,
        delay: Union[int, float, None] = None,
        faults: Union[dict, None] = None
    ):
        self.ratio = ratio
        self.delay = delay
        self.faults = faults


class ConfigRoot:

    def __init__(
        self,
        services: List[Union[ConfigService, ConfigAsync]],
        management: Union[ConfigManagement, None] = None,
        templating_engine: Union[str, None] = None,
        _globals: Union[ConfigGlobals, None] = None,
        performance_profiles: Union[Dict[str, ConfigPerformanceProfile], None] = None
    ):
        self.services = services
        self.management = management
        self.templating_engine = templating_engine
        self.globals = _globals
        self.performance_profiles = performance_profiles
