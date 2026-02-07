from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
   
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入文本")


class ChatResponse(BaseModel):
    
    reply: str = Field(..., description="模型/系统回复内容")
    trace_id: str = Field(..., description="用于排查问题的追踪ID")
