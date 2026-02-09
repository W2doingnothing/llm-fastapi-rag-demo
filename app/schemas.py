# app/schemas.py
"""
Pydantic Schemas：定义输入/输出“合同”
目的：
1) 自动做参数校验（避免写大量 if）
2) 统一响应结构（前端/调用方稳定解析）
3) /docs 自动生成清晰文档
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """客户端请求：用户输入"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户输入文本")


class ChatResponse(BaseModel):
    """成功响应：reply + trace_id"""
    reply: str = Field(..., description="模型/系统回复内容")
    trace_id: str = Field(..., description="请求追踪ID")


class ErrorResponse(BaseModel):
    """失败响应：统一错误结构（注意：失败不应该混进 reply）"""
    error: str = Field(..., description="错误类型（简短码）")
    message: str = Field(..., description="错误说明（给调用方看的）")
    trace_id: str = Field(..., description="请求追踪ID")
