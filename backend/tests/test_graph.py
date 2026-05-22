"""Test the LangGraph consultation flow with mocked LLM responses."""

import pytest
from backend.langgraph.state import ConsultationState
from backend.langgraph.graph import graph, route_after_gather

_INITIAL_GREETING = "您好，我是问诊助手。在开始问诊之前，请先告诉我您的年龄和性别，以及您的主要症状。"


class TestGraphRouting:
    """Test the conditional routing logic."""

    def test_route_ask_more(self):
        state: ConsultationState = {"next_action": "ask_more"}
        assert route_after_gather(state) == "end"

    def test_route_proceed_diagnosis(self):
        state: ConsultationState = {"next_action": "proceed_diagnosis"}
        assert route_after_gather(state) == "generate_diagnosis"

    def test_route_default(self):
        state: ConsultationState = {}
        assert route_after_gather(state) == "end"


class TestGraphFlow:
    """Test the full graph flow with mocked LLM responses."""

    def test_initial_greeting_no_llm_call(self):
        """First invoke should return the hardcoded greeting without calling LLM."""
        state: ConsultationState = {
            "session_id": "test-1",
            "messages": [],
            "age": "",
            "gender": "",
            "pregnancy": "",
            "chief_complaint": "",
            "symptoms": [],
            "associated_symptoms": [],
            "past_history": "",
            "medication_history": "",
            "allergies": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)

        assert result["phase"] == "collecting"
        assert result["next_action"] == "ask_more"
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "ai"
        assert _INITIAL_GREETING in result["messages"][0]["content"]

    def test_full_consultation_flow(self, mocker):
        """Test a complete consultation: greet → ask → gather → diagnose."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # consultation_loop uses call_llm_json_with_thinking
        mock_thinking.side_effect = [
            (
                {
                    "response": "头痛多久了？还有其他不适吗？",
                    "next_action": "ask_more",
                    "info_gaps": ["头痛持续时间", "伴随症状"],
                },
                "正在分析患者主诉：头痛，需确认持续时间和伴随症状...",
            ),
        ]
        # information_gather uses call_llm_json
        mock_json.side_effect = [
            {
                "chief_complaint": "头痛",
                "new_symptoms": [{"name": "头痛", "duration": "3天", "detail": ""}],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state: ConsultationState = {
            "session_id": "test-2",
            "messages": [
                {"role": "ai", "content": _INITIAL_GREETING},
                {"role": "patient", "content": "我头痛三天了"},
            ],
            "age": "",
            "gender": "",
            "pregnancy": "",
            "chief_complaint": "",
            "symptoms": [],
            "associated_symptoms": [],
            "past_history": "",
            "medication_history": "",
            "allergies": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)

        assert result["phase"] == "collecting"
        assert result["next_action"] == "ask_more"
        assert result["messages"][-1]["role"] == "ai"
        # Check info was extracted
        assert result["chief_complaint"] == "头痛"
        assert len(result["symptoms"]) == 1
        assert result["symptoms"][0]["name"] == "头痛"
        # Check thinking was captured
        assert "正在分析患者主诉" in result.get("thinking", "")

    def test_proceed_to_diagnosis(self, mocker):
        """Test LLM decides to proceed to diagnosis."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # consultation_loop + generate_diagnosis + generate_medical_record use call_llm_json_with_thinking
        mock_thinking.side_effect = [
            (
                {
                    "response": "好的，信息已足够，我来进行分析。",
                    "next_action": "proceed_diagnosis",
                    "info_gaps": [],
                },
                "判断信息已充足，准备进入诊断分析阶段。",
            ),
            (
                {
                    "diagnoses": [
                        {
                            "disease": "紧张性头痛",
                            "probability": "高",
                            "reason": "双侧头部压迫感，持续3天，无恶心呕吐",
                        }
                    ],
                    "suggested_exams": ["休息观察", "必要时测血压"],
                    "referral_advice": "如症状持续超过一周，建议就医",
                    "lifestyle_advice": "保持充足睡眠，减少压力",
                    "disclaimer": "仅供参考",
                },
                "鉴别诊断：考虑紧张性头痛可能大，需排除偏头痛、颈椎病变等。",
            ),
            (
                {
                    "response": "**📋 基本信息**\n- 年龄：未提供\n- 性别：未提供\n\n**🏥 主诉**\n头痛3天",
                },
                "整理病历信息，生成结构化总结。",
            ),
        ]
        # information_gather uses call_llm_json
        mock_json.side_effect = [
            {
                "chief_complaint": "",
                "new_symptoms": [],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state: ConsultationState = {
            "session_id": "test-3",
            "messages": [
                {"role": "ai", "content": "头痛多久了？"},
                {"role": "patient", "content": "三天了，太阳穴附近胀痛"},
            ],
            "chief_complaint": "头痛",
            "symptoms": [{"name": "头痛", "duration": "3天", "detail": "太阳穴胀痛"}],
            "associated_symptoms": [],
            "past_history": "",
            "medication_history": "",
            "allergies": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)

        assert result["phase"] == "complete"
        # generate_diagnosis sets next_action to "complete"
        assert result["next_action"] == "complete"

        # Should have diagnosis
        assert "diagnosis" in result
        diagnoses = result["diagnosis"].get("diagnoses", [])
        assert len(diagnoses) >= 1
        assert diagnoses[0]["disease"] == "紧张性头痛"

        # Messages should include the diagnosis response
        diagnosis_msgs = [m for m in result["messages"] if m["role"] == "ai"]
        last_msg = diagnosis_msgs[-1]["content"]
        assert "初步诊断" in last_msg
        assert "紧张性头痛" in last_msg
        # Check thinking was captured from medical record (last node)
        assert "整理病历信息" in result.get("thinking", "")

    def test_information_gather_no_patient_msg(self, mocker):
        """information_gather should do nothing when there's no patient message."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_thinking.return_value = ({}, "")

        state: ConsultationState = {
            "session_id": "test-4",
            "messages": [{"role": "ai", "content": "您好"}],
            "chief_complaint": "",
            "symptoms": [],
            "associated_symptoms": [],
            "past_history": "",
            "medication_history": "",
            "allergies": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)

        # consultation_loop sees messages (1 AI msg, no patient msg) → calls LLM
        # mock returns {} so response is empty
        assert result["next_action"] == "ask_more"  # default
        assert result["chief_complaint"] == ""  # not extracted


class TestStateTransitions:
    """Test that state transitions happen correctly."""

    def test_phase_transitions(self):
        """Verify phase values throughout the flow."""
        state: ConsultationState = {
            "session_id": "test-5",
            "messages": [],
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)
        assert result["phase"] == "collecting"
        assert result["next_action"] == "ask_more"

    def test_graph_handles_multiple_turns(self, mocker):
        """Simulate multiple turns across separate invoke calls."""

        def make_state(**overrides) -> ConsultationState:
            defaults: ConsultationState = {
                "session_id": "test-6",
                "messages": [],
                "age": "",
                "gender": "",
                "pregnancy": "",
                "chief_complaint": "",
                "symptoms": [],
                "associated_symptoms": [],
                "past_history": "",
                "medication_history": "",
                "allergies": "",
                "phase": "collecting",
                "next_action": "ask_more",
            }
            defaults.update(overrides)
            return defaults

        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # Turn 1: First invoke → greeting (no LLM)
        state = make_state()
        result = graph.invoke(state)
        assert _INITIAL_GREETING in result["messages"][0]["content"]

        # Turn 2: Patient says headache → LLM asks follow-up
        mock_thinking.side_effect = [
            (
                {
                    "response": "头痛部位在哪里？前额还是后脑？",
                    "next_action": "ask_more",
                    "info_gaps": ["头痛部位"],
                },
                "患者主诉头痛，需要了解具体部位。",
            ),
        ]
        mock_json.side_effect = [
            {
                "chief_complaint": "头痛",
                "new_symptoms": [{"name": "头痛", "duration": "3天", "detail": ""}],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state2 = make_state(
            messages=[
                {"role": "ai", "content": _INITIAL_GREETING},
                {"role": "patient", "content": "我头痛三天了"},
            ]
        )
        result2 = graph.invoke(state2)
        assert result2["chief_complaint"] == "头痛"
        assert len(result2["symptoms"]) == 1

        # Turn 3: Patient answers → LLM proceeds to diagnosis
        mock_thinking.side_effect = [
            (
                {
                    "response": "明白了，信息已足够。",
                    "next_action": "proceed_diagnosis",
                    "info_gaps": [],
                },
                "信息收集完毕，准备进入诊断。",
            ),
            (
                {
                    "diagnoses": [
                        {"disease": "偏头痛", "probability": "中", "reason": "单侧头痛"}
                    ],
                    "suggested_exams": [],
                    "referral_advice": "观察",
                    "lifestyle_advice": "休息",
                    "disclaimer": "仅供参考",
                },
                "鉴别诊断：考虑偏头痛可能，单侧头痛伴太阳穴部位疼痛。",
            ),
            (
                {
                    "response": "**📋 基本信息**\n头痛，左侧太阳穴",
                },
                "生成病历总结。",
            ),
        ]
        mock_json.side_effect = [
            {
                "chief_complaint": "",
                "new_symptoms": [],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state3 = make_state(
            chief_complaint="头痛",
            symptoms=[{"name": "头痛", "duration": "3天", "detail": ""}],
            messages=[
                {"role": "ai", "content": _INITIAL_GREETING},
                {"role": "patient", "content": "我头痛三天了"},
                {"role": "ai", "content": "头痛部位在哪里？"},
                {"role": "patient", "content": "左边太阳穴附近"},
            ],
        )
        result3 = graph.invoke(state3)
        assert result3["phase"] == "complete"
        assert "偏头痛" in result3["diagnosis"].get("diagnoses", [])[0]["disease"]

    def test_stomach_ache_consultation(self, mocker):
        """Test consultation flow with stomach ache complaint: 我的肚子有点痛"""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # consultation_loop asks about stomach ache
        mock_thinking.side_effect = [
            (
                {
                    "response": "腹痛具体在哪个位置？上腹还是下腹？持续多久了？有没有拉肚子或恶心？",
                    "next_action": "ask_more",
                    "info_gaps": ["腹痛位置", "持续时间", "伴随症状"],
                },
                "分析患者主诉：肚子痛，需要排除急腹症、胃肠炎等可能。",
            ),
        ]
        # information_gather extracts info
        mock_json.side_effect = [
            {
                "chief_complaint": "腹痛",
                "new_symptoms": [{"name": "腹痛", "duration": "", "detail": "部位不明确"}],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state: ConsultationState = {
            "session_id": "test-stomach-1",
            "messages": [
                {"role": "ai", "content": _INITIAL_GREETING},
                {"role": "patient", "content": "我的肚子有点痛"},
            ],
            "chief_complaint": "",
            "symptoms": [],
            "associated_symptoms": [],
            "past_history": "",
            "medication_history": "",
            "allergies": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)

        # Verify the LLM asked follow-up questions
        assert result["phase"] == "collecting"
        assert result["next_action"] == "ask_more"
        assert result["chief_complaint"] == "腹痛"
        assert len(result["symptoms"]) == 1
        assert result["symptoms"][0]["name"] == "腹痛"
        # AI should have responded with a question
        assert result["messages"][-1]["role"] == "ai"
        assert len(result["messages"][-1]["content"]) > 0

    def test_stomach_ache_full_diagnosis(self, mocker):
        """Test a complete stomach ache flow from complaint to diagnosis."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # consultation_loop + generate_diagnosis + generate_medical_record use call_llm_json_with_thinking
        mock_thinking.side_effect = [
            (
                {
                    "response": "根据您的描述，上腹隐痛伴反酸，信息已经足够，我为您分析一下。",
                    "next_action": "proceed_diagnosis",
                    "info_gaps": [],
                },
                "信息充分，准备进行消化系统疾病的鉴别诊断分析。",
            ),
            (
                {
                    "diagnoses": [
                        {
                            "disease": "慢性胃炎",
                            "probability": "高",
                            "reason": "上腹隐痛，伴反酸，饮食不规律",
                        },
                        {
                            "disease": "功能性消化不良",
                            "probability": "中",
                            "reason": "腹痛位置不固定，无器质性病变依据",
                        },
                    ],
                    "suggested_exams": ["胃镜检查", "幽门螺杆菌检测"],
                    "referral_advice": "建议消化内科就诊，如出现黑便或呕血立即就医",
                    "lifestyle_advice": "规律饮食，少食多餐，避免辛辣刺激食物，戒烟限酒",
                    "disclaimer": "本诊断仅为AI初步分析，不能替代专业医疗诊断",
                },
                "鉴别诊断：上腹痛伴反酸，优先考虑慢性胃炎、消化性溃疡，需排除胆囊疾病。",
            ),
            (
                {
                    "response": "**📋 基本信息**\n- 主诉：腹痛\n\n**🏥 主诉**\n上腹隐痛",
                },
                "整理病历，生成总结。",
            ),
        ]
        # information_gather uses call_llm_json
        mock_json.side_effect = [
            {
                "chief_complaint": "",
                "new_symptoms": [],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state: ConsultationState = {
            "session_id": "test-stomach-2",
            "messages": [
                {"role": "ai", "content": _INITIAL_GREETING},
                {"role": "patient", "content": "我的肚子有点痛"},
                {"role": "ai", "content": "腹痛具体在哪个位置？持续多久了？"},
                {"role": "patient", "content": "上腹部隐隐作痛，吃完饭更明显，还有点反酸"},
            ],
            "chief_complaint": "腹痛",
            "symptoms": [{"name": "腹痛", "duration": "", "detail": "上腹部隐痛，餐后加重"}],
            "associated_symptoms": [{"name": "反酸"}],
            "past_history": "",
            "medication_history": "",
            "allergies": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        result = graph.invoke(state)

        assert result["phase"] == "complete"
        assert result["next_action"] == "complete"
        assert "diagnosis" in result
        diagnoses = result["diagnosis"].get("diagnoses", [])
        assert len(diagnoses) >= 1
        # Should mention gastritis as primary diagnosis
        assert "慢性胃炎" in diagnoses[0]["disease"]
        # Messages should include the diagnosis
        last_ai_msg = [m for m in result["messages"] if m["role"] == "ai"][-1]
        assert "初步诊断" in last_ai_msg["content"]


class TestMedicalRecord:
    """Test the medical record summary generation after diagnosis."""

    def test_medical_record_generated_after_diagnosis(self, mocker):
        """Verify medical record is generated when diagnosis completes."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # consultation_loop → proceed, generate_diagnosis, generate_medical_record
        mock_thinking.side_effect = [
            # consultation_loop
            (
                {
                    "response": "信息已足够，我来分析。",
                    "next_action": "proceed_diagnosis",
                    "info_gaps": [],
                },
                "信息充足，准备诊断。",
            ),
            # generate_diagnosis
            (
                {
                    "diagnoses": [
                        {"disease": "感冒", "probability": "高", "reason": "流涕、咳嗽"}
                    ],
                    "suggested_exams": ["体温检测"],
                    "referral_advice": "休息",
                    "lifestyle_advice": "多喝水",
                    "disclaimer": "仅供参考",
                },
                "诊断思考过程",
            ),
            # generate_medical_record
            (
                {
                    "response": (
                        "**📋 基本信息**\n"
                        "- 年龄：30\n"
                        "- 性别：男\n\n"
                        "**🏥 主诉**\n"
                        "感冒2天\n\n"
                        "**📝 现病史**\n"
                        "流涕、咳嗽，持续2天"
                    ),
                },
                "生成病历总结的思考过程",
            ),
        ]
        mock_json.side_effect = [
            # information_gather
            {
                "chief_complaint": "",
                "new_symptoms": [],
                "new_associated_symptoms": [],
                "new_history": "",
                "new_medications": "",
                "new_allergies": "",
            },
        ]

        state: ConsultationState = {
            "session_id": "test-mr-1",
            "messages": [
                {"role": "ai", "content": "有什么症状？"},
                {"role": "patient", "content": "感冒了，流鼻涕咳嗽"},
            ],
            "age": "30",
            "gender": "男",
            "chief_complaint": "感冒",
            "symptoms": [{"name": "流涕", "duration": "2天", "detail": ""}],
            "phase": "collecting",
            "next_action": "ask_more",
        }

        from backend.langgraph.graph import graph
        result = graph.invoke(state)

        assert result["phase"] == "complete"
        assert "medical_record" in result
        assert "基本信息" in result["medical_record"]
        assert "30" in result["medical_record"]
        assert "男" in result["medical_record"]

    def test_medical_record_missing_diagnosis(self, mocker):
        """Medical record is still generated even with minimal state."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        mock_thinking.side_effect = [
            # consultation_loop: proceed to diagnosis
            (
                {"response": "好的", "next_action": "proceed_diagnosis", "info_gaps": []},
                "",
            ),
            # generate_diagnosis: minimal diagnosis
            (
                {
                    "diagnoses": [],
                    "suggested_exams": [],
                    "referral_advice": "",
                    "lifestyle_advice": "",
                    "disclaimer": "",
                },
                "",
            ),
            # generate_medical_record
            (
                {"response": "**📋 基本信息**\n信息有限"},
                "",
            ),
        ]
        mock_json.side_effect = [
            {"chief_complaint": "", "new_symptoms": [], "new_associated_symptoms": [],
             "new_history": "", "new_medications": "", "new_allergies": ""},
        ]

        state: ConsultationState = {
            "session_id": "test-mr-2",
            "messages": [
                {"role": "ai", "content": "你好"},
                {"role": "patient", "content": "头疼"},
            ],
            "chief_complaint": "",
            "phase": "collecting",
            "next_action": "ask_more",
        }

        from backend.langgraph.graph import graph
        result = graph.invoke(state)

        assert result["phase"] == "complete"
        assert "medical_record" in result
        assert isinstance(result["medical_record"], str)
        assert len(result["medical_record"]) > 0
