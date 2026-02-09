# app/settings.py
"""
集中管理配置：
- 读取 .env（本地）
- 提供默认值
- 支持 OpenAI-compatible 网关（如 AIHubMix）通过 base_url 转发
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        # LLM provider: mock / openai
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock").strip()

        # OpenAI / OpenAI-compatible configs
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.openai_timeout = int(os.getenv("OPENAI_TIMEOUT", "20"))

        # 兼容第三方网关：不填则用默认 OpenAI
        base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        self.openai_base_url = base_url or None

        # 自己控制重试次数（避免 SDK 重试 + 手写重试叠加）
        self.openai_max_attempts = int(os.getenv("OPENAI_MAX_ATTEMPTS", "3"))


settings = Settings()
