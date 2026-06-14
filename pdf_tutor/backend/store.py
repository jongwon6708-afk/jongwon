"""업로드한 PDF의 청크·메타데이터 저장 및 검색 인덱스 관리.

- 디스크: data/<doc_id>/meta.json, chunks.json  (컨테이너 재시작 후에도 유지)
- 메모리: BM25 인덱스는 처음 접근할 때 만들어 캐시한다(매 요청마다 재생성 방지).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass

from .pdf_processor import Chunk, chunks_to_dicts, dicts_to_chunks
from .retrieval import BM25, tokenize

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@dataclass
class Document:
    id: str
    filename: str
    pages: int
    num_chunks: int
    chunks: list[Chunk]


def _doc_dir(doc_id: str) -> str:
    return os.path.join(DATA_DIR, doc_id)


class Store:
    def __init__(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        self._docs: dict[str, Document] = {}
        self._indexes: dict[str, BM25] = {}

    # ---- 생성/저장 ----
    def create(self, filename: str, pages: int, chunks: list[Chunk]) -> Document:
        doc_id = uuid.uuid4().hex[:12]
        doc = Document(
            id=doc_id,
            filename=filename,
            pages=pages,
            num_chunks=len(chunks),
            chunks=chunks,
        )
        os.makedirs(_doc_dir(doc_id), exist_ok=True)
        with open(os.path.join(_doc_dir(doc_id), "meta.json"), "w", encoding="utf-8") as f:
            json.dump(
                {"id": doc_id, "filename": filename, "pages": pages, "num_chunks": len(chunks)},
                f,
                ensure_ascii=False,
            )
        with open(os.path.join(_doc_dir(doc_id), "chunks.json"), "w", encoding="utf-8") as f:
            json.dump(chunks_to_dicts(chunks), f, ensure_ascii=False)
        self._docs[doc_id] = doc
        return doc

    # ---- 조회 ----
    def list_docs(self) -> list[dict]:
        self._load_all_meta()
        return [
            {"id": d.id, "filename": d.filename, "pages": d.pages, "num_chunks": d.num_chunks}
            for d in sorted(self._docs.values(), key=lambda x: x.filename)
        ]

    def get(self, doc_id: str) -> Document | None:
        if doc_id in self._docs and self._docs[doc_id].chunks:
            return self._docs[doc_id]
        return self._load_doc(doc_id)

    def index(self, doc_id: str) -> BM25 | None:
        if doc_id in self._indexes:
            return self._indexes[doc_id]
        doc = self.get(doc_id)
        if not doc:
            return None
        bm25 = BM25([tokenize(c.text) for c in doc.chunks])
        self._indexes[doc_id] = bm25
        return bm25

    # ---- 검색 ----
    def search(self, doc_id: str, query: str, top_k: int = 6) -> list[Chunk]:
        bm25 = self.index(doc_id)
        doc = self.get(doc_id)
        if not bm25 or not doc:
            return []
        hits = bm25.search(query, top_k=top_k)
        return [doc.chunks[i] for i, _score in hits]

    def chunks_in_pages(self, doc_id: str, start: int, end: int) -> list[Chunk]:
        doc = self.get(doc_id)
        if not doc:
            return []
        return [c for c in doc.chunks if start <= c.page <= end]

    # ---- 내부 로딩 ----
    def _load_all_meta(self) -> None:
        if not os.path.isdir(DATA_DIR):
            return
        for doc_id in os.listdir(DATA_DIR):
            meta_path = os.path.join(_doc_dir(doc_id), "meta.json")
            if doc_id in self._docs or not os.path.isfile(meta_path):
                continue
            with open(meta_path, encoding="utf-8") as f:
                m = json.load(f)
            self._docs[doc_id] = Document(
                id=m["id"],
                filename=m["filename"],
                pages=m["pages"],
                num_chunks=m["num_chunks"],
                chunks=[],
            )

    def _load_doc(self, doc_id: str) -> Document | None:
        chunks_path = os.path.join(_doc_dir(doc_id), "chunks.json")
        meta_path = os.path.join(_doc_dir(doc_id), "meta.json")
        if not os.path.isfile(chunks_path) or not os.path.isfile(meta_path):
            return None
        with open(meta_path, encoding="utf-8") as f:
            m = json.load(f)
        with open(chunks_path, encoding="utf-8") as f:
            chunks = dicts_to_chunks(json.load(f))
        doc = Document(
            id=m["id"],
            filename=m["filename"],
            pages=m["pages"],
            num_chunks=m["num_chunks"],
            chunks=chunks,
        )
        self._docs[doc_id] = doc
        return doc
