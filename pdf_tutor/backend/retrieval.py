"""순수 파이썬 BM25 검색.

추가 API 키나 무거운 ML 라이브러리 없이, 수천 페이지 분량의 청크 중에서
질문과 관련된 부분만 빠르게 찾기 위한 가벼운 검색기입니다.

한국어/영어를 함께 다루기 위해 토크나이저는
- 영문/숫자: 단어 단위
- 한글·한자·가나(CJK): 글자 2-gram(바이그램)
으로 쪼갭니다. (형태소 분석기 없이도 한국어 검색이 그럭저럭 동작하게 함)
"""

from __future__ import annotations

import math
import re
from collections import Counter

# CJK(한글/한자/가나) 연속 구간
_CJK_RUN = re.compile(r"[가-힣一-鿿぀-ヿ]+")
# 영문/숫자 단어
_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens: list[str] = _WORD.findall(text)
    for run in _CJK_RUN.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


class BM25:
    """BM25 Okapi 랭킹. 청크(문서) 토큰 리스트로 인덱스를 만든다."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = corpus_tokens
        self.n = len(corpus_tokens)
        self.doc_len = [len(d) for d in corpus_tokens]
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0
        self.doc_freqs: list[Counter] = [Counter(d) for d in corpus_tokens]

        # document frequency (단어가 등장한 문서 수)
        df: Counter = Counter()
        for freqs in self.doc_freqs:
            df.update(freqs.keys())

        # idf 미리 계산
        self.idf: dict[str, float] = {}
        for term, freq in df.items():
            self.idf[term] = math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 6) -> list[tuple[int, float]]:
        """질의에 대해 (청크 인덱스, 점수) 상위 top_k 반환."""
        if self.n == 0:
            return []
        q_tokens = tokenize(query)
        scores = [0.0] * self.n
        for term in q_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, freqs in enumerate(self.doc_freqs):
                f = freqs.get(term)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                scores[i] += idf * (f * (self.k1 + 1)) / denom

        ranked = sorted(range(self.n), key=lambda i: scores[i], reverse=True)
        out = [(i, scores[i]) for i in ranked[:top_k] if scores[i] > 0]
        return out
