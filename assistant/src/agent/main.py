from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.tools import ToolDefinition
import asyncio
from dotenv import load_dotenv
load_dotenv()
import os
import aiofiles
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Union
from pydantic_core import to_jsonable_python
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter 
from googleapiclient.discovery import build
import os
import pickle
import json

from pydantic_ai.tools import RunContext

@dataclass
class Deps:
    credentials: any
    user_email: str
    connected : bool = False

async def if_google_connected(ctx : RunContext[Deps], tool_defs: list[ToolDefinition]
) -> Union[list[ToolDefinition], None]:
    # user_info = await get_user_info(ctx.credentials)
    if not ctx.deps.connected:
        return [tool_def for tool_def in tool_defs if tool_def.name not in ("get_emails", "set_events")]
    return tool_defs

system_prompt = "You are a helpful Ai assistant, which helps the user to get and summarise latest emails, set event in the calendar, and answer general queries."
model = GroqModel('llama-3.3-70b-versatile', provider=GroqProvider(api_key=os.getenv("GROQ")))
agent = Agent(model, 
              system_prompt=system_prompt)

@agent.tool()
def get_emails(ctx: RunContext[Deps], n: int = 5):
    """
    Get the latest emails from the user's Gmail inbox.
    Args:
        n (int): The number of emails to retrieve. default is 5.
    """
    service = build('gmail', 'v1', credentials=ctx.deps.credentials)
    results = service.users().messages().list(userId='me', maxResults=n).execute()
    messages = results.get('messages', [])

    emails = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = msg_data['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        snippet = msg_data.get('snippet', '')
        emails.append({'subject': subject, 'from': sender, 'snippet': snippet})

    return emails


async def get_history(chat_id: str):
    try:
        async with aiofiles.open(f"{chat_id}.json", "r") as f:
            contents = await f.read()
            messages_json = json.loads(contents)
            history = ModelMessagesTypeAdapter.validate_python(messages_json)
            return history
    except FileNotFoundError:
        return []  # No history yet
    except Exception as e:
        print(f"Error reading history: {e}")
        return []

async def save_history(chat_id: str, messages):
    async with aiofiles.open(f"{chat_id}.json", "w") as f:
        json_dump = json.dumps(to_jsonable_python(messages), indent=2)
        await f.write(json_dump)

async def delete_history(chat_id: str):
    async with aiofiles.open(f"{chat_id}.json", "w") as f:
        await f.write("[]")

async def run_agent(deps: Deps, query: str, history=None):
    history = []

    if history:
        history = history
    elif deps.user_email:
        history = await get_history(deps.user_email)

    result = await agent.run(query, deps=deps, message_history=history)
    if deps.user_email:
        await save_history(deps.user_email, result.all_messages())
    else:
        history = result.all_messages()
    return result


if __name__ == "__main__":

    deps = Deps(credentials=None, user_email="umaismuhammad99")
    result = asyncio.run(run_agent(deps, "What can you do for me"))