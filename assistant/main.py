from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from starlette.exceptions import HTTPException as StarletteHTTPException
from src.auth.main import router as auth_router
import os
import uuid
import pickle
from datetime import datetime, timedelta

app = FastAPI()
app.include_router(auth_router)

@app.get("/")
def hello():
    return {"message": "Server is Running"}
    

@app.get("/chat")
def get_chat():
    pass

@app.post("/chat")
def post_chat():
    pass
