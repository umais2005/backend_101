import os
from dotenv import load_dotenv
import supabase
load_dotenv("../.env")

def init_supabase() -> supabase.Client:
    supabase_client = supabase.create_client(
        supabase_url="https://xkbdivjljqvlmfsysyno.supabase.co",
        supabase_key=os.getenv("SUPABASE_API_KEY")
        )
    return supabase_client

def get_supabase_client() :
    supabase_client = init_supabase()
    
    try:
        # `yield` provides the client to the route handler
        yield supabase_client
    finally:
        # Optionally, add cleanup code here, e.g., closing connections
        pass