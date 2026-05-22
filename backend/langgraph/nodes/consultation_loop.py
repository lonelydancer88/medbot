"""核心对话节点：生成 AI 回复（首次问候或追问）并决定下一步方向。"""

import json
from backend.langgraph.state import ConsultationState
from backend.langgraph.prompts import CONSULTATION_LOOP_PROMPT
from backend.langgraph import llm as llm_module


_INITIAL_GREETING = "您好，我是问诊助手。在开始问诊之前，请先告诉我您的年龄和性别，以及您的主要症状。"


def build_consultation_prompt(state: ConsultationState) -> str:
    """Build the consultation loop prompt from state. Reusable by streaming endpoint."""
    history_lines = []
    for m in state.get("messages", []):
        role_label = "患者" if m["role"] == "patient" else "医生"
        history_lines.append(f"{role_label}: {m['content']}")

    structured_info = {
        "年龄": state.get("age", ""),
        "性别": state.get("gender", ""),
        "是否怀孕": state.get("pregnancy", ""),
        "主诉": state.get("chief_complaint", ""),
        "症状": state.get("symptoms", []),
        "伴随症状": state.get("associated_symptoms", []),
        "既往病史": state.get("past_history", ""),
        "用药史": state.get("medication_history", ""),
        "过敏史": state.get("allergies", ""),
    }

    return CONSULTATION_LOOP_PROMPT.format(
        history="\n".join(history_lines[-10:]),
        structured_info=json.dumps(structured_info, ensure_ascii=False, indent=2),
    )


def consultation_loop(state: ConsultationState) -> dict:
    """Core loop node — generates the AI response and sets next_action.

    Two modes:
    1. First call (no messages): returns a hardcoded greeting.
    2. Follow-up calls: calls LLM to continue the diagnostic dialogue.
    """

    if not state.get("messages"):
        return {
            "messages": [{"role": "ai", "content": _INITIAL_GREETING}],
            "next_action": "ask_more",
            "phase": "collecting",
        }

    prompt = build_consultation_prompt(state)

    result, thinking = llm_module.call_llm_json_with_thinking(prompt)

    response_text = result.get("response", "")
    next_action = result.get("next_action", "ask_more")

    updates: dict = {
        "messages": [{"role": "ai", "content": response_text}],
        "next_action": next_action,
        "thinking": thinking,
    }

    if next_action == "proceed_diagnosis":
        updates["phase"] = "diagnosing"
    else:
        updates["phase"] = "collecting"

    return updates
