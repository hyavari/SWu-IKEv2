import importlib.util
import os
import tempfile
import unittest

from swu_config import apply_config, load_config, validate_device_identity


@unittest.skipIf(importlib.util.find_spec('yaml') is None, 'PyYAML is not installed')
class LoadConfig(unittest.TestCase):

    def _write(self, text):
        handle = tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False)
        try:
            handle.write(text)
            handle.close()
            return handle.name
        except Exception:
            os.unlink(handle.name)
            raise

    def tearDown(self):
        path = getattr(self, '_path', None)
        if path and os.path.exists(path):
            os.unlink(path)

    def test_quoted_subscriber_fields(self):
        self._path = self._write(
            'imsi: "001011234567890"\n'
            'ki: "000102030405060708090a0b0c0d0e0f"\n'
            'headless: true\n'
        )
        data = load_config(self._path)
        self.assertEqual(data['imsi'], '001011234567890')
        self.assertEqual(data['ki'], '000102030405060708090a0b0c0d0e0f')
        self.assertTrue(data['headless'])

    def test_unquoted_imsi_is_rejected(self):
        self._path = self._write('imsi: 1011234567890\n')
        with self.assertRaises(ValueError):
            load_config(self._path)

    def test_unknown_key_is_rejected(self):
        self._path = self._write('foo: bar\n')
        with self.assertRaises(ValueError):
            load_config(self._path)


class ApplyConfig(unittest.TestCase):

    def test_yaml_fills_defaults_cli_wins(self):
        defaults = {'imsi': None, 'headless': False, 'destination_addr': '1.2.3.4'}
        values = dict(defaults)
        values['destination_addr'] = '9.9.9.9'
        merged = apply_config(
            values,
            defaults,
            {'imsi': '001011234567890', 'headless': True, 'dest': '192.168.64.1'},
        )
        self.assertEqual(merged['imsi'], '001011234567890')
        self.assertTrue(merged['headless'])
        self.assertEqual(merged['destination_addr'], '9.9.9.9')


class DeviceIdentity(unittest.TestCase):

    def test_accepts_none_and_valid(self):
        self.assertEqual(validate_device_identity(None, None), (None, None))
        self.assertEqual(
            validate_device_identity('123456789012347', '1234567890123456'),
            ('123456789012347', '1234567890123456'),
        )

    def test_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            validate_device_identity('123', None)
        with self.assertRaises(ValueError):
            validate_device_identity(None, '123')


if __name__ == '__main__':
    unittest.main()
