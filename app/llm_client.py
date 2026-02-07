

from app.settings import settings


def chat(message: str) -> str:

    provider = settings.llm_provider.lower()

    if provider == "mock":
        # 目前的假模型：回声
        return f"你说的是：{message}"

    # 以后扩展：provider == "openai"
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
