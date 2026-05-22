import json
from backend.langgraph.state import ConsultationState
from backend.langgraph.prompts import DIAGNOSIS_PROMPT
from backend.langgraph import llm as llm_module


def generate_diagnosis(state: ConsultationState) -> dict:
    """Generate preliminary diagnosis based on all collected information."""

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

    prompt = DIAGNOSIS_PROMPT.format(
        all_info=json.dumps(all_info, ensure_ascii=False, indent=2)
    )

    result, thinking = llm_module.call_llm_json_with_thinking(prompt)

    diagnoses = result.get("diagnoses", [])
    response_lines = ["**📋 初步诊断建议**\n"]
    for d in diagnoses:
        response_lines.append(
            f"- **{d.get('disease', '')}**（{d.get('probability', '')}可能性）\n"
            f"  - 依据：{d.get('reason', '')}"
        )

    exams = result.get("suggested_exams", [])
    if exams:
        response_lines.append("\n**🔬 建议检查**")
        for e in exams:
            response_lines.append(f"- {e}")

    referral = result.get("referral_advice", "")
    if referral:
        response_lines.append(f"\n**🏥 就医建议**\n{referral}")

    lifestyle = result.get("lifestyle_advice", "")
    if lifestyle:
        response_lines.append(f"\n**💡 生活建议**\n{lifestyle}")

    disclaimer = result.get(
        "disclaimer",
        "\n\n*⚕️ 此诊断建议仅供参考，不能替代专业医疗诊断。如有不适请及时就医。*",
    )
    response_lines.append(f"\n\n{disclaimer}")

    return {
        "diagnosis": result,
        "next_action": "complete",
        "phase": "complete",
        "messages": [{"role": "ai", "content": "\n".join(response_lines)}],
        "thinking": thinking,
    }
