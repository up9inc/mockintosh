#!/bin/python3

import sys
import json
from uuid import uuid4

from jinja2 import Template
from faker import Faker
import tornado.ioloop
import tornado.web


class Definition():
    def __init__(self, source):
        self.source = source
        self.compiled = None
        self.data = None
        self._compile()
        self.parse()

    def add_globals(self, template):
        fake = Faker()
        template.globals['uuid'] = uuid4
        template.globals['fake'] = fake

    def _compile(self):
        source_text = None
        with open(self.source, 'r') as file:
            source_text = file.read()
        template = Template(source_text)
        self.add_globals(template)
        self.compiled = template.render()

    def parse(self):
        self.data = json.loads(self.compiled)


class GenericHandler(tornado.web.RequestHandler):
    def initialize(self, response):
        self.response = response

    def get(self):
        self.write(self.response)


def make_app(endpoints):
    endpoint_handlers = []
    for endpoint in endpoints:
        endpoint_handlers.append(
            (endpoint['path'], GenericHandler, dict(response=endpoint['response']))
        )
    return tornado.web.Application(endpoint_handlers)


if __name__ == "__main__":
    source = sys.argv[1]
    definition = Definition(source)
    for service in definition.data['services']:
        app = make_app(service['endpoints'])
        app.listen(service['port'])
    tornado.ioloop.IOLoop.current().start()
