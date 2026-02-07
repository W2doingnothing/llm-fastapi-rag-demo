from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
   
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入文本")


class ChatResponse(BaseModel):
    
    reply: str = Field(..., description="模型/系统回复内容")
    trace_id: str = Field(..., description="用于排查问题的追踪ID")


class ErrorResponse(BaseModel):
    """统一错误响应结构：前端/调用方可以稳定解析"""
    error: str = Field(..., description="错误类型（简短码）")
    message: str = Field(..., description="面向开发者/用户的错误信息")
    trace_id: str = Field(..., description="请求追踪ID")