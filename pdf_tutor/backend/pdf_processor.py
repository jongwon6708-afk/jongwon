"""PDF 텍스트 추출 + 청크 분할.

수천 페이지를 한 번에 모델에 넣을 수 없으므로, 페이지별로 텍스트를 뽑아
적당한 크기(기본 1,200자, 200자 겹침)의 청크로 잘라 둔다.
각 청크는 어느 페이지에서 왔는지(page) 정보를 함께 보관해 출처 표기에 사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from pypdf import PdfReader

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


@dataclass
class Chunk:
    id: int
    page: int  # 1-based 페이지 번호
    text: str


def extract_pages(pdf_path: str) -> list[str]:
    """페이지별 텍스트 리스트(0-based 인덱스 = page-1)."""
    reader = PdfReader(pdf_path)
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        out.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return out


def build_chunks(pages: list[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    cid = 0
    for page_idx, page_text in enumerate(pages):
        for piece in _split_text(page_text, CHUNK_SIZE, CHUNK_OVERLAP):
            chunks.append(Chunk(id=cid, page=page_idx + 1, text=piece))
            cid += 1
    return chunks


def chunks_to_dicts(chunks: list[Chunk]) -> list[dict]:
    return [asdict(c) for c in chunks]


def dicts_to_chunks(dicts: list[dict]) -> list[Chunk]:
    return [Chunk(**d) for d in dicts]
