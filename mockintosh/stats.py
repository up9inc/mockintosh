#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains server classes.
"""


class BaseStats:
    def __init__(self):
        self.parent = None
        self.children = []
        self.request_counter = 0
        self.response_codes = []
        self.response_times = []

    def increase_request_counter(self):
        self.request_counter += 1
        if not hasattr(self, 'parent'):
            return

        method = getattr(self.parent, "increase_request_counter", None)
        if callable(method):
            method()

    def json(self):
        data = {
            'request_counter': self.request_counter
        }

        if hasattr(self, 'endpoints'):
            data['endpoints'] = []
            for endpoint in self.endpoints:
                data['endpoints'].append(endpoint.json())

        return data

    def reset(self):
        self.request_counter = 0
        self.response_codes = []
        self.response_times = []

        if hasattr(self, 'children'):
            for child in self.children:
                child.reset()


class EndpointStats(BaseStats):
    def __init__(self):
        super().__init__()


class ServiceStats(EndpointStats):
    def __init__(self):
        self.endpoints = []
        super().__init__()

    def add_endpoint(self):
        endpoint_stats = EndpointStats()
        endpoint_stats.parent = self
        self.endpoints.append(endpoint_stats)


class Stats(ServiceStats):
    def __init__(self):
        self.services = []
        super().__init__()

    def add_service(self):
        service_stats = ServiceStats()
        service_stats.parent = self
        self.services.append(service_stats)

    def json(self):
        data = {
            'global': {
                'request_counter': self.request_counter
            },
            'services': []
        }

        for service in self.services:
            data['services'].append(service.json())

        return data
