#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
.. module:: __init__
    :synopsis: Contains classes that tests the exceptions thrown by the mock server.
"""

import sys
import pytest
from jsonschema.exceptions import ValidationError

from mockintosh import Definition, get_schema
from mockintosh.exceptions import UnrecognizedConfigFileFormat, CertificateLoadingError
from mockintosh.servers import HttpServer, TornadoImpl
from mockintosh.methods import _nostderr
from utilities import get_config_path

schema = get_schema()


class TestExceptions():

    def test_file_not_found_error(self):
        config = 'configs/not_existing_file'
        with pytest.raises(FileNotFoundError, match=r"No such file or directory:"):
            Definition(get_config_path(config), schema)

    @pytest.mark.parametrize(('config'), [
        'configs/empty.json',
        'configs/empty.yaml'
    ])
    def test_json_schema_validation_error(self, config):
        with pytest.raises(ValidationError, match=r".*"):
            Definition(get_config_path(config), schema)

    def test_unrecognized_config_file_format_error(self):
        config = 'configs/invalid'
        with pytest.raises(
            UnrecognizedConfigFileFormat,
            match=r"Configuration file is neither a JSON file nor a YAML file!"
        ):
            Definition(get_config_path(config), schema)

    def test_certificate_loading_error(self):
        config = 'configs/missing_ssl_cert_file.json'
        with pytest.raises(
            CertificateLoadingError,
            match=r"Certificate loading error: File not found on path `missing_dir/cert.pem`"
        ):
            definition = Definition(get_config_path(config), schema)
            HttpServer(
                definition,
                TornadoImpl()
            )

    def test_nostderr(self):
        with _nostderr():
            sys.stderr.write('don\'t print this')
