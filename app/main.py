# app/main.py
"""
FastAPI 入口：
- trace_id 中间件
- 统一异常处理（参数错误/未知错误）
- /chat 业务接口：调用 llm_client.chat()
  - 成功返回 ChatResponse
  - 上游失败返回 502（并由统一错误响应结构承载）
"""

import logging
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.llm_client import chat as llm_chat, LLMUpstreamError

# ---------- logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | trace_id=%(trace_id)s | %(message)s",
)
logger = logging.getLogger("app")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return True


logger.addFilter(TraceIdFilter())

# ---------- app ----------
app = FastAPI(title="LLM FastAPI RAG Demo")


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={"trace_id": trace_id},
        )

        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response


app.add_middleware(TraceIdMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.warning(f"Validation error: {exc.errors()}", extra={"trace_id": trace_id})

    body = ErrorResponse(
        error="VALIDATION_ERROR",
        message="请求参数不合法，请检查字段类型/长度/必填项",
        trace_id=trace_id,
    )
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    统一处理 HTTPException（例如我们手动 raise 的 502）
    """
    trace_id = getattr(request.state, "trace_id", "-")
    logger.warning(f"HTTPException {exc.status_code}: {exc.detail}", extra={"trace_id": trace_id})

    # 把各种 HTTPException 也统一成 ErrorResponse
    body = ErrorResponse(
        error="HTTP_ERROR",
        message=str(exc.detail),
        trace_id=trace_id,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.exception(f"Unhandled error: {exc}", extra={"trace_id": trace_id})

    body = ErrorResponse(
        error="INTERNAL_ERROR",
        message="服务器内部错误",
        trace_id=trace_id,
    )
    return JSONResponse(status_code=500, content=body.model_dump())


@app.get("/health")
def health(request: Request):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.info("Health check ok", extra={"trace_id": trace_id})
    return {"status": "ok", "trace_id": trace_id}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    trace_id = getattr(request.state, "trace_id", "-")

    # 不打印用户原文（培养安全意识），只记录长度
    logger.info(f"Chat request received, len={len(req.message)}", extra={"trace_id": trace_id})

    try:
        reply = llm_chat(req.message)
        logger.info("Chat reply generated", extra={"trace_id": trace_id})
        return ChatResponse(reply=reply, trace_id=trace_id)

    except LLMUpstreamError as e:
        # 上游失败：返回 502（Bad Gateway）
        # 细节写日志，不直接返回给用户
        logger.warning(f"LLM upstream error: {e}", extra={"trace_id": trace_id})
        raise HTTPException(status_code=502, detail="LLM upstream error")
