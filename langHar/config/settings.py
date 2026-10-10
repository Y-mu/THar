from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Settings:
    llm_api_key: str
    typesafe_api_key: str
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    jev_model: str = "jev-latest"
    intent_confidence_threshold: float = 0.55

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        llm_api_key = (
            os.getenv("LLM_API_KEY", "").strip()
            or os.getenv("DEEPSEEK_API_KEY", "").strip()
        )
        typesafe_api_key = (
            os.getenv("TYPESAFE_API_KEY", "").strip()
            or os.getenv("JEV_API_KEY", "").strip()
        )
        missing = []
        if not llm_api_key:
            missing.append("LLM_API_KEY（或 DEEPSEEK_API_KEY）")
        if not typesafe_api_key:
            missing.append("TYPESAFE_API_KEY（或 JEV_API_KEY）")
        if missing:
            raise ConfigurationError(
                f"缺少有效配置：{', '.join(missing)}。请参考 .env.example。"
            )

        try:
            threshold = float(os.getenv("INTENT_CONFIDENCE_THRESHOLD", "0.55"))
        except ValueError as exc:
            raise ConfigurationError(
                "INTENT_CONFIDENCE_THRESHOLD 必须是 0 到 1 之间的数字。"
            ) from exc
        if not 0 <= threshold <= 1:
            raise ConfigurationError(
                "INTENT_CONFIDENCE_THRESHOLD 必须是 0 到 1 之间的数字。"
            )

        return cls(
            llm_api_key=llm_api_key,
            llm_model=(
                os.getenv("LLM_MODEL", "").strip()
                or os.getenv("DEEPSEEK_MODEL", "").strip()
                or "deepseek-chat"
            ),
            llm_base_url=(
                os.getenv("LLM_BASE_URL", "").strip()
                or os.getenv("DEEPSEEK_BASE_URL", "").strip()
                or "https://api.deepseek.com"
            ),
            typesafe_api_key=typesafe_api_key,
            jev_model=os.getenv("JEV_MODEL", "").strip() or "jev-latest",
            intent_confidence_threshold=threshold,
        )
