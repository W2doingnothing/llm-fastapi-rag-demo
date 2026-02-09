# app/llm_client.py
"""
LLM 客户端封装（非常关键的工程边界）：
- 只做一件事：给 message -> 返回 reply
- 失败时：抛异常（不要返回“错误字符串”混进 reply）
原因：
1) 保持 API 合同：成功/失败通道分离
2) 避免把上游错误细节泄露给用户
3) 让 main.py 统一做错误响应与日志
"""

import time
from typing import Optional
import json
from typing import Any, Dict
from openai import OpenAI
from openai import RateLimitError, APIConnectionError, APITimeoutError, APIStatusError

from app.settings import settings


class LLMUpstreamError(RuntimeError):
    """上游 LLM 调用失败（统一异常类型，便于 API 层处理）"""


def _chat_mock(message: str) -> str:
    return f"你说的是：{message}"


def _chat_openai_compatible(message: str) -> str:
    """
    调用 OpenAI / OpenAI-compatible 网关
    注意：
    - 不在这里记录 trace_id（trace_id 属于 API 层的请求上下文）
    - 不把上游错误 body 直接返回给用户（避免泄露）
    """
    if not settings.openai_api_key:
        raise LLMUpstreamError("OPENAI_API_KEY is not set")

    # 只用我们自己的重试；避免 SDK 重试叠加
    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        max_retries=0,
    )

    max_attempts = max(1, settings.openai_max_attempts)
    base_sleep = 1.0  # 1s, 2s, 4s...

    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "你是一个简洁、专业的助手。"},
                    {"role": "user", "content": message},
                ],
                timeout=settings.openai_timeout,
            )
            content = resp.choices[0].message.content or ""
            return content.strip()

        except RateLimitError as e:
            # 429：免费池常见，指数退避重试
            last_exc = e
            if attempt < max_attempts:
                time.sleep(base_sleep * (2 ** (attempt - 1)))
                continue
            raise LLMUpstreamError("Upstream rate limited (429)") from e

        except (APITimeoutError, APIConnectionError) as e:
            # 连接/超时：也可以重试
            last_exc = e
            if attempt < max_attempts:
                time.sleep(base_sleep * (2 ** (attempt - 1)))
                continue
            raise LLMUpstreamError("Upstream timeout/connection error") from e

        except APIStatusError as e:
            # 其他 HTTP 错误：通常无需重试，直接上抛
            raise LLMUpstreamError(f"Upstream HTTP error {e.status_code}") from e

        except Exception as e:
            # 未知错误：不把细节吐给用户，但保留异常链
            last_exc = e
            raise LLMUpstreamError("Unexpected upstream error") from e

    # 理论不会走到这
    raise LLMUpstreamError("Upstream failed") from last_exc


def chat(message: str) -> str:
    """
    对外唯一入口
    - 成功：返回 reply
    - 失败：抛 LLMUpstreamError
    """
    provider = settings.llm_provider.lower()

    if provider == "mock":
        return _chat_mock(message)

    if provider == "openai":
        return _chat_openai_compatible(message)

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

def _build_structured_prompt(user_message: str) -> str:
    """
    构造强约束提示词：只允许输出 JSON
    """
    schema_desc = {
        "intent": "question|coding|planning|other",
        "answer": "string",
        "confidence": "number between 0 and 1",
        "need_human": "boolean",
    }

    # 注意：这里是给模型看的约束，不是给用户看的
    return (
        "你必须只输出严格合法的 JSON（不要 Markdown，不要代码块，不要解释）。\n"
        "JSON 必须包含且仅包含以下字段：intent, answer, confidence, need_human。\n"
        f"字段说明：{schema_desc}\n"
        "intent 只能取：question/coding/planning/other。\n"
        "confidence 必须是 0~1 之间的小数。\n"
        "need_human 是布尔值 true/false。\n"
        "下面是用户输入：\n"
        f"{user_message}\n"
        "请输出 JSON："
    )


def chat_structured(message: str) -> Dict[str, Any]:
    """
    结构化输出（关键）：
    - 成功：返回 dict（可被 API 层进一步用 Pydantic 校验）
    - 失败：抛 LLMUpstreamError（不要返回“错误字符串”）
    """
    # 第一次尝试：强约束 prompt
    prompt1 = _build_structured_prompt(message)
    text1 = chat(prompt1)  # 复用你现有的 chat()（它会走 provider / 重试 / 抛异常）

    try:
        obj = json.loads(text1)
        if not isinstance(obj, dict):
            raise ValueError("JSON root is not an object")
        return obj
    except Exception:
        # 第二次尝试：纠错 prompt（告诉模型上次不合格）
        prompt2 = (
            "你刚才的输出不是严格合法的 JSON，导致解析失败。\n"
            "请你重新输出严格合法 JSON：不要 Markdown，不要代码块，不要多余文字。\n"
            + _build_structured_prompt(message)
        )
        text2 = chat(prompt2)
        try:
            obj2 = json.loads(text2)
            if not isinstance(obj2, dict):
                raise ValueError("JSON root is not an object")
            return obj2
        except Exception as e2:
            # 统一抛上游错误：交给 API 层返回 502 + 统一 ErrorResponse
            raise LLMUpstreamError("Structured JSON parse failed") from e2