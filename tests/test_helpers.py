#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests the helpers.
"""

from mockintosh.methods import _urlsplit


class TestHelpers():

    def test_urlsplit(self):
        scheme, netloc, path, query, fragment = _urlsplit('https://example.com/path/resource.txt?a=b&c=d#fragment')
        assert scheme == 'https'
        assert netloc == 'example.com'
        assert path == '/path/resource.txt'
        assert query == 'a=b&c=d'
        assert fragment == 'fragment'
