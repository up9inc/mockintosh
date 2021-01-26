#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains server classes.
"""


class BaseStats:
    def __init__(self):
        self.parent = None
        self.children = None
        self.request_counter = 0
        self.status_code_distribution = {}
        self.total_resp_time = 0

    def increase_request_counter(self):
        self.request_counter += 1
        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "increase_request_counter", None)
        if callable(method):
            method()

    def add_request_elapsed_time(self, elapsed_time_in_seconds):
        self.total_resp_time += elapsed_time_in_seconds
        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "add_request_elapsed_time", None)
        if callable(method):
            method(elapsed_time_in_seconds)

    def add_status_code(self, status_code):
        if status_code not in self.status_code_distribution:
            self.status_code_distribution[status_code] = 1
        else:
            self.status_code_distribution[status_code] += 1
        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "add_status_code", None)
        if callable(method):
            method(status_code)

    def json(self):
        data = {}

        if hasattr(self, 'identifier'):
            data['identifier'] = self.identifier

        data.update({
            'request_counter': self.request_counter,
            'avg_resp_time': self.total_resp_time / self.request_counter if self.request_counter != 0 else 0,
            'status_code_distribution': self.status_code_distribution
        })

        if hasattr(self, 'endpoints'):
            data['endpoints'] = []
            for endpoint in self.endpoints:
                data['endpoints'].append(endpoint.json())

        return data

    def reset(self):
        self.request_counter = 0
        self.status_code_distribution = {}
        self.total_resp_time = 0

        if hasattr(self, 'services'):
            for child in self.services:
                child.reset()

        if hasattr(self, 'endpoints'):
            for child in self.endpoints:
                child.reset()


class EndpointStats(BaseStats):
    def __init__(self, identifier):
        self.identifier = identifier
        super().__init__()


class ServiceStats(EndpointStats):
    def __init__(self, identifier):
        self.endpoints = []
        super().__init__(identifier)

    def add_endpoint(self, identifier):
        endpoint_stats = EndpointStats(identifier)
        endpoint_stats.parent = self
        self.endpoints.append(endpoint_stats)


class Stats(ServiceStats):
    def __init__(self):
        self.services = []
        super().__init__(None)

    def add_service(self, identifier):
        service_stats = ServiceStats(identifier)
        service_stats.parent = self
        self.services.append(service_stats)

    def json(self):
        data = {
            'global': {
                'request_counter': self.request_counter,
                'avg_resp_time': self.total_resp_time / self.request_counter if self.request_counter != 0 else 0,
                'status_code_distribution': self.status_code_distribution
            },
            'services': []
        }

        for service in self.services:
            data['services'].append(service.json())

        return data
