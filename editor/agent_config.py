"""Read a user-configured local Bridge credential without copying it to settings."""
from pathlib import Path
import json
import sys
from urllib.parse import urlsplit
from agent_client import endpoint

API_FIELDS = ('base_url', 'model', 'timeout', 'max_rounds', 'strict')
BASE_CONFIG = dict(base_url='https://api.openai.com/v1', model='', timeout=45, max_rounds=8, strict=True)


def _settings(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):return {}
        result = {}
        for name in ('base_url','model','default_key_file','default_key_endpoint'):
            if isinstance(data.get(name), str) and len(data[name]) <= 2048:result[name] = data[name]
        for name, low, high in (('timeout',5,120),('max_rounds',1,12)):
            if type(data.get(name)) is int and low <= data[name] <= high:result[name] = data[name]
        if type(data.get('strict')) is bool:result['strict'] = data['strict']
        return result
    except (OSError, ValueError, TypeError):return {}


def load_agent_config(path, defaults_path=None):
    if defaults_path is None:
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        defaults_path = root / 'agent-defaults.json'
    defaults = _settings(defaults_path)
    saved = _settings(path)
    try:
        if saved.get('base_url') and endpoint(saved['base_url']) != endpoint(defaults.get('base_url','')):
            defaults = {}
    except ValueError:defaults = {}
    config = {**BASE_CONFIG, **defaults, **saved}
    if defaults:
        for name in ('model','default_key_file','default_key_endpoint'):
            if not config.get(name) and defaults.get(name):config[name] = defaults[name]
    return config


def api_options(config):
    return {name:config[name] for name in API_FIELDS}


def default_api_key(config):
    try:
        current = endpoint(config['base_url'])
        bound = config.get('default_key_endpoint', '')
        if current != bound or urlsplit(current).hostname not in ('localhost', '127.0.0.1', '::1'):
            return ''
        path = Path(config.get('default_key_file', '')).expanduser()
        if not path.is_absolute():
            return ''
        with path.open(encoding='utf-8-sig') as source:
            key = source.read(16385).strip()
        if not key or len(key) > 16384 or '\r' in key or '\n' in key:
            return ''
        return key
    except (OSError, ValueError, TypeError, KeyError):
        return ''
