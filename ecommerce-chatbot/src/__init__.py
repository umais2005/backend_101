from fastapi import FastAPI
from .chatbot.route import router

app = FastAPI()
app.include_router(router)

@app.get("/")
def root():
    return {"message": "Hello World"}

