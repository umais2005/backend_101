from fastapi.routing import APIRouter
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
import os
import uuid
import pickle

router = APIRouter(prefix="/auth", tags="auth")

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # allow HTTP for testing

app = FastAPI()

# Paths and scopes
GOOGLE_CLIENT_SECRET_FILE = "credentials.json"
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events'
]
REDIRECT_URI = "http://localhost:8000/auth/callback"
TOKEN_DIR = "token_store"

# Make sure token_store exists
os.makedirs(TOKEN_DIR, exist_ok=True)

def get_credentials(username):
    token_path = f"{TOKEN_DIR}/{username}"
    if not os.path.exists(token_path):
        raise HTTPException(status_code=307, detail=f"/auth/login?username={username}")

    with open(token_path, "wb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return creds
    

@app.get("/login")
def login():
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    state = str(uuid.uuid4())  # unique session ID
    # flow.params['access_type'] = 'offline'
    # flow.params['prompt'] = 'consent'
    auth_url, _ = flow.authorization_url(state=state, include_granted_scopes=False, prompt='consent')
    return RedirectResponse(auth_url)

@app.get("/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    # print(code)
    state = request.query_params.get("state")

    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)

    credentials = flow.credentials
    access_token = credentials.token
    gmail = build("gmail", "v1", credentials=credentials)
    profile = gmail.users().getProfile(userId="me").execute()
    email = profile["emailAddress"]

    user_id = str(uuid.uuid4())  # you should use email instead ideally

    response = RedirectResponse("http://localhost:8000")
    response.set_cookie(key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production (HTTPS)
        max_age=3600,)
    
    return response