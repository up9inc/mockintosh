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
        self.response_codes = []
        self.avg_response_time_in_microseconds = 0

    def increase_request_counter(self):
        self.request_counter += 1
        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "increase_request_counter", None)
        if callable(method):
            method()

    def add_request_elapsed_time(self, elapsed_time_in_microseconds):
        self.avg_response_time_in_microseconds = (
            elapsed_time_in_microseconds + (
                self.avg_response_time_in_microseconds * self.request_counter
            )
        ) / (self.request_counter + 1)
        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "update_elapsed_time", None)
        if callable(method):
            method()

    def update_elapsed_time(self):
        if self.request_counter == 0:
            return

        total_elapsed_time = 0
        if hasattr(self, 'services'):
            for child in self.services:
                total_elapsed_time += child.avg_response_time_in_microseconds * child.request_counter
        if hasattr(self, 'endpoints'):
            for child in self.endpoints:
                total_elapsed_time += child.avg_response_time_in_microseconds * child.request_counter
        self.avg_response_time_in_microseconds = total_elapsed_time / self.request_counter

        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "update_elapsed_time", None)
        if callable(method):
            method()

    def json(self):
        data = {}

        if hasattr(self, 'identifier'):
            data['identifier'] = self.identifier

        data.update({
            'request_counter': self.request_counter,
            'avg_response_time_in_microseconds': self.avg_response_time_in_microseconds
        })

        if hasattr(self, 'endpoints'):
            data['endpoints'] = []
            for endpoint in self.endpoints:
                data['endpoints'].append(endpoint.json())

        return data

    def reset(self):
        self.request_counter = 0
        self.response_codes = []
        self.response_times = []

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
                'avg_response_time_in_microseconds': self.avg_response_time_in_microseconds
            },
            'services': []
        }

        for service in self.services:
            data['services'].append(service.json())

        return data
