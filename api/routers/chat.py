from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Header

from app.db import is_db_configured, save_chat_message, load_chat_history
from app.chat_commands import dispatch

router = APIRouter(prefix="/api/chat")


class ChatMessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime | None = None


class SendRequest(BaseModel):
    # Commands are short; the cap stops a scripted POST filling the free-tier DB.
    message: str = Field(min_length=1, max_length=500)


def _require_db():
    if not is_db_configured():
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured — chat history needs Postgres")


@router.get("/history", response_model=list[ChatMessageOut])
def get_history(x_session_id: Optional[str] = Header(None, alias="X-Session-Id")):
    _require_db()
    df = load_chat_history(session_id=x_session_id)
    return [
        ChatMessageOut(role=r.role, content=r.content, created_at=r.created_at)
        for r in df.itertuples()
    ]


@router.post("/send", response_model=ChatMessageOut)
def send_message(
    req: SendRequest,
    x_chat_token: Optional[str] = Header(None, alias="X-Chat-Token"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    _require_db()
    save_chat_message("user", req.message, x_session_id)
    reply = dispatch(req.message, token=x_chat_token, session_id=x_session_id)
    save_chat_message("assistant", reply, x_session_id)
    return ChatMessageOut(role="assistant", content=reply, created_at=datetime.utcnow())
