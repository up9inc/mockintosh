#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains statistics tracking classes.
"""

from collections import Counter


class BaseStats:

    def __init__(self):
        self.parent = None
        self.children = None
        self.request_counter = 0
        self.status_code_distribution = Counter()
        self.total_resp_time = 0

    def increase_request_counter(self) -> None:
        self.request_counter += 1

        method = getattr(self.parent, "increase_request_counter", None)
        if callable(method):
            method()

    def add_request_elapsed_time(self, elapsed_time_in_seconds: int) -> None:
        self.total_resp_time += elapsed_time_in_seconds

        method = getattr(self.parent, "add_request_elapsed_time", None)
        if callable(method):
            method(elapsed_time_in_seconds)

    def add_status_code(self, status_code: int) -> None:
        self.status_code_distribution.update([status_code])

        method = getattr(self.parent, "add_status_code", None)
        if callable(method):
            method(status_code)

    def json(self) -> dict:
        data = {}

        if hasattr(self, 'hint'):
            data['hint'] = self.hint

        data.update({
            'request_counter': self.request_counter,
            'avg_resp_time': self.total_resp_time / self.request_counter if self.request_counter != 0 else 0,
            'status_code_distribution': dict(self.status_code_distribution)
        })

        if hasattr(self, 'endpoints'):
            data['endpoints'] = []
            for endpoint in self.endpoints:
                data['endpoints'].append(endpoint.json())

        return data

    def reset(self) -> None:
        self.request_counter = 0
        self.status_code_distribution = Counter()
        self.total_resp_time = 0

        if hasattr(self, 'services'):
            for child in self.services:
                child.reset()

        if hasattr(self, 'endpoints'):
            for child in self.endpoints:
                child.reset()


class EndpointStats(BaseStats):

    def __init__(self, hint: str):
        self.hint = hint
        super().__init__()


class ServiceStats(EndpointStats):

    def __init__(self, hint: str):
        self.endpoints = []
        super().__init__(hint)

    def add_endpoint(self, hint: str) -> None:
        endpoint_stats = EndpointStats(hint)
        endpoint_stats.parent = self
        self.endpoints.append(endpoint_stats)


class Stats(ServiceStats):

    def __init__(self):
        self.services = []
        super().__init__(None)

    def add_service(self, hint: str) -> None:
        service_stats = ServiceStats(hint)
        service_stats.parent = self
        self.services.append(service_stats)

    def update_service(self, index: int, hint: str) -> None:
        service_stats = self.services[index]
        service_stats.hint = hint
        service_stats.reset()

    def json(self) -> dict:
        data = {
            'global': {
                'request_counter': self.request_counter,
                'avg_resp_time': self.total_resp_time / self.request_counter if self.request_counter != 0 else 0,
                'status_code_distribution': dict(self.status_code_distribution)
            },
            'services': []
        }

        for service in self.services:
            data['services'].append(service.json())

        return data
