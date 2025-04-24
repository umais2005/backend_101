from supabase import Client
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.messages import ModelResponse, ModelRequest, UserPromptPart, TextPart
from openai import AsyncOpenAI
from src.utils import get_embeddings, init_supabase, init_openai
import json
import redis

r = redis.Redis()


model = GroqModel('llama-3.3-70b-versatile')

@dataclass
class Deps:
    supabase_client: Client
    openai_client: AsyncOpenAI

system_prompt = """
You are an ecommerce customer support agent. You will provide service to customers who are seeking to buy from 
your Ammunitions and gun store, but need some recommendations. You will provide them with relevant products based on their queries.
you will use the get_relevant_products function to get the relevant products from the database.
"""

agent = Agent(model, 
              deps_type=Deps,
              system_prompt=system_prompt,
              result_retries=2
)

@agent.tool
async def get_relevant_products(ctx: RunContext[Deps], user_query: str, n_products: int = 10) -> list[dict]:
    """
    Get relevant products from the database based on the user query.
    """
    user_query_embedding = await get_embeddings(user_query, ctx.deps.openai_client)
    result = ctx.deps.supabase_client.rpc("match_products", {
        "query_embedding": user_query_embedding,
        "match_count": n_products
    }).execute()
    relevant_products = [result.data for r in result]
    return json.dumps(relevant_products)


# 🚀 Service Class
class EcommerceChatbotService:
    def __init__(self, user_id=None, thread_id=None):
        self.user_id = user_id
        self.thread_id = thread_id
        self.deps = Deps(
            openai_client=init_openai(),
            supabase_client=init_supabase()
        )
        self.messages = self.get_chat_history()

    def get_chat_history(self):
        """
        Get the chat history for the current thread.
        """
        if self.user_id:
            # Return user chat history.
            pass
        else:
            # Return temp chat from redis using thread id
            pass


    def save_chat_history(self):
        pass

    async def chat(self, user_input: str, user_id=None) -> str:
        if user_id:
            self.messages = self.get_chat_history(user_id=user_id)
        result = await agent.run(
            user_input,
            deps=self.deps,
            message_history=self.messages
        )

        # Store messages
        self.messages.append(
            ModelRequest(parts=[UserPromptPart(content=user_input)])
        )

        filtered_messages = [
            msg for msg in result.new_messages()
            if not (hasattr(msg, 'parts') and any(
                part.part_kind == 'user-prompt' or part.part_kind == 'text'
                for part in msg.parts))
        ]
        self.messages.extend(filtered_messages)

        self.messages.append(
            ModelResponse(parts=[TextPart(content=result.data)])
        )
        if user_id:
            self.save_chat_history()

        return result.data


# 🧪 Optional CLI Entrypoint for testing
async def main():
    bot = EcommerceChatbotService()
    print("Ecommerce Chatbot Ready (type 'quit' to exit)")
    try:
        while True:
            user_input = input("> ").strip()
            if user_input.lower() == 'quit':
                break
            response = await bot.chat(user_input)
            print(response)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
