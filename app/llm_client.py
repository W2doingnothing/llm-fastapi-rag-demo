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
