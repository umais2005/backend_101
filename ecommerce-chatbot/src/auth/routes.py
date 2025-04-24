from fastapi import APIRouter
from src.auth.schemas import User
from src.db.main import get_supabase_client
from supabase import Client


router = APIRouter(prefix="auth" ,tags=['auth'])

@router.post("/signup", response_model=User)
async def signup(userdata : ):
