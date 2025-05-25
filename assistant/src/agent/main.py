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
    connected: bool = False


class GmailAgent:
    def __init__(self, groq_api_key: str = None):
        """Initialize the Gmail Agent with dependencies."""
        # Initialize model and agent
        groq_key = groq_api_key or os.getenv("GROQ")
        self.model = GroqModel('llama-3.3-70b-versatile', provider=GroqProvider(api_key=groq_key))
        
        self.system_prompt = (
            "You are a helpful AI assistant, which helps the user to get and summarise "
            "latest emails, set event in the calendar, and answer general queries."
            "If you do not have access to these tools, this means that user has not connected their Google account yet."
            "You can tell the user to connect their Google account to use these features or you can answer general queries without using tools."
            "Otherwise, you have access to the following tools: "
            "get_emails: Get the latest emails from the user's Gmail inbox, "
            "set_events: Set an event in the user's Google Calendar."
            "Then use the tool output to give a final answer to the user."
        )
        
        self.agent = Agent(self.model, system_prompt=self.system_prompt, prepare_tools=self.filter_tools_by_connection)
        
        # Register tools
        self._register_tools()
    
    def _register_tools(self):
        """Register all agent tools."""
        @self.agent.tool()
        def get_emails(ctx: RunContext[Deps], n: int = 5):
            """
            Get the latest emails from the user's Gmail inbox.
            Args:
                n (int): The number of emails to retrieve. default is 5.
            """
            return self._get_emails_impl(ctx, n)
    
    def _get_emails_impl(self, ctx: RunContext[Deps], n: int = 5):
        """Implementation of get_emails tool."""
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
    
    async def filter_tools_by_connection(self, ctx: RunContext[Deps], tool_defs: list[ToolDefinition]) -> Union[list[ToolDefinition], None]:
        """Filter available tools based on Google connection status."""
        if not ctx.deps.connected:
            return [tool_def for tool_def in tool_defs if tool_def.name not in ("get_emails", "set_events")]
        return tool_defs
    
    async def get_history(self, history_id: str):
        """Retrieve chat history from file."""
        os.makedirs("./chat_histories", exist_ok=True)
        path = f"./chat_histories/{history_id}.json"
        try:
            async with aiofiles.open(path, "r") as f:
                contents = await f.read()
                messages_json = json.loads(contents)
                history = ModelMessagesTypeAdapter.validate_python(messages_json)
                return history
        except FileNotFoundError:
            async with aiofiles.open(path, "w") as f:
                json.dump([], f)
            return [] 
         # No history yet
        except Exception as e:
            print(f"Error reading history: {e}")
            return []

    async def save_history(self, history_id: str, messages):
        """Save chat history to file."""
        async with aiofiles.open(f"./chat_histories/{history_id}.json", "w") as f:
            json_dump = json.dumps(to_jsonable_python(messages), indent=2)
            await f.write(json_dump)

    async def delete_history(self, history_id: str):
        """Delete chat history file."""
        async with aiofiles.open(f"./chat_histories/{history_id}.json", "w") as f:
            await f.write("[]")

    async def run_agent(self, deps: Deps, query: str, history=None):
        """Run the agent with the given query and dependencies."""
        if history is None:
            history = []

        if history:
            history = history
        elif deps.user_email:
            history = await self.get_history(deps.user_email)

        result = await self.agent.run(query, deps=deps, message_history=history)
        
        if deps.user_email:
            await self.save_history(deps.user_email, result.all_messages())
        else:
            history = result.all_messages()
            
        return result


if __name__ == "__main__":

    gmail_agent = GmailAgent()

    # Create dependencies
    deps = Deps(
        credentials=None,
        user_email="user@example.com", 
        connected=False
    )

    # Run the agent
    result = asyncio.run(gmail_agent.run_agent(deps, "What was my last query?"))
    print(result.output)