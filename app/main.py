# app/main.py
from fastapi import FastAPI

# Create the FastAPI application instance
app = FastAPI()

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}
