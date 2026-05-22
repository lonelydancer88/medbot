"""Test the LLM JSON parsing utilities."""

import pytest
from backend.langgraph.llm import _parse_json, call_llm_json


class TestParseJson:
    def test_direct_json(self):
        text = '{"key": "value", "num": 42}'
        result = _parse_json(text)
        assert result == {"key": "value", "num": 42}

    def test_json_with_code_fence(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_json(text)
        assert result == {"key": "value"}

    def test_json_with_code_fence_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        result = _parse_json(text)
        assert result == {"key": "value"}

    def test_json_embedded_in_text(self):
        text = "Here is the result:\n{\"name\": \"test\"}\nThank you."
        result = _parse_json(text)
        assert result == {"name": "test"}

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            _parse_json("not json at all")

    def test_nested_json(self):
        text = '{"diagnoses": [{"disease": "感冒", "probability": "高"}], "meta": {"version": 1}}'
        result = _parse_json(text)
        assert result["diagnoses"][0]["disease"] == "感冒"
        assert result["meta"]["version"] == 1


class TestCallLlmJson:
    def test_mocked_call_llm_json_returns_response(self, mocker):
        """Test that call_llm_json returns parsed dict."""
        mock_raw = mocker.patch("backend.langgraph.llm._call_llm_raw")
        mock_raw.return_value = '{"response": "你好", "next_action": "ask_more"}'

        result = call_llm_json("test prompt")
        assert result == {"response": "你好", "next_action": "ask_more"}

    def test_mocked_call_handles_code_fence(self, mocker):
        mock_raw = mocker.patch("backend.langgraph.llm._call_llm_raw")
        mock_raw.return_value = '```json\n{"key": "value"}\n```'

        result = call_llm_json("prompt")
        assert result == {"key": "value"}

    def test_mocked_call_empty_response(self, mocker):
        mock_raw = mocker.patch("backend.langgraph.llm._call_llm_raw")
        mock_raw.return_value = "{}"

        result = call_llm_json("prompt")
        assert result == {}
