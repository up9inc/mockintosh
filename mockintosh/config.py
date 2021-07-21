#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes that mapped to the configuration file.
"""

from abc import abstractmethod
from typing import (
    List,
    Union,
    Dict,
    Tuple
)

from mockintosh.constants import PYBARS, JINJA
from mockintosh.performance import PerformanceProfile
from mockintosh.exceptions import (
    CommaInTagIsForbidden
)
from mockintosh.templating import TemplateRenderer


class ConfigService:

    services = []

    def __init__(
        self,
        _type: str,
        name: Union[str, None],
        internal_service_id: Union[int, None]
    ):
        self.type = _type
        self.name = name
        self.external_file_paths = []
        self._impl = None
        if internal_service_id is None:
            self.internal_service_id = len(ConfigService.services)
            ConfigService.services.append(self)
        else:
            self.internal_service_id = internal_service_id
            ConfigService.services[internal_service_id] = self

    def get_name(self) -> str:
        return self.name if self.name is not None else ''

    @abstractmethod
    def get_hint(self):
        raise NotImplementedError

    def add_external_file_path(self, external_file_path) -> None:
        self.external_file_paths.append(external_file_path)

    def destroy(self) -> None:
        for external_file_path in self.external_file_paths:
            external_file_path.destroy()


class ConfigContainsTag:

    def forbid_comma_in_tag(self, data: list):
        for row in data:
            if isinstance(row, (str, ConfigExternalFilePath)):
                return
            elif isinstance(row, dict):
                for key, value in row.items():
                    if key != 'tag':
                        continue
                    if ',' in value:  # pragma: no cover
                        raise CommaInTagIsForbidden(value)
            else:
                if row.tag is not None and ',' in row.tag:
                    raise CommaInTagIsForbidden(row.tag)


class ConfigExternalFilePath:

    files = []

    def __init__(self, path: str, service: ConfigService = None):
        self.path = path
        self._index = len(ConfigExternalFilePath.files)
        ConfigExternalFilePath.files.append(self)
        if service is not None:
            service.add_external_file_path(self)

    def destroy(self) -> None:
        ConfigExternalFilePath.files.pop(self._index)
        for i, external_file_path in enumerate(ConfigExternalFilePath.files):
            external_file_path._index = i


class ConfigDataset(ConfigContainsTag):

    def __init__(self, payload: Union[List[dict], str, ConfigExternalFilePath]):
        self.payload = payload
        if isinstance(self.payload, list):
            self.forbid_comma_in_tag(self.payload)


class ConfigSchema:

    def __init__(self, payload: Union[dict, ConfigExternalFilePath]):
        self.payload = payload


class ConfigHeaders:

    def __init__(self, payload: Dict[str, Union[str, List[str], ConfigExternalFilePath]]):
        self.payload = payload


class ConfigAmqpProperties:

    def __init__(
        self,
        content_type=None,
        content_encoding=None,
        delivery_mode=None,
        priority=None,
        correlation_id=None,
        reply_to=None,
        expiration=None,
        message_id=None,
        timestamp=None,
        _type=None,
        user_id=None,
        app_id=None,
        cluster_id=None
    ):
        self.content_type = content_type
        self.content_encoding = content_encoding
        self.delivery_mode = delivery_mode
        self.priority = priority
        self.correlation_id = correlation_id
        self.reply_to = reply_to
        self.expiration = expiration
        self.message_id = message_id
        self.timestamp = timestamp
        self.type = _type
        self.user_id = user_id
        self.app_id = app_id
        self.cluster_id = cluster_id


class ConfigConsume:

    def __init__(
        self,
        queue: str,
        group: Union[str, None] = None,
        key: Union[str, None] = None,
        schema: Union[ConfigSchema, None] = None,
        value: Union[str, None] = None,
        headers: Union[ConfigHeaders, None] = None,
        amqp_properties: Union[ConfigAmqpProperties, None] = None,
        capture: int = 1
    ):
        self.queue = queue
        self.group = group
        self.key = key
        self.schema = schema
        self.value = value
        self.headers = headers
        self.amqp_properties = amqp_properties
        self.capture = capture


class ConfigProduce:

    def __init__(
        self,
        queue: str,
        value: Union[str, ConfigExternalFilePath],
        create: bool = False,
        tag: Union[str, None] = None,
        key: Union[str, None] = None,
        headers: Union[ConfigHeaders, None] = None,
        amqp_properties: Union[ConfigAmqpProperties, None] = None
    ):
        self.queue = queue
        self.value = value
        self.create = create
        self.tag = tag
        self.key = key
        self.headers = headers
        self.amqp_properties = amqp_properties


class ConfigMultiProduce:

    def __init__(self, produce_list: List[ConfigProduce]):
        self.produce_list = produce_list


class ConfigActor:

    def __init__(
        self,
        name: Union[str, None] = None,
        dataset: Union[ConfigDataset, None] = None,
        produce: Union[ConfigMultiProduce, ConfigProduce, None] = None,
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


class ConfigAsyncService(ConfigService):

    services = []

    def __init__(
        self,
        _type: str,
        address: Union[str, None] = None,
        actors: List[ConfigActor] = [],
        name: Union[str, None] = None,
        ssl: bool = False,
        internal_service_id: Union[int, None] = None
    ):
        super().__init__(_type, name, internal_service_id)
        ConfigAsyncService.services.append(self)
        self.type = _type
        self.address = address
        self.actors = actors
        self.ssl = ssl

    def get_hint(self):
        return '%s://%s' % (self.type, self.address) if self.name is None else self.name

    def address_template_renderer(
        self,
        template_engine: str,
        rendering_queue,
    ) -> Tuple[str, dict]:
        if template_engine == PYBARS:
            from mockintosh.hbs.methods import env
        elif template_engine == JINJA:
            from mockintosh.j2.methods import env

        renderer = TemplateRenderer()
        self.address, _ = renderer.render(
            template_engine,
            self.address,
            rendering_queue,
            inject_methods=[
                env
            ]
        )


class ConfigResponse:

    def __init__(
        self,
        headers: Union[ConfigHeaders, None] = None,
        status: Union[str, int] = 200,
        body: Union[str, ConfigExternalFilePath, None] = None,
        use_templating: bool = True,
        templating_engine: str = PYBARS,
        tag: Union[str, None] = None,
        trigger_async_producer: Union[str, int, None] = None
    ):
        self.headers = headers
        self.status = status
        self.body = body
        self.use_templating = use_templating
        self.templating_engine = templating_engine
        self.tag = tag
        self.trigger_async_producer = trigger_async_producer

    def oas(self, status_data: dict):
        new_headers = {k.title(): v for k, v in self.headers.payload.items()}
        if 'Content-Type' in new_headers:
            if new_headers['Content-Type'].startswith('application/json'):
                status_data = {
                    'content': {
                        'application/json': {
                            'schema': {}
                        }
                    }
                }
        status_data['headers'] = {}
        for key in new_headers.keys():
            status_data['headers'][key] = {
                'schema': {
                    'type': 'string'
                }
            }


class ConfigMultiResponse(ConfigContainsTag):

    def __init__(self, payload: List[Union[ConfigResponse, ConfigExternalFilePath, str]]):
        self.payload = payload
        self.forbid_comma_in_tag(self.payload)


class ConfigBody:

    def __init__(
        self,
        schema: ConfigSchema = None,
        text: Union[str, None] = None,
        graphql_query: Union[str, ConfigExternalFilePath, None] = None,
        graphql_variables: Dict[str, str] = None,
        urlencoded: Dict[str, str] = None,
        multipart: Dict[str, str] = None
    ):
        self.schema = schema
        self.text = text
        self.urlencoded = urlencoded
        self.multipart = multipart
        self.graphql_query = graphql_query
        self.graphql_variables = graphql_variables


class ConfigEndpoint:

    def __init__(
        self,
        path: str,
        _id: Union[str, None] = None,
        comment: Union[str, None] = None,
        method: str = 'GET',
        query_string: Dict[str, str] = {},
        headers: Dict[str, str] = {},
        body: Union[ConfigBody, None] = None,
        dataset: Union[ConfigDataset, None] = None,
        response: Union[ConfigResponse, ConfigExternalFilePath, str, ConfigMultiResponse, None] = None,
        multi_responses_looped: bool = True,
        dataset_looped: bool = True,
        performance_profile: Union[str, None] = None
    ):
        self.path = path
        self.id = _id
        self.comment = comment
        self.method = method.upper()
        self.query_string = query_string
        self.headers = headers
        self.body = body
        self.dataset = dataset
        self.response = response
        self.multi_responses_looped = multi_responses_looped
        self.dataset_looped = dataset_looped
        self.performance_profile = performance_profile


class ConfigHttpService(ConfigService):

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
        fallback_to: Union[str, None] = None,
        internal_service_id: Union[int, None] = None
    ):
        super().__init__('http', name, internal_service_id)
        self.port = port
        self.hostname = hostname
        self.ssl = ssl
        self.ssl_cert_file = ssl_cert_file
        self.ssl_key_file = ssl_key_file
        self.management_root = management_root
        self.oas = oas
        self.endpoints = endpoints
        self.performance_profile = performance_profile
        self.fallback_to = fallback_to

    def get_hint(self):
        return '%s://%s:%s%s' % (
            'https' if self.ssl else 'http',
            self.hostname if self.hostname is not None else (
                'localhost'
            ),
            self.port,
            ' - %s' % self.name if self.name is not None else ''
        )


class ConfigGlobals:

    def __init__(
        self,
        headers: Union[ConfigHeaders, None],
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
        ratio: Union[int, float],
        delay: Union[int, float] = 0.0,
        faults: Union[dict, None] = None
    ):
        self.ratio = ratio
        self.delay = delay
        self.faults = {} if faults is None else faults
        self.actuator = PerformanceProfile(
            self.ratio,
            delay=self.delay,
            faults=self.faults
        )


class ConfigRoot:

    def __init__(
        self,
        services: List[Union[ConfigHttpService, ConfigAsyncService]],
        management: Union[ConfigManagement, None] = None,
        templating_engine: str = PYBARS,
        _globals: Union[ConfigGlobals, None] = None,
        performance_profiles: Dict[str, ConfigPerformanceProfile] = {}
    ):
        self.services = services
        self.management = management
        self.templating_engine = templating_engine
        self.globals = _globals
        self.performance_profiles = performance_profiles
