import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_config import default_api_key,load_agent_config,api_options


class AgentCredentialTests(unittest.TestCase):
    def test_defaults_repair_empty_fields_and_preserve_remote_settings(self):
        with TemporaryDirectory() as folder:
            folder=Path(folder);defaults=folder/'defaults.json';saved=folder/'config.json'
            profile=dict(base_url='http://127.0.0.1:8646/v1',model='qoder-deepseek-flash',timeout=120,
                         default_key_file=str(folder/'key'),default_key_endpoint='http://127.0.0.1:8646/v1/chat/completions')
            defaults.write_text(json.dumps(profile),encoding='utf-8')
            self.assertEqual(load_agent_config(saved,defaults)['model'],profile['model'])
            saved.write_text(json.dumps(dict(base_url=profile['base_url'],model='')),encoding='utf-8-sig')
            config=load_agent_config(saved,defaults)
            self.assertEqual(config['model'],profile['model'])
            self.assertEqual(set(api_options(config)),{'base_url','model','timeout','max_rounds','strict'})
            saved.write_text(json.dumps(dict(base_url='https://example.com/v1',model='remote')),encoding='utf-8')
            config=load_agent_config(saved,defaults)
            self.assertEqual(config['model'],'remote');self.assertNotIn('default_key_file',config)
            saved.write_text('{broken',encoding='utf-8')
            self.assertEqual(load_agent_config(saved,defaults)['model'],profile['model'])

    def test_bound_local_key_and_rotation(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'bridge-key'
            config = dict(base_url='http://127.0.0.1:8646/v1', default_key_file=str(path),
                          default_key_endpoint='http://127.0.0.1:8646/v1/chat/completions')
            self.assertEqual(default_api_key(config), '')
            path.write_text('test-key-one\n', encoding='utf-8')
            self.assertEqual(default_api_key(config), 'test-key-one')
            path.write_text('test-key-two', encoding='utf-8')
            self.assertEqual(default_api_key(config), 'test-key-two')
            for base in ('https://example.com/v1', 'http://127.0.0.1:9999/v1',
                         'http://127.0.0.1:8646/other', 'invalid'):
                self.assertEqual(default_api_key({**config, 'base_url': base}), '')
            remote = 'https://example.com/v1/chat/completions'
            self.assertEqual(default_api_key({**config, 'base_url': remote, 'default_key_endpoint': remote}), '')

    def test_invalid_credential_is_ignored(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'bridge-key'
            config = dict(base_url='http://localhost:8646/v1', default_key_file=str(path),
                          default_key_endpoint='http://localhost:8646/v1/chat/completions')
            for content in ('', 'one\ntwo', 'x' * 17000):
                path.write_text(content, encoding='utf-8')
                self.assertEqual(default_api_key(config), '')
            self.assertEqual(default_api_key({**config, 'default_key_file': 'relative-file'}), '')
            self.assertEqual(default_api_key({}), '')


if __name__ == '__main__':
    unittest.main()
