from fastapi import APIRouter, Depends
from .service import EcommerceChatbotService
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["chatbot"])


class ChatRequest(BaseModel):
    user_input : str 

@router.post("/")
async def chat(request: ChatRequest):
    service = EcommerceChatbotService()
    response = await service.chat(user_input=request.user_input)
    return {"response": response}

