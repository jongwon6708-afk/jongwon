# 📖 PDF 학습 튜터 (PDF Tutor)

수천 페이지짜리 책(PDF)을 **다 읽지 않고도** 공부할 수 있게 도와주는 웹 앱입니다.
AI(Claude)가 책을 대신 읽고 **질문답변·요약·퀴즈·플래시카드**로 가르쳐 줍니다.

## 어떻게 동작하나요?

수천 페이지는 한 번에 AI에 넣을 수 없습니다. 그래서:

1. PDF를 업로드하면 페이지별로 텍스트를 추출하고 작은 **조각(청크)** 으로 나눕니다.
2. 질문/주제가 들어오면 **BM25 검색**(한국어·영어 모두 지원, 추가 API 불필요)으로
   가장 관련 있는 조각만 골라냅니다. (이 방식을 RAG라고 합니다)
3. 그 조각만 Claude에 보내 답변·요약·퀴즈·카드를 생성합니다.
   → 책이 아무리 두꺼워도 매 요청은 작고 빠르고 저렴합니다.

## 기능

| 탭 | 설명 |
|----|------|
| 💬 질문답변 | 책 내용을 자유롭게 질문 → 관련 부분을 찾아 근거(쪽 번호)와 함께 답변(실시간 스트리밍) |
| 📝 요약 | 주제 또는 페이지 범위를 핵심 위주로 요약 + "꼭 기억할 3가지" |
| ❓ 퀴즈 | 4지선다 문제 출제 → 클릭하면 정답·해설 표시 |
| 🗂️ 플래시카드 | 핵심 개념 암기 카드 생성(클릭하면 뒷면) |

## 빠른 시작

### 1. Claude API 키 발급 (무료 가입 후 결제 수단 등록 필요)

1. <https://console.anthropic.com> 접속 후 가입/로그인
2. **Settings → API Keys → Create Key** 로 키 생성 (`sk-ant-...`)
3. 사용량만큼 과금됩니다. 본 앱은 검색으로 필요한 부분만 보내므로 비용이 작습니다.
   더 아끼려면 아래 `PDF_TUTOR_MODEL`을 `claude-sonnet-4-6` 또는 `claude-haiku-4-5`로 바꾸세요.

### 2. 설치 및 실행

```bash
cd pdf_tutor

# (권장) 가상환경
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# API 키 설정
cp .env.example .env
#  .env 파일을 열어 ANTHROPIC_API_KEY 값을 본인 키로 교체

# 환경변수 로드 후 서버 실행
export $(grep -v '^#' .env | xargs)      # Windows PowerShell은 아래 '참고' 방식 사용
uvicorn backend.main:app --reload --port 8000
```

브라우저에서 <http://localhost:8000> 접속 → PDF 업로드 → 학습 시작!

> **참고(.env 로드):** `export $(...)`가 안 되는 환경에서는 `ANTHROPIC_API_KEY`를
> 직접 환경변수로 설정한 뒤 `uvicorn`을 실행하면 됩니다.
> 예) macOS/Linux: `ANTHROPIC_API_KEY=sk-ant-... uvicorn backend.main:app --port 8000`

## 구조

```
pdf_tutor/
├── requirements.txt
├── .env.example
├── backend/
│   ├── main.py            # FastAPI 서버 + 엔드포인트
│   ├── pdf_processor.py   # PDF 텍스트 추출 + 청크 분할
│   ├── retrieval.py       # 순수 파이썬 BM25 검색(한/영 토크나이저)
│   ├── store.py           # 청크 저장 + 인덱스 캐시
│   └── claude_client.py   # Claude 호출(채팅/요약/퀴즈/플래시카드)
├── frontend/
│   └── index.html         # 단일 페이지 UI(빌드 불필요)
└── data/                  # 업로드 문서·인덱스 저장(git 제외)
```

## 한계 & 팁

- **스캔 이미지 PDF**(글자가 이미지로만 된 PDF)는 텍스트 추출이 안 됩니다.
  OCR로 텍스트화된 PDF를 사용하세요.
- 표/수식이 많은 PDF는 추출 품질이 떨어질 수 있습니다.
- 요약/퀴즈에서 페이지 범위가 매우 넓으면 비용 보호를 위해 일부만 사용합니다.
  특정 부분을 깊게 보려면 **주제**나 **좁은 페이지 범위**를 지정하세요.

## 사용 모델

기본값은 **Claude Opus 4.8** (`claude-opus-4-8`). `.env`의 `PDF_TUTOR_MODEL`로 변경 가능합니다.
