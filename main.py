#!/bin/python3

import sys
from uuid import uuid4

from jinja2 import Template
from faker import Faker

fake = Faker()

def add_globals(template):
    template.globals['uuid'] = uuid4
    template.globals['fake'] = fake

def compile_definition(source):
    source_text = None
    with open(source, 'r') as file:
        source_text = file.read()
    template = Template(source_text)
    add_globals(template)
    result = template.render()
    return result


if __name__ == "__main__":
    source = sys.argv[1]
    definition = compile_definition(source)
    print(definition)
