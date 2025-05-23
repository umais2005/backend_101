from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.models.groq import GroqModel
import asyncio
from dotenv import load_dotenv
load_dotenv()
import os
import logfire_api
import asyncio
from dataclasses import dataclass
from datetime import date

from pydantic_ai import Agent
from googleapiclient.discovery import build
import os
import pickle

from pydantic_ai.tools import RunContext

@dataclass
class Deps:
    service: any
    user_id: str


system_prompt = "You are a helpful Ai assistant. Answer concisely to the user"
model = GroqModel('llama-3.3-70b-versatile', provider=GroqProvider(api_key=os.getenv("GROQ")))
agent = Agent(model, 
              system_prompt=system_prompt)

@agent.tool()
def get_emails(ctx: RunContext, n: int = 5):
    """
    Get the latest emails from the user's Gmail inbox.
    Args:
        n (int): The number of emails to retrieve. default is 5.
    """
    service = ctx.service
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

resp = agent.run_sync("Hi, what can you do for me?")
print(resp)
print(resp.all_messages())