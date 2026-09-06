import argparse
import importlib.util
import os
import tempfile
import unittest
from types import SimpleNamespace

from ikev2_const import (
    ANY,
    AUTH_HMAC_SHA1_96,
    CFG_REQUEST,
    D_H,
    ENCR,
    ENCR_AES_CBC,
    ENCR_NULL,
    IKE,
    INTEG,
    INTERNAL_IP4_ADDRESS,
    KEY_LENGTH,
    MODP_1024_bit,
    PRF,
    PRF_HMAC_SHA1,
    TS_IPV4_ADDR_RANGE,
)
from swu_config import (
    apply_config,
    apply_file_config,
    argparse_defaults,
    format_connected_event,
    load_config,
    normalize_log_level,
    parse_proposals,
    validate_device_identity,
)


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


class Proposals(unittest.TestCase):

    def test_parse_ike_ts_cp(self):
        parsed = parse_proposals({
            'ike_sa': [{
                'protocol': 'IKE',
                'spi_size': 0,
                'transforms': [
                    {'type': 'ENCR', 'id': 'ENCR_NULL'},
                    {'type': 'PRF', 'id': 'PRF_HMAC_SHA1'},
                    {'type': 'INTEG', 'id': 'AUTH_HMAC_SHA1_96'},
                    {'type': 'D_H', 'id': 'MODP_1024_bit'},
                ],
            }],
            'ts_initiator': [{
                'type': 'TS_IPV4_ADDR_RANGE',
                'protocol': 'ANY',
                'start_port': 0,
                'end_port': 65535,
                'start': '0.0.0.0',
                'end': '255.255.255.255',
            }],
            'cp': {
                'type': 'CFG_REQUEST',
                'attributes': ['INTERNAL_IP4_ADDRESS'],
            },
        })
        self.assertEqual(parsed['ike_sa'], [[
            [IKE, 0],
            [ENCR, ENCR_NULL],
            [PRF, PRF_HMAC_SHA1],
            [INTEG, AUTH_HMAC_SHA1_96],
            [D_H, MODP_1024_bit],
        ]])
        self.assertEqual(
            parsed['ts_initiator'],
            [[TS_IPV4_ADDR_RANGE, ANY, 0, 65535, '0.0.0.0', '255.255.255.255']],
        )
        self.assertEqual(parsed['cp'], [CFG_REQUEST, [INTERNAL_IP4_ADDRESS]])

    def test_key_length_and_unknown_id(self):
        parsed = parse_proposals({
            'ike_sa': [{
                'protocol': 'IKE',
                'spi_size': 0,
                'transforms': [
                    {'type': 'ENCR', 'id': 'ENCR_AES_CBC', 'key_length': 128},
                ],
            }],
        })
        self.assertEqual(parsed['ike_sa'][0][1], [ENCR, ENCR_AES_CBC, [KEY_LENGTH, 128]])
        with self.assertRaises(ValueError):
            parse_proposals({
                'ike_sa': [{
                    'protocol': 'IKE',
                    'spi_size': 0,
                    'transforms': [{'type': 'ENCR', 'id': 'ENCR_NOPE'}],
                }],
            })


@unittest.skipIf(importlib.util.find_spec('yaml') is None, 'PyYAML is not installed')
class SwuYaml(unittest.TestCase):

    def test_example_file_matches_builtin_ike_first_proposal(self):
        options = SimpleNamespace(
            destination_addr='1.2.3.4',
            imsi=None,
            headless=False,
        )
        proposals = apply_file_config(
            options,
            {'destination_addr': '1.2.3.4', 'imsi': None, 'headless': False},
            'swu.yaml',
        )
        self.assertEqual(options.destination_addr, '192.168.64.1')
        self.assertEqual(options.imsi, '001011234567890')
        self.assertTrue(options.headless)
        self.assertEqual(len(proposals['ike_sa']), 3)
        self.assertEqual(len(proposals['child_sa']), 7)
        self.assertEqual(proposals['ike_sa'][0], [
            [IKE, 0],
            [ENCR, ENCR_NULL],
            [PRF, PRF_HMAC_SHA1],
            [INTEG, AUTH_HMAC_SHA1_96],
            [D_H, MODP_1024_bit],
        ])
        self.assertEqual(proposals['cp'][0], CFG_REQUEST)


class LoggingAndArgparse(unittest.TestCase):

    def test_connected_event_line(self):
        self.assertEqual(
            format_connected_event('internet', '192.168.64.1', ['10.10.42.134'], []),
            'event=connected apn=internet dest=192.168.64.1 ipv4=10.10.42.134 ipv6=-',
        )

    def test_log_level(self):
        self.assertEqual(normalize_log_level('WARNING'), 'warning')
        self.assertEqual(normalize_log_level(None), 'info')
        with self.assertRaises(ValueError):
            normalize_log_level('trace')

    def test_argparse_defaults(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--imsi', dest='imsi')
        parser.add_argument('--headless', dest='headless', action='store_true', default=False)
        defaults = argparse_defaults(parser)
        self.assertIsNone(defaults['imsi'])
        self.assertFalse(defaults['headless'])


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
