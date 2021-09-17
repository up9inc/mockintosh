import tempfile
import unittest

from mockintosh.__main__ import main


class CLITests(unittest.TestCase):
    def test_empty(self):
        with self.assertRaises(SystemExit):
            main([])

    def test_sample_config(self):
        main(["--sample-config", tempfile.mktemp()])

    def test_oas_conversion(self):
        pass

    def test_oas_serving(self):
        pass

    def test_config_serving(self):
        pass
