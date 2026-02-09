# app/llm_client.py
import time
from openai import OpenAI
from openai import RateLimitError, APIConnectionError, APITimeoutError, APIStatusError
from app.settings import settings


def _chat_mock(message: str) -> str:
    return f"你说的是：{message}"


def _err_detail(e: Exception) -> str:
    body = getattr(e, "body", None)
    msg = getattr(e, "message", None)
    parts = [type(e).__name__]
    if msg:
        parts.append(f"message={msg}")
    if body:
        parts.append(f"body={body}")
    return " | ".join(parts)


def _chat_openai(message: str) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        max_retries=2,  # ✅ 给 SDK 一点重试（连接抖动时很有用）
    )

    # ✅ 我们再额外做 3 次“退避重试”，专门应对免费池的 429 / 排队超时
    max_attempts = 3
    base_sleep = 1.0  # 1s, 2s, 4s...

    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "你是一个简洁、专业的助手。"},
                    {"role": "user", "content": message},
                ],
                timeout=settings.openai_timeout,  # ✅ 建议 60
            )
            return resp.choices[0].message.content.strip()

        except RateLimitError as e:
            detail = _err_detail(e)
            if attempt >= max_attempts:
                return f"❌ 429 Too Many Requests（已重试{max_attempts}次仍失败）: {detail}"
            time.sleep(base_sleep * (2 ** (attempt - 1)))

        except (APITimeoutError, APIConnectionError) as e:
            detail = _err_detail(e)
            if attempt >= max_attempts:
                return f"❌ 连接/超时（已重试{max_attempts}次仍失败）: {detail}"
            time.sleep(base_sleep * (2 ** (attempt - 1)))

        except APIStatusError as e:
            return f"❌ 上游HTTP错误 {e.status_code}: {_err_detail(e)}"

        except Exception as e:
            return f"❌ 服务内部异常: {_err_detail(e)}"


def chat(message: str) -> str:
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return _chat_mock(message)
    if provider == "openai":
        return _chat_openai(message)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")