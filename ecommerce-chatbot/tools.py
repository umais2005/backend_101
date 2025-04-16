from langchain_core.tools import tool
from langchain_groq import ChatGroq
from utils import get_embeddings, init_openai, init_supabase
import json


@tool
async def get_relevant_products(user_query: str, n_products:int = 10):
    """
    Get relevant products from the database based on the user query.
    Args:
        user_query (str): The user's query.
        n_products (int): The number of products to return.
    """
    user_query_embedding = await get_embeddings(user_query, init_openai())
    supabase_client = init_supabase()
    result = supabase_client.rpc("match_products", 
                        {"query_embedding": user_query_embedding,
                         "match_count" : n_products}).execute()
    relevant_products = [result.data for r in result]
    return json.dumps(relevant_products)




