from supabase import Client
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.messages import ModelResponse, ModelRequest, UserPromptPart, TextPart
from openai import AsyncOpenAI
from utils import get_embeddings, init_supabase, init_openai
import json

model = GroqModel('llama-3.3-70b-versatile')

@dataclass
class Deps:
    supabase_client: Client
    openai_client : AsyncOpenAI

system_prompt="""
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
async def get_relevant_products(ctx: RunContext[Deps],user_query: str, n_products:int = 10) -> list[dict]:
    """
    Get relevant products from the database based on the user query.
    Args:
        user_query (str): The user's query.
        n_products (int): The number of products to return.
    """
    user_query_embedding = await get_embeddings(user_query, ctx.deps.openai_client)
    result = ctx.deps.supabase_client.rpc("match_products", 
                        {"query_embedding": user_query_embedding,
                         "match_count" : n_products}).execute()
    relevant_products = [result.data for r in result]
    return json.dumps(relevant_products)
    # return relevant_products


async def main():
    # Initialize the clients
        deps = Deps(
            openai_client=init_openai(),
            supabase_client=init_supabase()
    )
        messages = []
        try:
            while True:
                user_input = input("> ").strip()
                if user_input.lower() == 'quit':
                    break

                # Run the agent with streaming
                result = await agent.run(
                    user_input,
                    deps=deps,
                    message_history=messages
                )

                # Store the user message
                messages.append(
                    ModelRequest(parts=[UserPromptPart(content=user_input)])
                )

                # Store itermediatry messages like tool calls and responses
                filtered_messages = [msg for msg in result.new_messages() 
                                if not (hasattr(msg, 'parts') and 
                                        any(part.part_kind == 'user-prompt' or part.part_kind == 'text' for part in msg.parts))]
                messages.extend(filtered_messages)

                # Optional if you want to print out tool calls and responses
                # print(filtered_messages + "\n\n")

                print(result.data)

                # Add the final response from the agent
                messages.append(
                    ModelResponse(parts=[TextPart(content=result.data)])
                )
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())