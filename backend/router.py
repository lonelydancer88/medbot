import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.langgraph.state import ConsultationState
from backend.langgraph.graph import graph
from backend.langgraph.llm import stream_consultation_llm, _parse_json_lenient
from backend.langgraph.nodes.consultation_loop import build_consultation_prompt
from backend.langgraph.nodes.information_gather import information_gather
from backend.langgraph.nodes.diagnosis import generate_diagnosis
from backend.langgraph.nodes.medical_record import generate_medical_record
from backend.db import crud

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    text: str


class SessionResponse(BaseModel):
    id: str
    status: str
    phase: str
    created_at: str


@router.post("/sessions")
def create_session():
    db_session = crud.create_session_in_db()
    # Initialize LangGraph state
    state: ConsultationState = {
        "session_id": db_session.id,
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

    # Run first step: collect_chief_complaint
    result = graph.invoke(state)

    # Save to DB
    crud.save_state(result)
    if result.get("messages"):
        last_msg = result["messages"][-1]
        crud.add_message_to_db(result["session_id"], last_msg["role"], last_msg["content"])

    return {
        "session_id": result["session_id"],
        "reply": last_msg["content"] if result.get("messages") else "",
        "phase": result["phase"],
        "thinking": result.get("thinking", ""),
    }


@router.post("/sessions/{session_id}/chat")
def chat(session_id: str, req: ChatRequest):
    db_session = crud.get_session_from_db(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if db_session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    # Rebuild state from DB
    state = json.loads(db_session.state_json)
    state["messages"] = [
        {"role": m.role, "content": m.content}
        for m in crud.get_messages_from_db(session_id)
    ]

    # Add patient message
    state["messages"].append({"role": "patient", "content": req.text})
    crud.add_message_to_db(session_id, "patient", req.text)

    # Run graph
    result = graph.invoke(state)

    # Save
    crud.save_state(result)
    if result.get("messages"):
        # Get only the new AI messages
        db_count = len(crud.get_messages_from_db(session_id))
        new_msgs = result["messages"][db_count:]
        for m in new_msgs:
            if m["role"] == "ai":
                crud.add_message_to_db(session_id, "ai", m["content"])

    # Save diagnosis if generated
    diagnosis_result = result.get("diagnosis")
    if diagnosis_result and diagnosis_result.get("diagnoses"):
        crud.save_diagnoses(session_id, diagnosis_result["diagnoses"])

    # Get the latest AI reply
    ai_replies = [m for m in result.get("messages", []) if m["role"] == "ai"]
    last_reply = ai_replies[-1]["content"] if ai_replies else ""

    return {
        "reply": last_reply,
        "phase": result["phase"],
        "is_complete": result.get("phase") == "complete",
        "thinking": result.get("thinking", ""),
    }


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    db_session = crud.get_session_from_db(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = crud.get_messages_from_db(session_id)
    diagnoses = crud.get_diagnoses_from_db(session_id)

    # Extract medical_record from saved state
    medical_record = ""
    try:
        state_data = json.loads(db_session.state_json) if db_session.state_json else {}
        medical_record = state_data.get("medical_record", "")
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "session_id": db_session.id,
        "status": db_session.status,
        "phase": db_session.phase,
        "created_at": db_session.created_at.isoformat(),
        "messages": [
            {"role": m.role, "content": m.content, "id": m.id}
            for m in messages
        ],
        "diagnoses": [
            {"disease": d.disease, "probability": d.probability, "reason": d.reason}
            for d in diagnoses
        ],
        "medical_record": medical_record,
    }


def _format_sse(event: str, data: str) -> str:
    """Format an SSE event. `data` should already be JSON-encoded."""
    return f"event: {event}\ndata: {data}\n\n"


def _apply_state_updates(state: dict, updates: dict):
    """Apply node return values to state, mimicking LangGraph reducers."""
    for key, value in updates.items():
        if key == "messages":
            # Not used in manual post-processing — messages handled separately
            continue
        elif key in ("symptoms", "associated_symptoms"):
            # These use Annotated[list, operator.add] — concatenate
            if value:
                state[key] = state.get(key, []) + value
        elif key == "thinking":
            state[key] = value
        elif key in ("next_action", "phase", "diagnosis"):
            state[key] = value
        elif key in ("age", "gender", "pregnancy"):
            if value:
                state[key] = value
        elif key in ("chief_complaint", "past_history", "medication_history", "allergies"):
            if value:
                existing = state.get(key, "")
                state[key] = existing + ("；" + value if existing else value)
        else:
            if value:
                state[key] = value


@router.post("/sessions/{session_id}/chat/stream")
def chat_stream(session_id: str, req: ChatRequest):
    db_session = crud.get_session_from_db(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if db_session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    # Rebuild state from DB
    state = json.loads(db_session.state_json)
    state["messages"] = [
        {"role": m.role, "content": m.content}
        for m in crud.get_messages_from_db(session_id)
    ]

    # Add patient message
    state["messages"].append({"role": "patient", "content": req.text})
    crud.add_message_to_db(session_id, "patient", req.text)

    prompt = build_consultation_prompt(state)

    def generate():
        # Phase 1: stream LLM response
        full_resp_text = ""
        full_thinking = ""
        for event_type, data in stream_consultation_llm(prompt):
            if event_type == "error":
                yield _format_sse("error", json.dumps(data, ensure_ascii=False))
                return
            elif event_type == "done":
                full_resp_text = data["text"]
                full_thinking = data["thinking"]

                # Parse the JSON output
                parsed = _parse_json_lenient(full_resp_text)
                response_text = parsed.get("response", full_resp_text)
                next_action = parsed.get("next_action", "ask_more")

                done_payload = json.dumps({
                    "text": response_text,
                    "thinking": full_thinking,
                }, ensure_ascii=False)
                yield _format_sse("done", done_payload)

                # ---- Post-processing ----
                state["messages"].append({"role": "ai", "content": response_text})
                state["thinking"] = full_thinking
                state["next_action"] = next_action
                state["phase"] = "diagnosing" if next_action == "proceed_diagnosis" else "collecting"

                crud.add_message_to_db(session_id, "ai", response_text)

                # Run information_gather
                try:
                    gather_updates = information_gather(state)
                    _apply_state_updates(state, gather_updates)
                except Exception:
                    pass  # non-fatal

                # Run diagnosis if needed
                if state.get("next_action") == "proceed_diagnosis":
                    try:
                        diag_updates = generate_diagnosis(state)
                        state.update({k: v for k, v in diag_updates.items() if k != "messages"})

                        diag_result = diag_updates.get("diagnosis", {})
                        diag_content = ""
                        if diag_updates.get("messages"):
                            diag_content = diag_updates["messages"][0]["content"]

                        diag_payload = json.dumps({
                            "diagnoses": diag_result.get("diagnoses", []),
                            "content": diag_content,
                        }, ensure_ascii=False)
                        yield _format_sse("diagnosis", diag_payload)

                        crud.add_message_to_db(session_id, "ai", diag_content)
                        if diag_result.get("diagnoses"):
                            crud.save_diagnoses(session_id, diag_result["diagnoses"])

                        # Generate medical record summary
                        try:
                            mr_updates = generate_medical_record(state)
                            state["medical_record"] = mr_updates.get("medical_record", "")

                            mr_payload = json.dumps({
                                "content": mr_updates.get("medical_record", ""),
                                "thinking": mr_updates.get("thinking", ""),
                            }, ensure_ascii=False)
                            yield _format_sse("medical_record", mr_payload)
                        except Exception:
                            pass  # non-fatal
                    except Exception:
                        state["next_action"] = "ask_more"
                        state["phase"] = "collecting"

                # Save final state
                try:
                    crud.save_state(state)
                except Exception as e:
                    yield _format_sse("error", json.dumps(
                        f"Failed to save: {e}", ensure_ascii=False
                    ))

                # Send final phase event
                phase_payload = json.dumps({
                    "phase": state["phase"],
                    "is_complete": state.get("phase") == "complete",
                }, ensure_ascii=False)
                yield _format_sse("phase", phase_payload)
            else:
                # "thinking" or "text" — stream to frontend
                yield _format_sse(event_type, json.dumps(data, ensure_ascii=False))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
def list_sessions(skip: int = 0, limit: int = 20):
    sessions = crud.list_sessions_db(skip, limit)
    return {
        "sessions": [
            {
                "session_id": s.id,
                "status": s.status,
                "phase": s.phase,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ]
    }
