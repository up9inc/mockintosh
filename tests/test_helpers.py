#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests the helpers.
"""

import pytest

from mockintosh import start_render_queue
from mockintosh.helpers import _urlsplit
from mockintosh.j2.methods import env
from mockintosh.constants import JINJA
from mockintosh.config import (
    ConfigAsyncService
)


class TestHelpers():

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
