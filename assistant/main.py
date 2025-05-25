import json
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from mistralai import Chat
from pydantic import BaseModel

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from contextlib import asynccontextmanager
from googleapiclient.discovery import build
from pydantic_ai import UnexpectedModelBehavior
from src.agent.main import GmailAgent, Deps
import httpx
from typing import Literal,  List, Optional
from dotenv import load_dotenv
import os
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
load_dotenv()

class AppState:
    def __init__(self):
        self.gmail_agent: Optional[GmailAgent] = None

class ChatMessage(BaseModel):
    message: str


# Models for data
class ChatResponse(BaseModel):
    message: str
    role : Literal["user", "assistant"]
    timestamp: Optional[str] = None


class MessageHistory(BaseModel):
    messages: List[ChatResponse] | None = None
    total_count: int


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the GmailAgent when the application starts."""
    print("Starting up Gmail Agent...")
    try:
        app_state.gmail_agent = GmailAgent()
        print("Gmail Agent initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Gmail Agent: {e}")
        raise
    
    yield
    
    print("Shutting down Gmail Agent...")

# Create the FastAPI app
app = FastAPI(title="My Personal Chat App", lifespan=lifespan)

# Google OAuth2 credentials
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your_google_client_id_here")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "your_google_client_secret_here")
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

REDIRECT_URI = "http://localhost:8000/auth/callback"

CLIENT_CONFIG = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

# Simple storage for the single user (you!)
user_credentials = None
user_logged_in = False
google_access_token = None
user_info = None
gmail_service = None
calendar_service = None



# Step 1: Start the login process
@app.get("/login")
async def login():
    """
    This starts the Google OAuth flow
    Redirects user to Google's authorization page
    """
    print(user_logged_in)
    if user_logged_in:
        return RedirectResponse(url="http://localhost:8000/", status_code=302)
    

    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )


    auth_url , _ = flow.authorization_url(
            access_type='offline',  # Enables refresh token
        include_granted_scopes='false', 
        prompt='consent'  # Forces the user to re-consent
    )
    
    # Redirect user to Google
    return RedirectResponse(url=auth_url)

# Step 2: Google redirects back here with the code
@app.get("/auth/callback")
async def google_callback(request: Request):
    """
    Handle the OAuth callback using Google's Flow class
    """
    global user_logged_in, user_credentials, user_info
    
    try:
        # Create the Flow object again
        flow = Flow.from_client_config(
            CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Get the full callback URL with all parameters
        authorization_response = str(request.url)
        
        # Exchange the authorization code for credentials
        flow.fetch_token(authorization_response=authorization_response)
        print("Token:", flow.credentials.token)
        print("Valid:", flow.credentials.valid)
        print("Expired:", flow.credentials.expired)
        print("Refresh Token:", flow.credentials.refresh_token)

        # Get the credentials
        user_credentials = flow.credentials
        # Use the credentials to get user info
        user_info = await get_user_info(user_credentials)
        
        user_logged_in = True
        
        response = RedirectResponse(url="http://localhost:8000/", status_code=302)
        response.set_cookie(key="credentials", value=user_credentials.to_json(), httponly=True)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
            

async def get_user_info(user_credentials):
    if not user_credentials:
        print("No credentials found.")
        return None

    # Refresh token if expired
    if not user_credentials.valid:
        if user_credentials.expired and user_credentials.refresh_token:
            try:
                user_credentials.refresh(GoogleRequest())
            except Exception as e:
                print(f"Error refreshing access token: {e}")
                return None
        else:
            print("Credentials are invalid and cannot be refreshed.")
            return None

    try:
        
        # Use the credentials to access the Google OAuth2 API
        service = build('oauth2', 'v2', credentials=user_credentials)
        user_info = service.userinfo().get().execute()
        return user_info

    except Exception as e:
        print(f"Error getting user info: {e}")
        return None
    
def get_gmail_agent() -> GmailAgent:
    """Dependency to get the Gmail agent instance."""
    if app_state.gmail_agent is None:
        raise HTTPException(status_code=500, detail="Gmail Agent not initialized")
    return app_state.gmail_agent

def to_chat_message_history(msgs : list[ModelMessage]) -> MessageHistory:
    final_msgs = []
    for m in msgs:
        first_part = m.parts[0]
        if isinstance(m, ModelRequest):
            if isinstance(first_part, UserPromptPart):
                assert isinstance(first_part.content, str)
                final_msgs.append(m)       
        
        elif isinstance(m, ModelResponse):
            if isinstance(first_part, TextPart):
                final_msgs.append(m)
        else:
            raise UnexpectedModelBehavior(f'Unexpected message type for chat app: {m}')
        
        return MessageHistory(
            messages=final_msgs,
            total_count=len(final_msgs)
        )

@app.get("/chat/messages", response_model=MessageHistory)
async def get_chat_messages(
    gmail_agent: GmailAgent = Depends(get_gmail_agent)
):
    """Get chat message history for the current user."""
    global user_info
    
    if not user_logged_in or not user_info:
        raise HTTPException(status_code=401, detail="Please login with Google first")
    
    user_email = user_info.get("email")
    if not user_email:
        # raise HTTPException(status_code=400, detail="User email not available")
        return MessageHistory(messages=[], total_count=0)
    
    try:
        msgs = await gmail_agent.get_history(user_email)
        filtered_msgs = to_chat_message_history(msgs)
        return MessageHistory(
            messages=filtered_msgs,
            total_count=len(msgs)
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve messages: {str(e)}")


@app.delete("/chat/messages")
async def delete_chat_messages(
    gmail_agent: GmailAgent = Depends(get_gmail_agent)
):
    """Delete chat message history for the current user."""
    global user_info
    
    if not user_logged_in or not user_info:
        raise HTTPException(status_code=401, detail="Please login with Google first")
    
    user_email = user_info.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not available")
    
    try:
        await gmail_agent.delete_history(user_email)
        return {"message": "Chat history deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete messages: {str(e)}")


# Step 3: Your chat endpoint that uses Google data
@app.post("/chat", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    gmail_agent: GmailAgent = Depends(get_gmail_agent)
):
    """
    Main chat endpoint that uses Google data.
    It can use your Google credentials to access emails, calendar, etc.
    """
    global user_logged_in, google_access_token, user_info, user_credentials
    
    try:
        # Create dependencies based on user login status
        connected = bool(user_info)
        
        if user_logged_in and user_credentials:
            deps = Deps(
                credentials=user_credentials, 
                user_email=user_info.get("email") if user_info else None, 
                connected=connected
            )
        else:
            deps = Deps(
                credentials=None, 
                user_email=None, 
                connected=False
            )
        
        # Run the agent with the message
        result = await gmail_agent.run_agent(deps, message.message)
        print(result.output)
        latest_msg = result.all_messages()[-1]
        # Extract response text from result
        return ChatResponse(
            message=latest_msg.parts[0].content if latest_msg.parts else "No response",
            role="assistant",
            timestamp=latest_msg.timestamp if hasattr(latest_msg, 'timestamp') else None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


# Check if you're logged in
@app.get("/status")
async def get_status():
    """
    Check if you're logged in and see your info
    """
    if user_logged_in:
        return {
            "logged_in": True,
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "message": "You're ready to chat!",
            "has_google_access": google_access_token is not None
        }
    else:
        return {
            "logged_in": False,
            "message": "Please login with Google first",
            "login_url": "/login"
        }

# Logout (reset everything)
@app.get("/logout")
async def logout():
    """
    Logout and clear credentials
    """
    global user_logged_in, user_credentials, user_info
    
    # Revoke the credentials if possible
    if user_credentials and user_credentials.token:
        try:
            # Revoke the token
            import requests
            requests.post('https://oauth2.googleapis.com/revoke',
                         params={'token': user_credentials.token},
                         headers={'content-type': 'application/x-www-form-urlencoded'})
        except Exception as e:
            print(e)
            pass  # Ignore errors during revocation
    
    user_logged_in = False
    user_credentials = None
    user_info = None
    
    return RedirectResponse(url="http://localhost:8000/", status_code=302)


# Home page with simple instructions
@app.get("/")
async def root():
    """
    Home page with instructions
    """
    if user_logged_in:
        return HTMLResponse(f"""
            <html>
                <body>
                    <h1>Personal Chat App</h1>
                    <p>Welcome {user_info['name']}! You're logged in.</p>
                    <p><a href="/docs">Go to API docs to test chat</a></p>
                    <p><a href="/status">Check your status</a></p>
                    <form method="get" action="/logout">
                        <button type="submit">Logout</button>
                    </form>
                </body>
            </html>
        """)
    else:
        return HTMLResponse("""
            <html>
                <body>
                    <h1>Personal Chat App</h1>
                    <p>You're not logged in.</p>
                    <p><a href="/login">Click here to login with Google</a></p>
                </body>
            </html>
        """)