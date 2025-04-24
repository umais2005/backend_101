from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
load_dotenv("../.env")

def init_openai()-> AsyncOpenAI:
    openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)
    return openai_client


async def get_embeddings(text: str, openai_client:AsyncOpenAI) -> list[str]:
    try:
        response = await openai_client.embeddings.create(
            input=text, 
            model="text-embedding-3-small",
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")