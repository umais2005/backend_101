from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from src.agent.main import agent, Deps
import httpx
from dotenv import load_dotenv
load_dotenv()
import os

# Create the FastAPI app
app = FastAPI(title="My Personal Chat App")

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

# Models for data
class ChatMessage(BaseModel):
    message: str

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
        calendar_service = build("calendar", "v3", credentials=user_credentials)
        
        # Use the credentials to access the Google OAuth2 API
        service = build('oauth2', 'v2', credentials=user_credentials)
        user_info = service.userinfo().get().execute()
        return user_info

    except Exception as e:
        print(f"Error getting user info: {e}")
        return None

# Step 3: Your chat endpoint that uses Google data
@app.post("/chat")
async def chat(message: ChatMessage):
    """
    This is your main chat endpoint
    It can use your Google credentials to access emails, calendar, etc.
    """
    global user_logged_in, google_access_token, user_info, user_credentials
    connected = bool(user_info)
    
    if user_logged_in:
        deps = Deps(credentials=user_credentials, user_email=user_info.get("email") if user_info else None, connected=connected)
    else:
        deps = Deps(credentials=None, user_email=None)
    
    result = await agent.run(message.message, deps=deps)
    return result
    
    # Check if you're logged in
    # if not user_logged_in:
    #     raise HTTPException(status_code=401, detail="Please login with Google first. Go to /login")
    # Run the agent with the message
    # result = await agent.run_stream(message.message, deps=deps)
    
     


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