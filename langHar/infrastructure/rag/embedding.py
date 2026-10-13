from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv


class BGEEmbeddingManager:
    """本地 BGE embedding 的单例管理器。"""

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    LOCAL_MODEL_DIR = Path("models/bge-small-zh-v1.5")

    _instance: Optional[Any] = None

    @classmethod
    def get_embeddings(cls) -> Any:
        if cls._instance is None:
            load_dotenv()
            cls._ensure_model_available()
            cls._instance = cls._build_embeddings()
        return cls._instance

    @classmethod
    def _ensure_model_available(cls) -> None:
        if cls.LOCAL_MODEL_DIR.is_dir():
            return
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=cls.MODEL_NAME, local_dir=str(cls.LOCAL_MODEL_DIR))

    @classmethod
    def _build_embeddings(cls) -> Any:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name=str(cls.LOCAL_MODEL_DIR),
            model_kwargs={"device": cls._detect_device(), "local_files_only": True},
            encode_kwargs={"normalize_embeddings": True},
        )

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"