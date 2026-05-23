from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.chat import ChatMessage, ChatRole
from app.services import sqlite_store
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    observation_id: str
    question: str


class ChatTurnResponse(BaseModel):
    user_message: ChatMessage
    assistant_message: ChatMessage


_service: ChatService | None = None


def get_service() -> ChatService:
    global _service
    if _service is None:
        _service = ChatService()
    return _service


@router.post("", response_model=ChatTurnResponse)
def chat(req: ChatRequest) -> ChatTurnResponse:
    if not req.question.strip():
        raise HTTPException(400, "question must not be empty")

    observation = sqlite_store.get_observation(req.observation_id)
    if not observation:
        raise HTTPException(404, f"Observation not found: {req.observation_id}")

    history = sqlite_store.list_chat_messages(req.observation_id)
    report = sqlite_store.get_latest_report_for_observation(req.observation_id)

    user_msg = ChatMessage(
        message_id=str(uuid.uuid4()),
        observation_id=req.observation_id,
        role=ChatRole.USER,
        content=req.question.strip(),
    )
    sqlite_store.save_chat_message(user_msg)

    assistant_msg = get_service().reply(
        observation=observation,
        report=report,
        history=[*history, user_msg],
        question=req.question.strip(),
    )
    sqlite_store.save_chat_message(assistant_msg)

    return ChatTurnResponse(user_message=user_msg, assistant_message=assistant_msg)


@router.get("/{observation_id}", response_model=list[ChatMessage])
def history(observation_id: str) -> list[ChatMessage]:
    if not sqlite_store.get_observation(observation_id):
        raise HTTPException(404, f"Observation not found: {observation_id}")
    return sqlite_store.list_chat_messages(observation_id)
