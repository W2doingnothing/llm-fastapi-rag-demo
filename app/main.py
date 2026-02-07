import uuid
from fastapi import FastAPI, HTTPException
from app.schemas import ChatRequest, ChatResponse

app = FastAPI(title="LLM FastAPI RAG Demo")


@app.get("/health")
def health():

    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):

    try:

        trace_id = str(uuid.uuid4())


        reply = f"你说的是：{req.message}"

        return ChatResponse(reply=reply, trace_id=trace_id)

    except Exception as e:

        raise HTTPException(status_code=500, detail=f"server error: {e}")