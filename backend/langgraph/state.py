"""LangGraph state definition with proper reducers for list fields."""

from typing import Annotated, TypedDict
import operator


class Symptom(TypedDict, total=False):
    name: str
    duration: str
    detail: str


class ConsultationState(TypedDict, total=False):
    # 会话信息
    session_id: str
    # 使用 operator.add reducer: 节点返回新消息列表，自动追加到已有列表
    messages: Annotated[list, operator.add]

    # 基础人口信息
    age: str
    gender: str
    pregnancy: str                 # yes / no / unknown (仅女性 18-50 适用)

    # 结构化医学信息
    chief_complaint: str
    symptoms: Annotated[list, operator.add]
    associated_symptoms: Annotated[list, operator.add]
    past_history: str
    medication_history: str
    allergies: str

    # 流程控制
    phase: str                     # collecting | diagnosing | complete
    next_action: str               # ask_more | proceed_diagnosis
    diagnosis: dict
    medical_record: str            # LLM 生成的病历总结（markdown）

    # LLM 思考过程（当前轮次的 reasoning/thinking 内容）
    thinking: str
