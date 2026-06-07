from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_current_user
from app.models import User
from app.services.chatbot_service import generate_chat_response

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat", response_model=ChatResponse)
async def chat_with_bot(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")
        
    reply_text = await generate_chat_response(current_user.id, request.message, db)
    return ChatResponse(reply=reply_text)
