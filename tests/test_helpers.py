#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests the helpers.
"""
import logging
import re
import unittest
import uuid

import graphql
import pytest

from mockintosh import start_render_queue
from mockintosh.config import (
    ConfigAsyncService
)
from mockintosh.constants import JINJA, PYBARS
from mockintosh.hbs.methods import reg_ex
from mockintosh.helpers import _urlsplit
from mockintosh.j2.methods import env
from mockintosh.templating import RenderingTask


class TestHelpers:

    def test_urlsplit(self):
        scheme, netloc, path, query, fragment = _urlsplit('https://example.com/path/resource.txt?a=b&c=d#fragment')
        assert scheme == 'https'
        assert netloc == 'example.com'
        assert path == '/path/resource.txt'
        assert query == 'a=b&c=d'
        assert fragment == 'fragment'

    def test_invalid_ipv6(self):
        with pytest.raises(ValueError, match=r"Invalid IPv6 URL"):
            _urlsplit('https://[::1/path/resource.txt?a=b&c=d#fragment')

    def test_jinja_env_helper(self):
        assert env('TESTING_ENV', 'someothervalue') == 'somevalue'
        assert env('TESTING_NOT_ENV', 'someothervalue') == 'someothervalue'

        queue, job = start_render_queue()

        config_async_service = ConfigAsyncService(
            'kafka',
            "{{env('TESTING_ENV', 'someothervalue')}}"
        )
        config_async_service.address_template_renderer(
            JINJA,
            queue
        )
        assert config_async_service.address == 'somevalue'

        config_async_service = ConfigAsyncService(
            'kafka',
            "{{env('TESTING_NOT_ENV', 'someothervalue')}}"
        )
        config_async_service.address_template_renderer(
            JINJA,
            queue
        )
        assert config_async_service.address == 'someothervalue'

        job.kill()


class TemplateMapper(object):
    matches = {}

    def __call__(self, match):
        new_id = '_' + str(uuid.uuid4()).replace('-', '')
        self.matches[new_id] = match.group(0)
        return new_id


def graphql_match(query, template):
    query = graphql.parse(query)
    query = graphql.print_ast(query).strip()
    logging.info("Normalized query:\n%s", query)

    mapper = TemplateMapper()
    template = re.sub(r'({{[^{}]*}})', mapper, template)
    logging.info("Template after replace:\n%s", template)

    template = graphql.parse(template)
    template = graphql.print_ast(template).strip()
    logging.info("Template after normalized:\n%s", template)

    template = '^' + re.escape(template) + '$'

    for k, v in mapper.matches.items():
        template = template.replace(k, v)

    template = template.replace("\\ ", " ")
    template = template.replace("\\\n", "\n")

    logging.info("Template after render:\n%s", template)

    return re.match(template, query)


class TestGraphQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        logging.basicConfig(level=logging.DEBUG, format='[%(relativeCreated)d %(name)s %(levelname)s] %(message)s')

    def test_1(self):
        query = """
        query HeroNameAndFriends {
            hero(
                    where: {name: {_eq: "hello"}, _and: {age: {_gt: 3}}}
                ) {
                    name
                    age
                    friends {      name    }
            }
        }
        """

        template = r"""
        query HeroNameAndFriends {
            hero(
                    where: {name: {_eq: "{{regEx '.+'}}"}, _and: {age: {_gt: {{regEx '.+'}}}}}
                ) {
                    name
                    age
                    friends { name }
            }
        }
        """

        self.assertTrue(graphql_match(query, query))

        self.assertTrue(graphql_match(query, template))

    def test_2(self):
        query = """
        {
            hero(
                    where: {name: {_eq: "hello"}}
                )
        }
        """
        template = """
        {
            hero(
                    where: {
                        name: {_eq: "{{regEx '.+'}}"}
                    }
                )
        }
        """
        self.assertTrue(graphql_match(query, template))

    def test_3(self):
        query = """
              { 
                      userIdentify: user(user_id: "deadbeef-6c86-4ee0-97b3-12ef2e530c6f") {
                        identity(aliases: [{id: "435345", tag: "sometag", priority: 2}]) {
                          identify {
                            id
                          }
                        }
                      }
                     
                      userEvents: user(user_id: "deadbeef-6c86-4ee0-97b3-12ef2e530c6f") {
                        events(from: "2021-07-18T18:37:24.584Z") {
                          id
                          name
                          time
                          session_id
                          view_id
                          properties
                        }
                      }
                     }
                             """
        template = """
            {
              userIdentify: user(user_id: "{{regEx '.*' 'str_1'}}") {
                identity(aliases: [{
                    id: "{{regEx '.*' 'str_2'}}", 
                    tag: "{{regEx '.*' 'str_3'}}", 
                    priority: {{regEx '.*' 'int_4'}}
                    }]) {
                  identify {
                    id
                  }
                }
              }
              userEvents: user(user_id: "{{regEx '.*' 'str_5'}}") {
                events(from: "{{regEx '.*' 'str_6'}}") {
                  id
                  name
                  time
                  session_id
                  view_id
                  properties
                }
              }
            }
        """
        self.assertTrue(graphql_match(query, template))
