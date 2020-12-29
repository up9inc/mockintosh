#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: module that contains common methods.
"""

import sys
import io
import re
import logging
import tempfile
from contextlib import contextmanager

from mockintosh.constants import PYBARS, JINJA, SHORT_JINJA, JINJA_VARNAME_DICT, SPECIAL_CONTEXT

from OpenSSL import crypto


def _safe_path_split(path):
    return re.split(r'/(?![^{{}}]*}})', path)


def _to_camel_case(snake_case):
    components = snake_case.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _detect_engine(data, context='config', default=PYBARS):
    template_engine = default
    if 'templatingEngine' in data and (
        data['templatingEngine'].lower() in (JINJA.lower(), SHORT_JINJA)
    ):
        template_engine = JINJA
    logging.debug('Templating engine (%s) is: %s' % (context, template_engine))
    return template_engine


def _handlebars_add_regex_context(context, scope, key, regex, *args):
    _type = 'regex'
    if SPECIAL_CONTEXT not in context:
        context[SPECIAL_CONTEXT] = {}
    if scope not in context[SPECIAL_CONTEXT]:
        context[SPECIAL_CONTEXT][scope] = {}
    context[SPECIAL_CONTEXT][scope][key] = {
        'type': _type,
        'regex': regex,
        'args': args
    }


def _jinja_add_regex_context(context, scope, key, regex, *args):
    _type = 'regex'
    if SPECIAL_CONTEXT not in context.environment.globals:
        context.environment.globals[SPECIAL_CONTEXT] = {}
    if scope not in context.environment.globals[SPECIAL_CONTEXT]:
        context.environment.globals[SPECIAL_CONTEXT][scope] = {}
    context.environment.globals[SPECIAL_CONTEXT][scope][key] = {
        'type': _type,
        'regex': regex,
        'args': args
    }


def _jinja_add_varname(context, varname):
    if JINJA_VARNAME_DICT not in context.environment.globals:
        context.environment.globals[JINJA_VARNAME_DICT] = {}
    context.environment.globals[JINJA_VARNAME_DICT][varname] = None


@contextmanager
def _nostderr():
    """Method to suppress the standard error. (use it with `with` statements)
    """
    save_stderr = sys.stderr
    sys.stderr = io.StringIO()
    yield
    sys.stderr = save_stderr


def _import_from(module, name):
    module = __import__(module, fromlist=[name])
    return getattr(module, name)


def _cert_gen(
    email_address="info@example.com",
    hostname="example.com",
    country_name="US",
    locality_name="Example",
    state_or_province_name="Example",
    organization_name="Example",
    organization_unit_name="Example",
    serial_number=0,
    validity_start_in_seconds=0,
    validity_end_in_seconds=10 * 365 * 24 * 60 * 60,
    key_file=None,
    cert_file=None
):
    key_file = tempfile.mktemp() if key_file is None else key_file
    cert_file = tempfile.mktemp() if cert_file is None else cert_file

    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    cert = crypto.X509()
    cert.get_subject().C = country_name
    cert.get_subject().ST = state_or_province_name
    cert.get_subject().L = locality_name
    cert.get_subject().organizationName = organization_name
    cert.get_subject().OU = organization_unit_name
    cert.get_subject().CN = hostname
    cert.get_subject().emailAddress = email_address
    cert.set_serial_number(serial_number)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(validity_end_in_seconds)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')

    with open(cert_file, "w") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(key_file, "w") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))

    return cert_file, key_file
