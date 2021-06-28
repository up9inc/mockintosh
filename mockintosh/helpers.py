#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains helper methods.
"""

import sys
import io
import re
import time
import json
import logging
from contextlib import contextmanager
from base64 import b64encode
from urllib.parse import _coerce_args, SplitResult, _splitnetloc, scheme_chars
from typing import (
    Tuple,
    Callable,
    Union
)

from mockintosh.constants import PYBARS, JINJA, SHORT_JINJA, JINJA_VARNAME_DICT, SPECIAL_CONTEXT


def _safe_path_split(path: str) -> list:
    return re.split(r'/(?![^{{}}]*}})', path)


def _to_camel_case(snake_case: str) -> str:
    components = snake_case.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _detect_engine(obj: Union[object, dict], context: str = 'config', default: str = PYBARS) -> str:
    template_engine = default
    if isinstance(obj, dict):
        if 'templatingEngine' in obj and (
            obj['templatingEngine'].lower() in (JINJA.lower(), SHORT_JINJA)
        ):
            template_engine = JINJA
    else:
        if obj.templating_engine.lower() in (JINJA.lower(), SHORT_JINJA):
            template_engine = JINJA
    logging.debug('Templating engine (%s) is: %s', context, template_engine)
    return template_engine


def _handlebars_add_to_context(context: dict, scope: str, key: str, value) -> None:
    if SPECIAL_CONTEXT not in context:
        context[SPECIAL_CONTEXT] = {}
    if scope not in context[SPECIAL_CONTEXT]:
        context[SPECIAL_CONTEXT][scope] = {}
    context[SPECIAL_CONTEXT][scope][key] = value


def _jinja_add_to_context(context: dict, scope: str, key: str, value) -> None:
    if SPECIAL_CONTEXT not in context.environment.globals:
        context.environment.globals[SPECIAL_CONTEXT] = {}
    if scope not in context.environment.globals[SPECIAL_CONTEXT]:
        context.environment.globals[SPECIAL_CONTEXT][scope] = {}
    context.environment.globals[SPECIAL_CONTEXT][scope][key] = value


def _jinja_add_varname(context: dict, varname: str) -> None:
    context.environment.globals[JINJA_VARNAME_DICT][varname] = None


@contextmanager
def _nostderr() -> None:
    """Method to suppress the standard error. (use it with `with` statements)
    """
    save_stderr = sys.stderr
    sys.stderr = io.StringIO()
    yield
    sys.stderr = save_stderr


def _import_from(module: str, name: str) -> Callable:
    module = __import__(module, fromlist=[name])
    return getattr(module, name)


def _b64encode(s: bytes) -> str:
    return b64encode(s).decode()


def _urlsplit_scheme(url: str, i: int) -> Tuple[str, str]:
    for c in url[:i]:
        if c not in scheme_chars:  # pragma: no cover
            break  # https://github.com/nedbat/coveragepy/issues/198
    else:
        scheme, url = url[:i].lower(), url[i + 1:]
    return scheme, url


def _urlsplit_netloc(url: str) -> Tuple[str, str]:
    netloc, url = _splitnetloc(url, 2)
    if (
        ('[' in netloc and ']' not in netloc)
        or  # noqa: W504, W503
        (']' in netloc and '[' not in netloc)
    ):
        raise ValueError("Invalid IPv6 URL")
    return netloc, url


def _urlsplit_fragment(url: str) -> Tuple[str, str]:
    result = re.split(r'#(?![^{{}}]*}})', url, maxsplit=1)
    url = result[0]
    fragment = ''
    if len(result) > 1:
        fragment = result[1]
    return fragment, url


def _urlsplit_query(url: str) -> Tuple[str, str]:
    result = re.split(r'\?(?![^{{}}]*}})', url, maxsplit=1)
    url = result[0]
    query = ''
    if len(result) > 1:
        query = result[1]
    return query, url


def _urlsplit(url: str, scheme: str = '', allow_fragments: bool = True):
    """Templating safe version of urllib.parse.urlsplit

    Ignores '?' and '#' inside {{}} templating tags.

    Caching disabled.
    """

    url, scheme, _coerce_result = _coerce_args(url, scheme)
    allow_fragments = bool(allow_fragments)
    netloc = query = fragment = ''
    i = url.find(':')
    if i > 0:
        scheme, url = _urlsplit_scheme(url, i)

    if url[:2] == '//':
        netloc, url = _urlsplit_netloc(url)

    if allow_fragments and '#' in url:
        fragment, url = _urlsplit_fragment(url)

    if '?' in url:
        query, url = _urlsplit_query(url)

    v = SplitResult(scheme, netloc, url, query, fragment)
    return _coerce_result(v)


def _delay(seconds: int) -> None:
    logging.debug('Sleeping for %d seconds.', seconds)
    time.sleep(seconds)


def _serialize_header_value(val):
    if not isinstance(val, str):
        return json.dumps(val)
    return val
