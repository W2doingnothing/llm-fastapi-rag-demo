# app/settings.py
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        # LLM provider
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock").strip()

        # OpenAI / OpenAI-compatible configs
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.openai_timeout = int(os.getenv("OPENAI_TIMEOUT", "20"))

        # ✅ 新增：兼容第三方（如 AIHubMix）
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None


settings = Settings()