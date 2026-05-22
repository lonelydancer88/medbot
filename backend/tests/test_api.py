"""Test the FastAPI endpoints with mocked LLM responses."""

import json


class TestCreateSession:
    def test_create_session_returns_greeting(self, client, mocker):
        """Creating a session should return the initial greeting (no LLM needed)."""
        resp = client.post("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["reply"] != ""
        assert data["phase"] == "collecting"

    def test_create_session_then_chat_flow(self, client, mocker):
        """Full API flow: create session → chat → get session."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        # Create session (no LLM call for greeting)
        create_resp = client.post("/api/sessions")
        sid = create_resp.json()["session_id"]

        # Chat: patient says "我头痛三天了"
        # consultation_loop calls call_llm_json_with_thinking
        mock_thinking.side_effect = [
            (
                {
                    "response": "头痛多久了？还有其它不适吗？",
                    "next_action": "ask_more",
                    "info_gaps": ["持续时间"],
                },
                "追问头痛持续时间以判断急慢性。",
            ),
        ]
        # information_gather calls call_llm_json
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

        chat_resp = client.post(
            f"/api/sessions/{sid}/chat", json={"text": "我头痛三天了"}
        )
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        assert data["reply"] != ""
        assert data["is_complete"] is False
        assert data["phase"] == "collecting"

        # Get session should include both messages
        get_resp = client.get(f"/api/sessions/{sid}")
        assert get_resp.status_code == 200
        msgs = get_resp.json()["messages"]
        assert len(msgs) >= 2  # greeting + patient + ai response

    def test_chat_completed_session_refused(self, client, mocker):
        """Chatting on a completed session should return 400."""
        mock_thinking = mocker.patch("backend.langgraph.llm.call_llm_json_with_thinking")
        mock_json = mocker.patch("backend.langgraph.llm.call_llm_json")

        create_resp = client.post("/api/sessions")
        sid = create_resp.json()["session_id"]

        # Mock a full flow that completes
        mock_thinking.side_effect = [
            # consultation_loop
            (
                {"response": "明白了。", "next_action": "proceed_diagnosis", "info_gaps": []},
                "信息足够了，开始诊断。",
            ),
            # generate_diagnosis
            (
                {
                    "diagnoses": [{"disease": "感冒", "probability": "高", "reason": "典型症状"}],
                    "suggested_exams": [],
                    "referral_advice": "多休息",
                    "lifestyle_advice": "多喝水",
                    "disclaimer": "仅供参考",
                },
                "分析：上呼吸道感染可能，属于自限性疾病。",
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

        chat_resp = client.post(
            f"/api/sessions/{sid}/chat", json={"text": "我感冒了"}
        )
        assert chat_resp.status_code == 200
        assert chat_resp.json()["is_complete"] is True

        # Second chat should be refused
        chat_resp2 = client.post(
            f"/api/sessions/{sid}/chat", json={"text": "再问一个问题"}
        )
        assert chat_resp2.status_code == 400

    def test_chat_nonexistent_session(self, client, mocker):
        """Chatting on a nonexistent session should return 404."""
        resp = client.post("/api/sessions/nonexistent/chat", json={"text": "hello"})
        assert resp.status_code == 404


class TestListSessions:
    def test_list_sessions_empty(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 0

    def test_list_sessions_after_creation(self, client, mocker):
        client.post("/api/sessions")
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert len(resp.json()["sessions"]) >= 1


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
