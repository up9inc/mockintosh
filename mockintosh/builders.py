#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains classes that builds complex data structures.
"""

from typing import (
    Union,
    List
)

from mockintosh.constants import PYBARS
from mockintosh.config import (
    ConfigService,
    ConfigActor,
    ConfigAsyncService,
    ConfigBody,
    ConfigConsume,
    ConfigDataset,
    ConfigEndpoint,
    ConfigExternalFilePath,
    ConfigGlobals,
    ConfigHeaders,
    ConfigAmqpProperties,
    ConfigHttpService,
    ConfigManagement,
    ConfigMultiProduce,
    ConfigMultiResponse,
    ConfigPerformanceProfile,
    ConfigProduce,
    ConfigResponse,
    ConfigRoot,
    ConfigSchema
)


class ConfigRootBuilder:

    def build_config_external_file_path(self, data: Union[str, list, dict, None], service: ConfigService = None) -> Union[ConfigExternalFilePath, str, list, dict, None]:
        if isinstance(data, str) and len(data) > 1 and data[0] == '@':
            return ConfigExternalFilePath(data, service=service)
        else:
            return data

    def build_config_dataset(self, data: Union[List[dict], str, None], service: ConfigService = None) -> Union[ConfigDataset, None]:
        if data is None:
            return None

        payload = None
        if isinstance(data, list):
            payload = data
        elif isinstance(data, str):
            payload = self.build_config_external_file_path(data, service=service)

        return ConfigDataset(payload)

    def build_config_schema(self, data: Union[dict, str, None], service: ConfigService = None) -> Union[ConfigSchema, None]:
        if data is None:
            return data

        schema = None
        if isinstance(data, dict):
            schema = data
        elif isinstance(data, str):
            schema = self.build_config_external_file_path(data, service=service)

        return ConfigSchema(schema)

    def build_config_headers(self, data: dict, service: ConfigService = None) -> Union[ConfigHeaders, None]:
        config_headers = None
        if 'headers' in data:
            payload = {}
            data_headers = data['headers']
            for key, value in data_headers.items():
                payload[key] = self.build_config_external_file_path(value, service=service)
            config_headers = ConfigHeaders(payload)
        return config_headers

    def build_config_amqp_properties(self, data: dict) -> Union[ConfigHeaders, None]:
        config_amqp_properties = None
        if 'amqpProperties' in data:
            config_amqp_properties = ConfigAmqpProperties(**data['amqpProperties'])
        return config_amqp_properties

    def build_config_consume(self, consume: Union[dict, None], service: ConfigService = None) -> Union[ConfigConsume, None]:
        if consume is None:
            return None

        return ConfigConsume(
            consume['queue'],
            group=consume.get('group', None),
            key=consume.get('key', None),
            schema=self.build_config_schema(consume.get('schema', None), service=service),
            value=consume.get('value', None),
            headers=self.build_config_headers(consume, service=service),
            amqp_properties=self.build_config_amqp_properties(consume),
            capture=consume.get('capture', 1)
        )

    def build_config_produce(self, produce: dict, service: ConfigService = None) -> ConfigProduce:
        return ConfigProduce(
            produce['queue'],
            self.build_config_external_file_path(produce['value'], service=service),
            produce.get('create', False),
            tag=produce.get('tag', None),
            key=produce.get('key', None),
            headers=self.build_config_headers(produce, service=service),
            amqp_properties=self.build_config_amqp_properties(produce)
        )

    def build_config_multi_produce(self, data: List[dict], service: ConfigService = None) -> ConfigMultiResponse:
        produce_list = []
        for produce in data:
            produce_list.append(self.build_config_produce(produce, service=service))

        return ConfigMultiProduce(produce_list)

    def build_config_actor(self, actor: dict, service: ConfigService = None) -> ConfigActor:
        produce = None
        if 'produce' in actor:
            produce = actor['produce']
            if isinstance(produce, list):
                produce = self.build_config_multi_produce(produce, service=service)
            elif isinstance(produce, dict):
                produce = self.build_config_produce(produce, service=service)

        return ConfigActor(
            name=actor.get('name', None),
            dataset=self.build_config_dataset(actor.get('dataset', None), service=service),
            produce=produce,
            consume=self.build_config_consume(actor.get('consume', None), service=service),
            delay=actor.get('delay', None),
            limit=actor.get('limit', None),
            multi_payloads_looped=actor.get('multiPayloadsLooped', True),
            dataset_looped=actor.get('datasetLooped', True)
        )

    def build_config_async_service(self, data: dict, internal_service_id: Union[int, None] = None) -> ConfigAsyncService:
        config_service = ConfigAsyncService(
            'amqp' if data['type'] in ('rabbitmq', 'activemq') else data['type'],
            address=data.get('address', None),
            actors=[],
            name=data.get('name', None),
            ssl=data.get('ssl', False),
            internal_service_id=internal_service_id
        )

        actors = []
        if 'actors' in data:
            actors = [self.build_config_actor(actor, service=config_service) for actor in data['actors']]
        config_service.actors = actors

        return config_service

    def build_config_response(self, data: dict, service: ConfigService = None) -> ConfigResponse:
        return ConfigResponse(
            headers=self.build_config_headers(data, service=service),
            status=data.get('status', None),
            body=self.build_config_external_file_path(data.get('body', None), service=service),
            use_templating=data.get('useTemplating', True),
            templating_engine=data.get('templatingEngine', PYBARS),
            tag=data.get('tag', None),
            trigger_async_producer=data.get('triggerAsyncProducer', None)
        )

    def build_config_multi_response(self, data: List[Union[dict, str]], service: ConfigService) -> ConfigMultiResponse:
        responses = []
        for response in data:
            if isinstance(response, dict):
                responses.append(self.build_config_response(response, service=service))
            elif isinstance(response, str):
                responses.append(self.build_config_external_file_path(response, service=service))

        return ConfigMultiResponse(responses)

    def build_config_body(self, data: Union[dict, None], service: ConfigService = None) -> Union[ConfigBody, None]:
        if data is None:
            return data

        return ConfigBody(
            schema=self.build_config_schema(data.get('schema', None), service=service),
            text=data.get('text', None),
            graphql_query=self.build_config_external_file_path(data.get('graphql-query', None), service=service),
            graphql_variables=data.get('graphql-variables', None),
            urlencoded=data.get('urlencoded', None),
            multipart=data.get('multipart', None),
        )

    def build_config_endpoint(self, endpoint: dict, service: ConfigService = None) -> ConfigEndpoint:
        response = None
        if 'response' in endpoint:
            response = endpoint['response']
            if isinstance(response, dict):
                response = self.build_config_response(response, service=service)
            elif isinstance(response, str):
                response = ConfigResponse(body=self.build_config_external_file_path(response, service=service))
            elif isinstance(response, list):
                response = self.build_config_multi_response(response, service=service)
        else:
            response = ConfigResponse()

        return ConfigEndpoint(
            endpoint['path'],
            _id=endpoint.get('id', None),
            comment=endpoint.get('comment', None),
            method=endpoint.get('method', 'GET'),
            query_string=endpoint.get('queryString', {}),
            headers=endpoint.get('headers', {}),
            body=self.build_config_body(endpoint.get('body', None), service=service),
            dataset=self.build_config_dataset(endpoint.get('dataset', None), service=service),
            response=response,
            multi_responses_looped=endpoint.get('multiResponsesLooped', True),
            dataset_looped=endpoint.get('datasetLooped', True),
            performance_profile=endpoint.get('performanceProfile', None)
        )

    def build_config_http_service(self, service: dict, internal_service_id: Union[int, None] = None) -> ConfigHttpService:
        oas = self.build_config_external_file_path(service.get('oas', None))
        config_service = ConfigHttpService(
            service['port'],
            name=service.get('name', None),
            hostname=service.get('hostname', None),
            ssl=service.get('ssl', False),
            ssl_cert_file=service.get('sslCertFile', None),
            ssl_key_file=service.get('sslKeyFile', None),
            management_root=service.get('managementRoot', None),
            oas=oas,
            endpoints=[],
            performance_profile=service.get('performanceProfile', None),
            fallback_to=service.get('fallbackTo', None),
            internal_service_id=internal_service_id
        )

        if isinstance(oas, ConfigExternalFilePath):
            config_service.add_external_file_path(oas)

        config_service.endpoints = [self.build_config_endpoint(endpoint, service=config_service) for endpoint in service.get('endpoints', [])]

        return config_service

    def build_config_management(self, data: dict) -> Union[ConfigManagement, None]:
        config_management = None
        if 'management' in data:
            data_management = data['management']
            config_management = ConfigManagement(
                data_management['port'],
                ssl=data_management.get('ssl', False),
                ssl_cert_file=data_management.get('sslCertFile', None),
                ssl_key_file=data_management.get('sslKeyFile', None)
            )
        return config_management

    def build_config_globals(self, data: dict) -> Union[ConfigGlobals, None]:
        config_globals = None
        if 'globals' in data:
            data_globals = data['globals']
            config_globals = ConfigGlobals(
                headers=self.build_config_headers(data_globals),
                performance_profile=data_globals.get('performance_profile', None)
            )
        return config_globals

    def build_config_performance_profile(self, data: dict) -> ConfigPerformanceProfile:
        return ConfigPerformanceProfile(
            data['ratio'],
            data.get('delay', 0.0),
            data.get('faults', {})
        )

    def build_config_service(self, service: dict, internal_service_id: Union[int, None] = None) -> Union[ConfigHttpService, ConfigAsyncService]:
        _type = service.get('type', 'http')
        if _type == 'http':
            return self.build_config_http_service(service, internal_service_id)
        else:
            return self.build_config_async_service(service, internal_service_id)

    def build_config_root(self, data: dict) -> ConfigRoot:
        config_services = []
        for service in data['services']:
            config_services.append(self.build_config_service(service))
        config_management = self.build_config_management(data)
        config_templating_engine = data.get('templatingEngine', PYBARS)
        config_globals = self.build_config_globals(data)

        config_performance_profiles = {}
        if 'performanceProfiles' in data:
            config_performance_profiles = {}
            for key, value in data['performanceProfiles'].items():
                config_performance_profiles[key] = self.build_config_performance_profile(value)

        return ConfigRoot(
            config_services,
            management=config_management,
            templating_engine=config_templating_engine,
            _globals=config_globals,
            performance_profiles=config_performance_profiles
        )

    def build(self, data: dict) -> ConfigRoot:
        return self.build_config_root(data)
