from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredWordDocumentLoader,
)


class DocumentSourceLoader:
    """按文件类型加载原始 Document，不做切分。"""

    LOADER_MAP = {
        ".md": TextLoader,
        ".markdown": TextLoader,
        ".txt": TextLoader,
        ".pdf": PyPDFLoader,
        ".docx": UnstructuredWordDocumentLoader,
        ".html": UnstructuredHTMLLoader,
        ".htm": UnstructuredHTMLLoader,
    }

    @classmethod
    def load(cls, source_dir: str | Path) -> list:
        source_dir = Path(source_dir)
        docs = []
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            loader_cls = cls.LOADER_MAP.get(path.suffix.lower())
            if loader_cls is None:
                continue
            docs.extend(loader_cls(str(path)).load())
        return docs

    @classmethod
    def load_file(cls, file_path: str | Path) -> list:
        path = Path(file_path)
        loader_cls = cls.LOADER_MAP.get(path.suffix.lower())
        if loader_cls is None:
            return []
        return loader_cls(str(path)).load()