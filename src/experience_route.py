from fastapi import APIRouter, HTTPException, Header
from typing import Any, Dict, Optional

import src.database as db
from src.experience.experience_agent import langgraph_experience_app as langgraph_app, ALL_FIELDS, handle_experience_message as handle_user_message
from src.schemas import StartChatRequest, ChatRequest
from src.experience_resume import format_ats_experience_with_llm


router = APIRouter()

# ============================================================
# ✅ START CHAT (collects API key)
# ============================================================
@router.post("/start_chat")
async def start_chat(
    request: StartChatRequest,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    try:
        if not x_api_key:
            raise HTTPException(400, "Missing LLM API key in header (x-api-key)")

        chat_id = db.create_chat_session(request.user_id)

        initial_state = {
            "chat_id": chat_id,
            "messages": [],
            "current_experience": {},
            "experiences_collected": [],
            "field_completion_status": {field: False for field in ALL_FIELDS},
            "field_ask_count": {field: 0 for field in ALL_FIELDS},
            "current_field": None,
            "conversation_context": "Starting conversation",
            "interaction_count": 0,
            "is_first_message": True,
        }

        config = {
            "configurable": {
                "thread_id": chat_id,
                "api_key": x_api_key,  # ✅ Include key in config
            },
            "recursion_limit": 3,
        }

        response = await langgraph_app.ainvoke(initial_state, config=config)

        ai_message = (
            response["messages"][-1].content
            if response.get("messages")
            else "Let's begin with your first experience!"
        )

        # Calculate initial status
        status_dict = response.get(
            "field_completion_status",
            {field: False for field in ALL_FIELDS},
        )
        completed_fields = sum(1 for v in status_dict.values() if v is True)
        total_fields = len(ALL_FIELDS)
        percentage = (
            int((completed_fields / total_fields) * 100) if total_fields > 0 else 0
        )

        return {
            "status": True,
            "message": "Chat session started successfully",
            "data": {
                "chat_id": chat_id,
                "ai_response": ai_message,
                "current_section": "experiences",
                "is_complete": False,
                "percentage": percentage,
                "status": status_dict,
            },
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        return {
            "status": False,
            "message": f"Error starting chat: {str(e)}",
            "data": None,
        }


# ============================================================
# ✅ CONTINUE CHAT (pass API key through)
# ============================================================
@router.post("/chat/{chat_id}")
async def chat(
    chat_id: str,
    request: ChatRequest,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    try:
        if not x_api_key:
            raise HTTPException(400, "Missing LLM API key in header (x-api-key)")

        session = db.get_chat_session(chat_id)
        if not session:
            return {
                "status": False,
                "message": "Chat session not found",
                "data": None,
            }

        # ✅ Pass api_key to handle_user_message
        result = handle_user_message(chat_id, request.user_message, langgraph_app, api_key=x_api_key)

        return {
            "status": True,
            "message": "Message processed successfully",
            "data": result,
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        return {
            "status": False,
            "message": f"Error processing chat: {str(e)}",
            "data": None,
        }


# ============================================================
# ✅ GET FULL CONVERSATION
# ============================================================
@router.get("/conversation/{chat_id}")
async def get_full_conversation(chat_id: str):
    try:
        session = db.get_chat_session(chat_id)
        if not session:
            return {
                "status": False,
                "message": "Chat session not found",
                "data": None,
            }

        messages = session.get("messages", [])
        conversation_pairs = []
        current_pair: Dict[str, Any] = {}

        for msg in messages:
            if msg["role"] == "user":
                current_pair = {"user": msg["message"]}
            elif msg["role"] == "ai":
                current_pair["ai"] = msg["message"]
                conversation_pairs.append(current_pair)
                current_pair = {}

        return {
            "status": True,
            "message": "Conversation retrieved successfully",
            "data": {"chat_id": chat_id, "conversation": conversation_pairs},
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Error retrieving conversation: {str(e)}",
            "data": None,
        }


# ============================================================
# ✅ GET ATS RESUME JSON
# ============================================================

@router.get("/resume/json/{chat_id}")
async def get_ats_resume_json(
    chat_id: str,
    x_api_key: Optional[str] = Header(None, alias="x-api-key")
):
    try:
        if not x_api_key:
            raise HTTPException(400, "Missing LLM API key in header (x-api-key)")

        session = db.get_chat_session(chat_id)
        if not session:
            raise HTTPException(404, "Chat not found")

        experiences = session.get("resume_data", {}).get("experiences", [])
        if not experiences:
            raise HTTPException(400, "No experience saved yet")

        # Pass api_key if format_ats_experience_with_llm needs it
        ats_experience = format_ats_experience_with_llm(experiences[0], api_key=x_api_key)

        return {
            "status": True,
            "message": "AI-generated ATS JSON ready!",
            "data": ats_experience,
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(500, str(e))