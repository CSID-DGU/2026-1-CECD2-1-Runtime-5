# Runtime Security Service

컨테이너 런타임 보안 이벤트 탐지 및 자동 대응 서비스.  
Falco가 위협을 탐지하면 LLM이 action을 추천하고, 보안 담당자가 승인한 결과는 Playbook으로 축적되어 이후 동일 공격에 LLM 없이 즉시 분석·추천합니다.

---

## 폴더 구조

```
runtime-service/
├── backend/           # FastAPI API 서버 (SQLite, OpenAI, Chroma 연동)
├── bridge/            # Falcosidekick webhook 수신 → backend 전달
├── frontend/          # React 대시보드
└── docker-compose.yml
```

---

## 전체 흐름

```
컨테이너 내부 행위 발생
  ↓
Falco 탐지 → Falcosidekick → bridge /webhook
  ↓
backend /llm/analyze
  ├─ Playbook 정확 매칭 → action/insight 재사용 (LLM 호출 생략)
  └─ 매칭 없음 → Chroma VectorDB 유사 Playbook 검색 → LLM 추천
  ↓
backend /events/ingest 저장
  ↓
Dashboard에서 이벤트 확인
  ↓
보안 담당자 승인 또는 롤백
  ↓
Playbook + VectorDB 반영 → 이후 동일 공격에 재사용
```

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| 런타임 탐지 | Falco, Falcosidekick |
| 이벤트 수신 | bridge (FastAPI) |
| API 서버 | backend (FastAPI) |
| DB | SQLite |
| VectorDB | ChromaDB |
| LLM | OpenAI gpt-4o-mini |
| Embedding | OpenAI text-embedding-3-small |
| 프론트엔드 | React (Vite) |

---

## 사전 준비

`backend/.env` 파일 생성

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=./runtime.db
CHROMA_COLLECTION=runtime_playbooks
```

---

## 실행 방법

### 1. 백엔드 파이프라인

```bash
docker compose up --build
```

| 서비스 | 주소 |
|---|---|
| Backend API | http://localhost:8081 |
| Bridge | http://localhost:5001 |
| Chroma | http://localhost:8000 |
| Falcosidekick | http://localhost:2801 |

### 2. 프론트엔드

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### 3. 테스트 이벤트 생성

```bash
docker compose --profile datagen up event-generator
```

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| 실시간 대시보드 | 탐지 이벤트 목록, 위험도별 통계, 시간대별 타임라인 |
| 로그 모니터링 | rule_name + AI insight + 처리 상태 확인 |
| 승인/롤백 | 담당자가 LLM 추천 action을 승인하거나 직접 수정 후 Playbook 저장 |
| Playbook 학습 | 승인된 결과가 누적될수록 LLM 없이 처리되는 비율 증가 |
| VectorDB 검색 | 새 공격이 기존 Playbook과 유사하면 LLM 컨텍스트로 활용 |
| 보안 어시스턴트 | 자연어로 이벤트 조회, 분석 요청, 승인/롤백 처리 가능 |
| CSV 리포트 | 전체 이벤트 내역 다운로드 |

---

## 초기 Playbook (seed)

서비스 시작 시 아래 5개 Playbook이 자동으로 등록됩니다.

| Rule | Action |
|---|---|
| Drop and execute new binary in container | stop |
| Run shell untrusted | stop |
| Netcat Remote Code Execution in Container | stop |
| PTRACE attached to process | stop |
| Read sensitive file untrusted | alert |

---

## 보안 어시스턴트 사용 예시

대시보드 챗봇에서 자연어로 이벤트를 처리할 수 있습니다.

| 입력 예시 | 동작 |
|---|---|
| "방금 탐지된 이벤트 설명해줘" | 최근 이벤트 분석 결과 반환 |
| "EV-XXXXXX 승인해줘" | 해당 이벤트 CONFIRMED 처리 + Playbook 저장 |
| "EV-XXXXXX rollback하고 stop으로 바꿔줘" | ROLLED_BACK + manual_action: stop 저장 |
| "최근 rollback한 이벤트 알려줘" | ROLLED_BACK 상태 이벤트 목록 반환 |

---

## 주요 API

| Method | Path | 설명 |
|---|---|---|
| GET | /api/v1/events | 이벤트 목록 |
| PATCH | /api/v1/events/{id}/decision | 승인/롤백 |
| POST | /api/v1/llm/analyze | Playbook/VectorDB/LLM 분석 |
| GET | /api/v1/playbooks | Playbook 목록 |
| GET | /api/v1/dashboard/summary | 대시보드 요약 |
| POST | /api/v1/copilot/chat | 보안 어시스턴트 챗봇 |
| GET | /api/v1/reports/export | CSV 리포트 다운로드 |

---

## 참고

- `backend/.env`는 Git에 올리지 않습니다.
- 현재 추천된 action(stop/alert/ignore)은 Dashboard에 표시되며, 실제 컨테이너 중지/차단은 실행되지 않습니다.