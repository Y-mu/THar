from __future__ import annotations

from langchain_text_splitters import (
    HTMLHeaderTextSplitter,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


class DocumentChunker:
    """按来源类型选择 splitter，输出结构化块。"""

    MD_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    HTML_HEADERS = [("h1", "h1"), ("h2", "h2"), ("h3", "h3")]
    MAX_CHUNK_SIZE = 800
    CHUNK_OVERLAP = 120

    @classmethod
    def split(cls, docs: list) -> list:
        fallback = RecursiveCharacterTextSplitter(
            chunk_size=cls.MAX_CHUNK_SIZE,
            chunk_overlap=cls.CHUNK_OVERLAP,
        )
        chunks = []
        for doc in docs:
            splitter = cls._pick_splitter(doc)
            pieces = splitter.split_text(doc.page_content)
            for piece in pieces:
                piece.metadata = {**doc.metadata, **piece.metadata}
                if len(piece.page_content) > cls.MAX_CHUNK_SIZE:
                    chunks.extend(fallback.split_documents([piece]))
                else:
                    chunks.append(piece)
        return chunks

    @classmethod
    def _pick_splitter(cls, doc):
        source = str(doc.metadata.get("source", "")).lower()
        if source.endswith((".md", ".markdown")):
            return MarkdownHeaderTextSplitter(
                headers_to_split_on=cls.MD_HEADERS, strip_headers=False
            )
        if source.endswith((".html", ".htm")):
            return HTMLHeaderTextSplitter(headers_to_split_on=cls.HTML_HEADERS)
        return RecursiveCharacterTextSplitter(
            chunk_size=cls.MAX_CHUNK_SIZE, chunk_overlap=cls.CHUNK_OVERLAP
        )