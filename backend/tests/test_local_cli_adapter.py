"""Tests for local CLI model adapter helpers."""

import unittest

from app.ai.local_cli_adapter import LocalCLIAdapter, messages_to_prompt, parse_cli_args


class LocalCLIAdapterHelperTestCase(unittest.TestCase):
    def test_messages_to_prompt_preserves_roles(self):
        prompt = messages_to_prompt([
            {"role": "system", "content": "Follow rules."},
            {"role": "user", "content": "Write chapter 1."},
        ])
        self.assertIn("[SYSTEM]\nFollow rules.", prompt)
        self.assertIn("[USER]\nWrite chapter 1.", prompt)

    def test_parse_cli_args_replaces_placeholders_from_json_array(self):
        args = parse_cli_args('["exec","--model","{model}","{prompt}"]', "codex_cli", "hello", "codex-cli")
        self.assertEqual(args, ["exec", "--model", "codex-cli", "hello"])

    def test_parse_cli_args_appends_prompt_without_placeholder(self):
        args = parse_cli_args('["exec"]', "codex_cli", "hello", "codex-cli")
        self.assertEqual(args, ["exec", "hello"])

    def test_normalize_jsonl_output_extracts_text(self):
        adapter = LocalCLIAdapter(api_key="", base_url="codex_cli", cli_command="codex")
        text = adapter._normalize_output('{"type":"message","content":"hello"}\n{"delta":" world"}\n')
        self.assertEqual(text, "hello world")

    def test_normalize_plain_output_is_preserved(self):
        adapter = LocalCLIAdapter(api_key="", base_url="claude_cli", cli_command="claude")
        self.assertEqual(adapter._normalize_output("plain answer\n"), "plain answer")
