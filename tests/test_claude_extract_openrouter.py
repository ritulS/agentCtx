"""claude_extract with MSWEA_EXTRACT_PROVIDER=openrouter: only the API call changes.
Run: venv/bin/python -m unittest tests/test_claude_extract_openrouter.py -v
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / 'src'):
    sys.path.insert(0, str(entry))

from agentctx.compression import claude_extract                       # noqa: E402
from agentctx.compression import primitives as mem                    # noqa: E402

OR_SETTINGS = {'provider': 'openrouter', 'model': 'vendor/model', 'effort': 'low', 'max_tokens': 10,
               'timeout_s': 1.0, 'fallbacks': False, 'base_url': 'https://openrouter.ai/api/v1'}


class FakeCompletion:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


class FakeOpenAI:
    """Records the create() kwargs and returns the scripted completion."""
    def __init__(self, completion):
        self.calls = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)
        self._completion = completion

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._completion


class SettingsTest(unittest.TestCase):
    def test_default_provider_is_anthropic(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('MSWEA_EXTRACT_PROVIDER', None)
            self.assertEqual(claude_extract.extract_settings()['provider'], 'anthropic')
            self.assertEqual(claude_extract.extract_model_info()['provider'], 'anthropic')

    def test_openrouter_requires_model(self):
        with patch.dict(os.environ, {'MSWEA_EXTRACT_PROVIDER': 'openrouter'}):
            os.environ.pop('MSWEA_EXTRACT_MODEL', None)
            with self.assertRaises(ValueError):
                claude_extract.extract_settings()
            self.assertIn('error', claude_extract.extract_model_info())

    def test_openrouter_settings(self):
        env = {'MSWEA_EXTRACT_PROVIDER': 'openrouter', 'MSWEA_EXTRACT_MODEL': 'qwen/qwen3.5-397b-a17b',
               'MSWEA_EXTRACT_EFFORT': 'none', 'MSWEA_EXTRACT_FALLBACKS': '1'}
        with patch.dict(os.environ, env):
            s = claude_extract.extract_settings()
        self.assertEqual(s['provider'], 'openrouter')
        self.assertEqual(s['model'], 'qwen/qwen3.5-397b-a17b')
        self.assertEqual(s['effort'], 'none')            # openrouter-only value accepted
        self.assertFalse(s['fallbacks'])                 # Anthropic beta: forced off
        self.assertEqual(s['base_url'], claude_extract.DEFAULT_OPENROUTER_BASE_URL)

    def test_anthropic_rejects_openrouter_only_effort(self):
        with patch.dict(os.environ, {'MSWEA_EXTRACT_PROVIDER': 'anthropic', 'MSWEA_EXTRACT_EFFORT': 'none'}):
            with self.assertRaises(ValueError):
                claude_extract.extract_settings()

    def test_openrouter_key_lookup(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'sk-or-x', 'ANTHROPIC_API_KEY': 'sk-ant-y'}):
            self.assertEqual(claude_extract.resolve_api_key('openrouter'), 'sk-or-x')
            self.assertEqual(claude_extract.resolve_api_key(), 'sk-ant-y')


class RequestTest(unittest.TestCase):
    def test_openrouter_request_keeps_blocks_and_breakpoints(self):
        model = claude_extract.ClaudeExtractModel(settings=OR_SETTINGS, client=object())
        blocks = [{'type': 'text', 'text': 'A'}, {'type': 'text', 'text': 'B', 'cache_control': {'type': 'ephemeral'}},
                  {'type': 'text', 'text': 'C'}]
        request = model._request([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': blocks}])
        self.assertEqual(request['model'], 'vendor/model')
        self.assertEqual(request['max_tokens'], 10)
        self.assertEqual(request['messages'][0],
                         {'role': 'system', 'content': [{'type': 'text', 'text': 'S', 'cache_control': {'type': 'ephemeral'}}]})
        self.assertEqual(request['messages'][1], {'role': 'user', 'content': blocks})
        self.assertIsNot(request['messages'][1]['content'][1], blocks[1])   # copied, not aliased
        self.assertEqual(request['extra_body'], {'reasoning': {'effort': 'low'}})
        for key in ('system', 'thinking', 'output_config', 'betas'):       # Anthropic-only fields absent
            self.assertNotIn(key, request)

    def test_anthropic_request_unchanged(self):
        settings = {**OR_SETTINGS, 'provider': 'anthropic', 'model': 'm'}
        model = claude_extract.ClaudeExtractModel(settings=settings, client=object())
        request = model._request([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'U'}])
        self.assertEqual(request['system'], [{'type': 'text', 'text': 'S', 'cache_control': {'type': 'ephemeral'}}])
        self.assertEqual(request['messages'], [{'role': 'user', 'content': 'U'}])
        self.assertEqual(request['thinking'], {'type': 'adaptive'})


class ResponseTest(unittest.TestCase):
    COMPLETION = {
        'id': 'gen-123', 'model': 'vendor/model', 'provider': 'Vendor',
        'choices': [{'finish_reason': 'stop', 'native_finish_reason': 'end_turn',
                     'message': {'role': 'assistant', 'content': 'keep m00003\nnone', 'reasoning': 'because'}}],
        'usage': {'prompt_tokens': 1000, 'completion_tokens': 20, 'cost': 0.0012,
                  'prompt_tokens_details': {'cached_tokens': 700, 'cache_write_tokens': 100},
                  'completion_tokens_details': {'reasoning_tokens': 15}},
    }

    def test_openrouter_response_maps_to_openai_shape(self):
        client = FakeOpenAI(FakeCompletion(self.COMPLETION))
        model = claude_extract.ClaudeExtractModel(settings=OR_SETTINGS, client=client)
        reply = model.query([{'role': 'system', 'content': 'S'}, {'role': 'user', 'content': 'U'}])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]['model'], 'vendor/model')
        self.assertEqual(reply['role'], 'assistant')
        self.assertEqual(reply['content'], 'keep m00003\nnone')
        resp = reply['extra']['response']
        self.assertEqual(resp['id'], 'gen-123')
        self.assertEqual(resp['provider'], 'Vendor')
        self.assertEqual(resp['stop_reason'], 'end_turn')
        self.assertEqual(resp['choices'][0]['finish_reason'], 'stop')
        self.assertEqual(resp['usage']['prompt_tokens'], 1000)
        self.assertEqual(resp['usage']['completion_tokens'], 20)
        self.assertEqual(resp['usage']['cache_read_input_tokens'], 700)
        self.assertEqual(resp['usage']['cache_creation_input_tokens'], 100)
        self.assertEqual(resp['usage']['uncached_input_tokens'], 200)
        self.assertEqual(resp['usage']['reasoning_tokens'], 15)
        self.assertEqual(resp['usage']['cost'], 0.0012)
        # The primitives' readers understand the mapped shape unchanged.
        self.assertEqual(mem._response_finish_reason(reply), 'stop')
        self.assertEqual(mem._response_usage(reply), (1000, 20))
        self.assertEqual(mem._response_reasoning(reply), 'because')

    def test_openrouter_content_filter_is_emptied(self):
        data = {**self.COMPLETION,
                'choices': [{'finish_reason': 'content_filter',
                             'message': {'role': 'assistant', 'content': 'I cannot help with that.'}}]}
        model = claude_extract.ClaudeExtractModel(settings=OR_SETTINGS, client=FakeOpenAI(FakeCompletion(data)))
        reply = model.query([{'role': 'user', 'content': 'U'}])
        self.assertEqual(reply['content'], '')
        self.assertEqual(reply['extra']['response']['choices'][0]['finish_reason'], 'refusal')

    def test_openrouter_missing_usage_details(self):
        data = {**self.COMPLETION, 'usage': {'prompt_tokens': 5, 'completion_tokens': 1}}
        model = claude_extract.ClaudeExtractModel(settings=OR_SETTINGS, client=FakeOpenAI(FakeCompletion(data)))
        usage = model.query([{'role': 'user', 'content': 'U'}])['extra']['response']['usage']
        self.assertEqual((usage['prompt_tokens'], usage['completion_tokens'], usage['uncached_input_tokens']), (5, 1, 5))
        self.assertIsNone(usage['cache_read_input_tokens'])
        self.assertIsNone(usage['cost'])


if __name__ == '__main__':
    unittest.main()
