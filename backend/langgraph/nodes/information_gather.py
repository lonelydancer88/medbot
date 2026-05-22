import json
from backend.langgraph.state import ConsultationState
from backend.langgraph import llm as llm_module


def information_gather(state: ConsultationState) -> dict:
    """Extract structured medical info from the latest patient message.

    Returns only NEW items for list fields — the Annotated[list, operator.add]
    reducer in the state definition handles appending.
    """

    patient_msgs = [m for m in state.get("messages", []) if m["role"] == "patient"]
    if not patient_msgs:
        return {}

    latest_exchange = patient_msgs[-1]["content"]

    current_info = {
        "age": state.get("age", ""),
        "gender": state.get("gender", ""),
        "pregnancy": state.get("pregnancy", ""),
        "chief_complaint": state.get("chief_complaint", ""),
        "symptoms": state.get("symptoms", []),
        "associated_symptoms": state.get("associated_symptoms", []),
        "past_history": state.get("past_history", ""),
        "medication_history": state.get("medication_history", ""),
        "allergies": state.get("allergies", ""),
    }

    prompt = """从最新的医患对话中提取结构化医学信息。只提取本轮对话中提到的新信息。

对话：
{latest_exchange}

当前已知道的信息：
{current_info}

输出 JSON（不要有其他内容）：
{{
  "age": "年龄（如果首次提到，否则填空）",
  "gender": "性别（男/女，如果首次提到）",
  "pregnancy": "怀孕状态（yes=已怀孕/no=未怀孕/unknown=不清楚，仅当患者为女性18-50岁时填写）",
  "chief_complaint": "主诉（如果首次提到）",
  "new_symptoms": [{{"name": "症状名", "duration": "持续时间", "detail": "细节描述"}}],
  "new_associated_symptoms": ["伴随症状"],
  "new_history": "提及的既往病史",
  "new_medications": "提及的用药史",
  "new_allergies": "提及的过敏史"
}}
将未提及的字段设为空字符串或空列表。"""

    prompt = prompt.format(
        latest_exchange=latest_exchange,
        current_info=json.dumps(current_info, ensure_ascii=False, indent=2),
    )

    extracted = llm_module.call_llm_json(prompt)

    updates: dict = {}

    # Age
    if extracted.get("age") and not state.get("age"):
        updates["age"] = extracted["age"]

    # Gender
    if extracted.get("gender") and not state.get("gender"):
        updates["gender"] = extracted["gender"]

    # Pregnancy
    if extracted.get("pregnancy") and not state.get("pregnancy"):
        updates["pregnancy"] = extracted["pregnancy"]

    # Chief complaint
    if extracted.get("chief_complaint") and not state.get("chief_complaint"):
        updates["chief_complaint"] = extracted["chief_complaint"]

    new_symptoms = extracted.get("new_symptoms", [])
    if new_symptoms:
        # Return only truly new symptoms (not already in state)
        existing_names = {s.get("name") for s in state.get("symptoms", [])}
        truly_new = [s for s in new_symptoms if s.get("name") and s["name"] not in existing_names]
        if truly_new:
            updates["symptoms"] = truly_new

    new_assoc = extracted.get("new_associated_symptoms", [])
    if new_assoc:
        existing = set(state.get("associated_symptoms", []))
        truly_new = [s for s in new_assoc if s and s not in existing]
        if truly_new:
            updates["associated_symptoms"] = truly_new

    if extracted.get("new_history") and not state.get("past_history"):
        updates["past_history"] = extracted["new_history"]
    elif extracted.get("new_history"):
        updates["past_history"] = state.get("past_history", "") + "；" + extracted["new_history"]

    if extracted.get("new_medications") and not state.get("medication_history"):
        updates["medication_history"] = extracted["new_medications"]
    elif extracted.get("new_medications"):
        updates["medication_history"] = (
            state.get("medication_history", "") + "；" + extracted["new_medications"]
        )

    if extracted.get("new_allergies") and not state.get("allergies"):
        updates["allergies"] = extracted["new_allergies"]
    elif extracted.get("new_allergies"):
        updates["allergies"] = state.get("allergies", "") + "；" + extracted["new_allergies"]

    return updates
