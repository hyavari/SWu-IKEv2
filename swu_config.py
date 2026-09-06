try:
    import yaml
except ImportError:
    yaml = None

# YAML keys match CLI long options (underscores instead of dashes).
CONFIG_TO_ATTR = {
    'modem': 'modem',
    'source': 'source_addr',
    'dest': 'destination_addr',
    'apn': 'apn',
    'gateway_ip_address': 'gateway_ip_address',
    'imsi': 'imsi',
    'mcc': 'mcc',
    'mnc': 'mnc',
    'ki': 'ki',
    'op': 'op',
    'opc': 'opc',
    'netns': 'netns',
    'sqn': 'sqn',
    'no_default_route': 'no_default_route',
    'no_dns': 'no_dns',
    'export_keys': 'export_keys',
    'headless': 'headless',
    'imei': 'imei',
    'imeisv': 'imeisv',
}

BOOL_KEYS = frozenset(('no_default_route', 'no_dns', 'headless'))
QUOTED_STRING_KEYS = frozenset((
    'imsi', 'ki', 'op', 'opc', 'imei', 'imeisv', 'sqn', 'mcc', 'mnc',
))


def load_config(path):
    if yaml is None:
        raise ImportError('PyYAML is not installed. Re-run ./install_deps.sh')
    with open(path) as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError('config file must be a YAML mapping')
    unknown = sorted(set(data) - set(CONFIG_TO_ATTR))
    if unknown:
        raise ValueError('unknown config keys: ' + ', '.join(unknown))
    for key, value in data.items():
        if key in BOOL_KEYS:
            if not isinstance(value, bool):
                raise ValueError(key + ' must be true or false')
        elif key in QUOTED_STRING_KEYS and value is not None and not isinstance(value, str):
            raise ValueError(key + ' must be a quoted string so leading zeros are kept')
        elif value is not None and not isinstance(value, (str, bool)):
            data[key] = str(value)
    return data


def apply_config(values, defaults, config):
    """Fill values from config where the current value is still the parser default."""
    out = dict(values)
    for yaml_key, attr in CONFIG_TO_ATTR.items():
        if yaml_key not in config:
            continue
        if out.get(attr) == defaults.get(attr):
            out[attr] = config[yaml_key]
    return out


def apply_file_config(options, defaults, path):
    merged = apply_config(vars(options), defaults, load_config(path))
    for attr, value in merged.items():
        setattr(options, attr, value)
    return options


def validate_device_identity(imei, imeisv):
    if imei is not None and (len(imei) != 15 or not imei.isdigit()):
        raise ValueError('--imei must be 15 digits')
    if imeisv is not None and (len(imeisv) != 16 or not imeisv.isdigit()):
        raise ValueError('--imeisv must be 16 digits')
    return imei, imeisv
