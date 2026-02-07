import logging
import uuid
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.schemas import ChatRequest, ChatResponse, ErrorResponse

# ---------- logging 配置 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | trace_id=%(trace_id)s | %(message)s",
)
logger = logging.getLogger("app")


class TraceIdFilter(logging.Filter):
    """给日志补 trace_id 字段，避免 format 报 KeyError"""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return True


logger.addFilter(TraceIdFilter())

# ---------- FastAPI app ----------
app = FastAPI(title="LLM FastAPI RAG Demo")


# ---------- Middleware：给每个请求注入 trace_id ----------
class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

        # 记录请求入站日志（方法/路径）
        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={"trace_id": trace_id},
        )

        response = await call_next(request)

        # 把 trace_id 也放到响应头里（方便前端/调试）
        response.headers["X-Trace-Id"] = trace_id
        return response


app.add_middleware(TraceIdMiddleware)


# ---------- 全局异常处理：参数校验错误 ----------
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


# ---------- 全局异常处理：兜底未知错误 ----------
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


# ---------- API ----------
@app.get("/health")
def health(request: Request):
    trace_id = getattr(request.state, "trace_id", "-")
    logger.info("Health check ok", extra={"trace_id": trace_id})
    return {"status": "ok", "trace_id": trace_id}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    trace_id = getattr(request.state, "trace_id", "-")

    # 业务日志：记录输入长度（不要直接打用户隐私内容，先养成习惯）
    logger.info(f"Chat request received, len={len(req.message)}", extra={"trace_id": trace_id})

    # 先做“假 LLM”
    reply = f"你说的是：{req.message}"

    logger.info("Chat reply generated", extra={"trace_id": trace_id})
    return ChatResponse(reply=reply, trace_id=trace_id)
    