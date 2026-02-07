# app/settings.py


import os
from dotenv import load_dotenv

# 加载根目录下的 .env（在启动时读取）
load_dotenv()


class Settings:
    def __init__(self):
        # mock / openai（后面可以扩展）
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock").strip()

        # 真实 key（暂时可空）
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()


settings = Settings()
