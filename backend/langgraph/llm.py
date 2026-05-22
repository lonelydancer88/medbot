"""LLM 调用封装。生产环境调用外部 API，测试时可 mock。"""
import json
import re
import sys
from backend.config import ANTHROPIC_API_KEY, ANTHROPIC_API_URL, LLM_MODEL


def _extract_content_blocks(raw_content) -> tuple[str, str]:
    """Extract text and thinking blocks from LLM response.

    Returns (text_content, thinking_content) tuple.
    """
    if not isinstance(raw_content, list):
        return str(raw_content).strip(), ""

    texts = []
    thinkings = []
    for block in raw_content:
        if isinstance(block, dict):
            block_type = block.get("type", "")
            if block_type == "text":
                texts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinkings.append(block.get("thinking", ""))
        else:
            texts.append(str(block))

    return "\n".join(texts).strip(), "\n".join(thinkings).strip()


def _call_llm_raw(prompt: str, retries: int = 2) -> str:
    """Low-level LLM call. Uses Anthropic-compatible API."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Please set it in .env file or environment."
        )

    from langchain_anthropic import ChatAnthropic

    kwargs = dict(
        model=LLM_MODEL,
        api_key=ANTHROPIC_API_KEY,
        temperature=0.3,
    )
    if ANTHROPIC_API_URL:
        kwargs["anthropic_api_url"] = ANTHROPIC_API_URL

    llm = ChatAnthropic(**kwargs)

    for attempt in range(retries + 1):
        try:
            result = llm.invoke(prompt)

            # Handle both string and list-of-content-blocks responses
            if isinstance(result.content, list):
                texts = []
                for block in result.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block.get("text", ""))
                    else:
                        texts.append(str(block))
                joined = "\n".join(texts).strip()
                if joined:
                    return joined
            else:
                text = str(result.content).strip()
                if text:
                    return text

            if attempt < retries:
                import time
                time.sleep(1)

        except Exception as e:
            if attempt < retries:
                import time
                time.sleep(1)
            else:
                raise

    return ""


def call_llm_json(prompt: str, strict: bool = False) -> dict:
    """Call LLM and parse response as JSON.

    Args:
        prompt: The prompt to send to the LLM.
        strict: If True, raises on invalid JSON. If False, falls back
                gracefully by treating the response as conversational text.
    """
    raw = _call_llm_raw(prompt)
    if strict:
        return _parse_json(raw)
    return _parse_json_lenient(raw)


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM response (handles markdown code fences)."""
    text = text.strip()
    if not text:
        raise ValueError("Failed to parse LLM response as JSON: empty response")

    # Try to extract JSON from markdown code block
    pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find {...} in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse LLM response as JSON: {text[:200]}")


def _parse_json_lenient(text: str) -> dict:
    """Parse LLM response as JSON, with graceful fallback.

    If the LLM didn't output valid JSON, treat the entire text as
    the conversational response. Detect diagnosis-like content to
    auto-proceed instead of defaulting to ask_more.
    """
    text = text.strip()
    if not text:
        return {"response": "", "next_action": "ask_more", "info_gaps": []}

    # Try to extract JSON from markdown code block
    pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find {...} in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    # Graceful fallback: treat text as the conversational response
    # Detect if this looks like a diagnosis rather than a follow-up question
    next_action = _classify_response_intent(text)
    return {"response": text, "next_action": next_action, "info_gaps": []}


def _classify_response_intent(text: str) -> str:
    """Classify whether a free-text response is a diagnosis or asking more.

    Returns "proceed_diagnosis" or "ask_more".
    """
    # Strong diagnostic markers — the LLM is clearly giving a diagnosis
    strong_markers = [
        "初步诊断", "诊断建议", "诊断结果", "诊断分析",
        "情况分析", "病情分析", "综合分析",
        "建议检查", "检查建议", "就医建议",
        "治疗方案", "治疗建议", "处理建议",
        "处方建议", "用药建议",
        "鉴别诊断", "临床诊断",
        "**诊断",  # markdown bold: **诊断**
        "**情况分析**", "**病情分析**",
    ]
    for marker in strong_markers:
        if marker in text:
            return "proceed_diagnosis"

    # If the response is multi-paragraph and doesn't end with a question,
    # it's likely a diagnosis
    if len(text) > 200 and "？" not in text[-100:]:
        # Check it has structural elements (headers, lists)
        structural_count = text.count("**") + text.count("##") + text.count("- ")
        if structural_count >= 3:
            return "proceed_diagnosis"

    return "ask_more"


def call_llm_json_with_thinking(prompt: str) -> tuple[dict, str]:
    """Call LLM and return (parsed_json, thinking_text).

    Like call_llm_json() but also captures the LLM's internal thinking/reasoning
    blocks (e.g., DeepSeek's thinking content).
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Please set it in .env file or environment."
        )

    from langchain_anthropic import ChatAnthropic

    kwargs = dict(
        model=LLM_MODEL,
        api_key=ANTHROPIC_API_KEY,
        temperature=0.3,
    )
    if ANTHROPIC_API_URL:
        kwargs["anthropic_api_url"] = ANTHROPIC_API_URL

    llm = ChatAnthropic(**kwargs)

    for attempt in range(2 + 1):
        try:
            result = llm.invoke(prompt)
            text_content, thinking_content = _extract_content_blocks(result.content)
            if text_content:
                parsed = _parse_json_lenient(text_content)
                return parsed, thinking_content

            if attempt < 2:
                import time
                time.sleep(1)
        except Exception as e:
            if attempt < 2:
                import time
                time.sleep(1)
            else:
                raise

    return {"response": "", "next_action": "ask_more", "info_gaps": []}, ""


def _extract_chunk_delta(raw_content) -> tuple[str, str]:
    """Like _extract_content_blocks but for streaming chunks: no newline join."""
    if not isinstance(raw_content, list):
        return str(raw_content), ""

    texts = []
    thinkings = []
    for block in raw_content:
        if isinstance(block, dict):
            block_type = block.get("type", "")
            if block_type == "text":
                texts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinkings.append(block.get("thinking", ""))
        else:
            texts.append(str(block))

    return "".join(texts), "".join(thinkings)


def stream_consultation_llm(prompt: str):
    """Stream LLM response for consultation.

    Uses ChatAnthropic(streaming=True).stream() to yield incremental
    thinking and text deltas. Yields (event_type, data) tuples:

        ("thinking", str)  — delta thinking content
        ("text", str)      — delta text content
        ("done", dict)     — {"text": full_text, "thinking": full_thinking}
        ("error", str)     — error message

    No retries — streaming errors are yielded immediately.
    """
    if not ANTHROPIC_API_KEY:
        yield ("error", "ANTHROPIC_API_KEY not set")
        return

    from langchain_anthropic import ChatAnthropic

    kwargs = dict(
        model=LLM_MODEL,
        api_key=ANTHROPIC_API_KEY,
        temperature=0.3,
        streaming=True,
    )
    if ANTHROPIC_API_URL:
        kwargs["anthropic_api_url"] = ANTHROPIC_API_URL

    llm = ChatAnthropic(**kwargs)

    text_parts: list[str] = []
    thinking_parts: list[str] = []

    try:
        for chunk in llm.stream(prompt):
            text_delta, thinking_delta = _extract_chunk_delta(chunk.content)
            if thinking_delta:
                thinking_parts.append(thinking_delta)
                yield ("thinking", thinking_delta)
            if text_delta:
                text_parts.append(text_delta)
                yield ("text", text_delta)
    except Exception as e:
        yield ("error", str(e))
        return

    full_text = "".join(text_parts).strip()
    full_thinking = "".join(thinking_parts).strip()
    yield ("done", {"text": full_text, "thinking": full_thinking})
