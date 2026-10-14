from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import Lock
from typing import Optional

from dotenv import load_dotenv
from huggingface_hub import snapshot_download
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)


class BGEEmbeddingManager:
    """本地 BGE embedding 的单例管理器。"""

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    MODEL_DIR = Path("models/bge-small-zh-v1.5")
    BATCH_SIZE = 32
    NORMALIZE = True
    QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

    # 设备优先级：cuda > mps > cpu
    PREFERRED_DEVICES = ("cuda", "mps", "cpu")

    _instance: Optional[HuggingFaceEmbeddings] = None
    _lock = Lock()

    @classmethod
    def _detect_device(cls) -> str:
        """检测可用的加速设备，按优先级返回。"""
        import torch

        if torch.cuda.is_available():
            device = "cuda"
            name = torch.cuda.get_device_name(0)
            print(f"[BGE] 使用 CUDA 加速：{name}")
            return device

        # Apple Silicon 的 MPS 后端
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            print("[BGE] 使用 Apple MPS 加速")
            return "mps"

        if mps is None or not mps.is_built():
            reason = "当前 PyTorch 未编译 MPS 支持"
        else:
            try:
                torch.empty(0, device="mps")
            except RuntimeError as exc:
                reason = str(exc)
            else:
                reason = "PyTorch 报告 MPS 不可用，请检查系统版本和 Metal GPU 支持"
        print(f"[BGE] 使用 CPU；MPS 不可用原因：{reason}")
        return "cpu"

    @classmethod
    def _ensure_model_available(cls) -> Path:
        load_dotenv()
        model_dir = Path(os.getenv("RAG_EMBEDDING_MODEL_PATH", str(cls.MODEL_DIR)))
        model_dir = model_dir.expanduser().resolve()
        if cls._model_files_available(model_dir):
            return model_dir

        logger.info("本地 BGE 模型缺失或不完整，开始下载 %s 到 %s", cls.MODEL_NAME, model_dir)
        try:
            snapshot_download(
                repo_id=cls.MODEL_NAME,
                local_dir=str(model_dir),
                allow_patterns=["*.json", "*.txt", "*.safetensors", "pytorch_model.bin"],
            )
        except Exception as exc:
            raise FileNotFoundError(
                f"自动下载 {cls.MODEL_NAME} 失败，请检查 Hugging Face 网络连接"
                f"和目录写入权限后重试。模型目录：{model_dir}。"
            ) from exc

        if not cls._model_files_available(model_dir):
            raise FileNotFoundError(f"模型下载不完整：{model_dir}，请重试。")
        logger.info("BGE 模型下载完成：%s", model_dir)
        return model_dir

    @staticmethod
    def _model_files_available(model_dir: Path) -> bool:
        required = ("config.json", "tokenizer_config.json", "vocab.txt")
        weights = ("model.safetensors", "pytorch_model.bin")

        def has_file(name: str) -> bool:
            path = model_dir / name
            return path.is_file() and path.stat().st_size > 0

        return all(has_file(name) for name in required) and any(
            has_file(name) for name in weights
        )

    @classmethod
    def _build_embedding(cls) -> HuggingFaceEmbeddings:
        model_dir = cls._ensure_model_available()
        device = cls._detect_device()
        encode_kwargs = {
            "batch_size": cls.BATCH_SIZE,
            "normalize_embeddings": cls.NORMALIZE,
        }
        return HuggingFaceEmbeddings(
            model_name=str(model_dir),
            model_kwargs={"device": device, "local_files_only": True},
            encode_kwargs=encode_kwargs,
            query_encode_kwargs={**encode_kwargs, "prompt": cls.QUERY_INSTRUCTION},
        )

    @classmethod
    def get_embeddings(cls) -> HuggingFaceEmbeddings:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._build_embedding()
            return cls._instance
