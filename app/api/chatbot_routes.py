from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_current_user
from app.models import User
from app.services.chatbot_service import generate_chat_response, ChatbotUnavailableError
from app.limiter import limiter, authenticated_user_key

router = APIRouter()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute;60/hour", key_func=authenticated_user_key)
async def chat_with_bot(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")
        
    try:
        reply_text = await generate_chat_response(current_user.id, payload.message, db)
    except ChatbotUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    return ChatResponse(reply=reply_text)
