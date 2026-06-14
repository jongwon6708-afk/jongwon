"""Claude(Anthropic) API 호출 모음.

검색으로 찾은 청크들을 컨텍스트로 넣어
- 질문답변(채팅, 스트리밍)
- 구간 요약
- 퀴즈 출제
- 플래시카드 생성
을 수행한다.

모델 기본값은 claude-opus-4-8. 환경변수 PDF_TUTOR_MODEL 로 바꿀 수 있다.
"""

from __future__ import annotations

import json
import os
from typing import Iterator

import anthropic

from .pdf_processor import Chunk

MODEL = os.environ.get("PDF_TUTOR_MODEL", "claude-opus-4-8")

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # ANTHROPIC_API_KEY 환경변수에서 자동으로 키를 읽는다.
        _client = anthropic.Anthropic()
    return _client


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _context_from_chunks(chunks: list[Chunk]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[{c.page}쪽]\n{c.text}")
    return "\n\n---\n\n".join(parts)


SYSTEM_TUTOR = (
    "당신은 사용자가 업로드한 책(PDF)을 바탕으로 학습을 돕는 친절한 한국어 튜터입니다. "
    "반드시 제공된 '본문 발췌'에 근거해서만 답하세요. 발췌에 없는 내용은 추측하지 말고 "
    "'본문에서 해당 내용을 찾지 못했습니다'라고 말하세요. "
    "답변에는 근거가 된 쪽 번호를 (예: 123쪽)처럼 표시하세요. "
    "초보자도 이해할 수 있도록 쉽고 단계적으로 설명하세요."
)


# ---------- 채팅(스트리밍) ----------
def chat_stream(question: str, chunks: list[Chunk]) -> Iterator[str]:
    context = _context_from_chunks(chunks)
    user = (
        f"다음은 책에서 찾은 관련 본문 발췌입니다.\n\n"
        f"<본문 발췌>\n{context}\n</본문 발췌>\n\n"
        f"질문: {question}\n\n"
        f"위 발췌에 근거해 답해 주세요."
    )
    client = get_client()
    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_TUTOR,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# ---------- 구간 요약 ----------
def summarize(chunks: list[Chunk], hint: str = "") -> str:
    context = _context_from_chunks(chunks)
    extra = f"\n특히 다음에 집중해 주세요: {hint}\n" if hint.strip() else ""
    user = (
        f"다음 본문을 학습용으로 요약해 주세요.{extra}\n"
        f"- 핵심 개념을 불릿으로 정리\n"
        f"- 중요한 용어는 굵게\n"
        f"- 마지막에 '꼭 기억할 3가지'를 추가\n\n"
        f"<본문>\n{context}\n</본문>"
    )
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_TUTOR,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


# ---------- 퀴즈 ----------
QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "answer_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                    "page": {"type": "integer"},
                },
                "required": ["question", "choices", "answer_index", "explanation", "page"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def make_quiz(chunks: list[Chunk], count: int = 5) -> dict:
    context = _context_from_chunks(chunks)
    user = (
        f"다음 본문을 바탕으로 4지선다 객관식 문제 {count}개를 만들어 주세요.\n"
        f"- 각 문제는 보기 4개(choices), 정답 인덱스(answer_index, 0부터 시작), "
        f"해설(explanation), 근거 쪽 번호(page)를 포함합니다.\n"
        f"- 본문 내용에 근거한 문제만 출제하세요.\n\n"
        f"<본문>\n{context}\n</본문>"
    )
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM_TUTOR,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": QUIZ_SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------- 플래시카드 ----------
FLASHCARD_SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "front": {"type": "string"},
                    "back": {"type": "string"},
                    "page": {"type": "integer"},
                },
                "required": ["front", "back", "page"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


def make_flashcards(chunks: list[Chunk], count: int = 8) -> dict:
    context = _context_from_chunks(chunks)
    user = (
        f"다음 본문에서 암기·복습에 좋은 플래시카드 {count}장을 만들어 주세요.\n"
        f"- front: 질문/용어, back: 답/설명, page: 근거 쪽 번호\n"
        f"- 핵심 개념 위주로, 간결하게.\n\n"
        f"<본문>\n{context}\n</본문>"
    )
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM_TUTOR,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": FLASHCARD_SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)
