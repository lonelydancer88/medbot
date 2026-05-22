import json
from backend.langgraph.state import ConsultationState
from backend.langgraph.prompts import MEDICAL_RECORD_PROMPT
from backend.langgraph import llm as llm_module


def generate_medical_record(state: ConsultationState) -> dict:
    """Generate a structured medical record summary from all collected data."""

    all_info = {
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

    # Format recent messages for the LLM to reference
    messages = state.get("messages", [])
    conversation_text = ""
    for m in messages[-10:]:  # last 10 messages for context
        role = "医生" if m["role"] == "ai" else "患者"
        conversation_text += f"{role}：{m['content']}\n\n"

    prompt = MEDICAL_RECORD_PROMPT.format(
        all_info=json.dumps(all_info, ensure_ascii=False, indent=2),
        diagnosis=json.dumps(state.get("diagnosis", {}), ensure_ascii=False, indent=2),
        conversation=conversation_text,
    )

    result, thinking = llm_module.call_llm_json_with_thinking(prompt)

    # The prompt asks for markdown, not JSON. _parse_json_lenient will
    # wrap the text in {"response": text, ...}. Extract the response field.
    summary_text = ""
    if isinstance(result, dict):
        summary_text = result.get("response", "") or ""
    if not summary_text:
        summary_text = str(result) if result else ""

    return {
        "medical_record": summary_text,
        "thinking": thinking,
    }
