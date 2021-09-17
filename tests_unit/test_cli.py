import logging
import tempfile
import unittest
from os import path

import mockintosh
from mockintosh.__main__ import main

__location__ = path.abspath(path.dirname(__file__))

logging.basicConfig(level=logging.DEBUG)


class CLITests(unittest.TestCase):
    def test_empty(self):
        with self.assertRaises(SystemExit):
            main([])

    def test_sample_config(self):
        main(["--sample-config", tempfile.mktemp()])

    def test_oas_conversion(self):
        main(["--convert=%s" % tempfile.mktemp(), __location__ + "/../tests_integrated/subdir/oas.json"])

    def test_oas_serving(self):
        main([__location__ + "/tests_integrated/subdir/oas.json"])

    def test_config_serving(self):
        main([mockintosh.__location__ + "/res/sample.yml"])
