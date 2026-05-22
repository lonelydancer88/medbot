"""LangGraph 图定义 — 问诊助手的有状态对话编排。

设计：turn-based，每次 invoke() 处理一个患者输入 -> 输出一个 AI 回复。
"""

from langgraph.graph import StateGraph, END
from backend.langgraph.state import ConsultationState
from backend.langgraph.nodes.consultation_loop import consultation_loop
from backend.langgraph.nodes.information_gather import information_gather
from backend.langgraph.nodes.diagnosis import generate_diagnosis
from backend.langgraph.nodes.medical_record import generate_medical_record


def route_after_gather(state: ConsultationState) -> str:
    """After information_gather, go to diagnosis if flagged, otherwise END."""
    if state.get("next_action") == "proceed_diagnosis":
        return "generate_diagnosis"
    return "end"


def build_graph() -> StateGraph:
    """Build and compile the consultation LangGraph.

    Flow per invoke():
      consultation_loop (generate AI reply)
          → information_gather (extract structured info)
          → END (wait for next patient input)
            or → generate_diagnosis → generate_medical_record → END
    """
    builder = StateGraph(ConsultationState)

    builder.add_node("consultation_loop", consultation_loop)
    builder.add_node("information_gather", information_gather)
    builder.add_node("generate_diagnosis", generate_diagnosis)
    builder.add_node("generate_medical_record", generate_medical_record)

    # Each invoke starts with the patient's latest input in state
    builder.set_entry_point("consultation_loop")

    # Always extract info after generating a response
    builder.add_edge("consultation_loop", "information_gather")

    # After extraction, decide: diagnosis or wait for next input
    builder.add_conditional_edges(
        "information_gather",
        route_after_gather,
        {
            "generate_diagnosis": "generate_diagnosis",
            "end": END,
        },
    )

    # After diagnosis, always generate a medical record summary
    builder.add_edge("generate_diagnosis", "generate_medical_record")
    builder.add_edge("generate_medical_record", END)

    return builder.compile()


graph = build_graph()
