"""PDF 학습 튜터 - FastAPI 서버.

엔드포인트
- POST /api/upload          PDF 업로드 → 추출·인덱싱
- GET  /api/docs            업로드한 문서 목록
- GET  /api/status          API 키 설정 여부 확인
- POST /api/chat            질문답변(스트리밍)
- POST /api/summary         구간/주제 요약
- POST /api/quiz            퀴즈 출제
- POST /api/flashcards      플래시카드 생성
프론트엔드(/) 는 frontend/index.html 을 서빙한다.
"""

from __future__ import annotations

import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import claude_client
from .pdf_processor import Chunk, build_chunks, extract_pages
from .store import Store

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# 모델에 한 번에 보내는 본문 글자 수 상한 (비용·컨텍스트 보호)
MAX_CONTEXT_CHARS = 30000

app = FastAPI(title="PDF 학습 튜터")
store = Store()


def _cap_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """본문이 너무 길면 글자 수 상한까지만 사용."""
    out: list[Chunk] = []
    total = 0
    for c in chunks:
        if total + len(c.text) > MAX_CONTEXT_CHARS and out:
            break
        out.append(c)
        total += len(c.text)
    return out


def _select_chunks(doc_id: str, topic: str, page_start: int | None, page_end: int | None) -> list[Chunk]:
    """주제(topic)가 있으면 검색, 페이지 범위가 있으면 그 구간, 둘 다 없으면 앞부분."""
    if topic and topic.strip():
        chunks = store.search(doc_id, topic, top_k=12)
        if chunks:
            return _cap_chunks(chunks)
    if page_start and page_end:
        return _cap_chunks(store.chunks_in_pages(doc_id, page_start, page_end))
    doc = store.get(doc_id)
    if not doc:
        return []
    return _cap_chunks(doc.chunks)


# ---------- 모델 ----------
class ChatReq(BaseModel):
    doc_id: str
    question: str


class SummaryReq(BaseModel):
    doc_id: str
    topic: str = ""
    page_start: int | None = None
    page_end: int | None = None


class GenReq(BaseModel):
    doc_id: str
    topic: str = ""
    page_start: int | None = None
    page_end: int | None = None
    count: int = 5


# ---------- 엔드포인트 ----------
@app.get("/api/status")
def status():
    return {"api_key_set": claude_client.has_api_key(), "model": claude_client.MODEL}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF 파일만 업로드할 수 있습니다.")

    # 임시 파일로 저장 후 추출
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        pages = extract_pages(tmp_path)
    finally:
        os.unlink(tmp_path)

    chunks = build_chunks(pages)
    if not chunks:
        raise HTTPException(
            400,
            "PDF에서 텍스트를 추출하지 못했습니다. (스캔 이미지 PDF일 수 있어요. "
            "OCR로 텍스트화된 PDF가 필요합니다.)",
        )
    doc = store.create(file.filename, len(pages), chunks)
    return {"id": doc.id, "filename": doc.filename, "pages": doc.pages, "num_chunks": doc.num_chunks}


@app.get("/api/docs")
def docs():
    return store.list_docs()


@app.post("/api/chat")
def chat(req: ChatReq):
    _require_key()
    chunks = store.search(req.doc_id, req.question, top_k=6)
    if not chunks:
        raise HTTPException(404, "문서를 찾을 수 없거나 관련 내용이 없습니다.")

    def gen():
        for piece in claude_client.chat_stream(req.question, chunks):
            yield piece

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


@app.post("/api/summary")
def summary(req: SummaryReq):
    _require_key()
    chunks = _select_chunks(req.doc_id, req.topic, req.page_start, req.page_end)
    if not chunks:
        raise HTTPException(404, "요약할 내용을 찾지 못했습니다.")
    return {"summary": claude_client.summarize(chunks, hint=req.topic)}


@app.post("/api/quiz")
def quiz(req: GenReq):
    _require_key()
    chunks = _select_chunks(req.doc_id, req.topic, req.page_start, req.page_end)
    if not chunks:
        raise HTTPException(404, "문제를 낼 내용을 찾지 못했습니다.")
    return claude_client.make_quiz(chunks, count=max(1, min(req.count, 10)))


@app.post("/api/flashcards")
def flashcards(req: GenReq):
    _require_key()
    chunks = _select_chunks(req.doc_id, req.topic, req.page_start, req.page_end)
    if not chunks:
        raise HTTPException(404, "카드를 만들 내용을 찾지 못했습니다.")
    return claude_client.make_flashcards(chunks, count=max(1, min(req.count, 20)))


def _require_key():
    if not claude_client.has_api_key():
        raise HTTPException(
            400,
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일에 키를 넣고 서버를 다시 시작하세요.",
        )


# ---------- 프론트엔드 ----------
@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
