# Runtime Security System Backend

본 백엔드 서비스는 컨테이너 런타임 보안 이벤트를 수신하여 AI 기반으로 분석하고 자동 대응하는 핵심 파이프라인을 제공합니다. `research` 영역에서 검증된 Semantic Cache 및 프롬프트 최적화 전략이 통합되어 구현되어 있습니다.

---

## 1. 주요 기능

```
공격 발생
  ↓
Falco 탐지 → falcosidekick → bridge /webhook
  ↓
backend /llm/analyze
  1. Playbook exact match → LLM 없이 즉시 처리
  2. Semantic Cache hit   → LLM 없이 즉시 처리
  3. VectorDB top-k 검색 + LLM 분석 → 캐시 저장
  ↓
action이 stop이면 즉시 docker stop 실행
  ↓
events/ingest 저장
  ↓
Dashboard 표시
  ↓
담당자 승인/롤백 → Playbook + VectorDB 반영
```

---

## 3. 기술 스택

| 영역 | 기술 |
|---|---|
| 런타임 탐지 | Falco, Falcosidekick |
| 이벤트 수신 | bridge (FastAPI) |
| API 서버 | backend (FastAPI) |
| DB | PostgreSQL, pgvector |
| 캐시 | Redis |
| LLM | OpenAI gpt-4o-mini |
| Embedding | OpenAI text-embedding-3-small |
| 프론트엔드 | React (Vite) |
| 배포 | Docker Compose |

---

## 4. DB 스키마

### events

| 필드 | 타입 | 설명 |
|---|---|---|
| id | TEXT PK | 이벤트 ID (EV-XXXXXX) |
| rule_name | TEXT | Falco rule 이름 |
| priority | TEXT | 이벤트 심각도 |
| container | TEXT | 컨테이너 이름 또는 ID |
| cmdline | TEXT | 실행 명령어 |
| output | TEXT | Falco 원본 메시지 |
| llm_action | TEXT | LLM 추천 action |
| manual_action | TEXT | 관리자 직접 지정 action |
| llm_insight | TEXT | AI 분석 설명 |
| from_playbook | BOOLEAN | Playbook 매칭 여부 (default FALSE) |
| status | TEXT | PENDING / AUTO_ACTIONED / CONFIRMED / ROLLED_BACK |
| timestamp | TEXT | 저장 시각 (ISO 문자열) |

### playbooks

| 필드 | 타입 | 설명 |
|---|---|---|
| rule_name | TEXT PK | Falco rule 이름 |
| action | TEXT | stop / alert / ignore |
| insight | TEXT | 위협 설명 |
| approved_by | TEXT | system / security_engineer |
| created_at | TEXT | 저장 시각 (ISO 문자열) |
| source_text | TEXT | embedding 원본 텍스트 |
| embedding | VECTOR(1536) | OpenAI embedding 벡터 (HNSW cosine 인덱스) |
| embedding_model | TEXT | 사용한 embedding 모델명 |
| updated_at | TEXT | 갱신 시각 (ISO 문자열) |

### chat_messages

| 필드 | 타입 | 설명 |
|---|---|---|
| id | SERIAL PK | 자동 증가 ID |
| sender | TEXT | user / bot |
| message | TEXT | 메시지 내용 |
| created_at | TEXT | 저장 시각 (ISO 문자열) |

---

## 5. 사전 준비

`backend/.env` 파일 생성

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://runtime:runtime1234@postgres:5432/runtime_security
REDIS_URL=redis://redis:6379
CACHE_TTL=3600
```

---

## 6. 실행 방법

기본 (DRY_RUN=true, 실제 컨테이너 조작 없음)

```bash
docker compose up --build
```

실제 대응 실행

```bash
REMEDIATION_DRY_RUN=false docker compose up -d --build
```

프론트엔드

```bash
cd frontend && npm install && npm run dev
```

---

## 7. 주요 기능

- 실시간 대시보드 (위험도별 통계, 타임라인)
- 로그 모니터링 (rule_name + AI insight + 처리 상태)
- 자동 대응 (action=stop이면 즉시 docker stop)
- Playbook 학습 (승인 누적 → LLM 호출 감소)
- Semantic Cache (Redis, rule+priority MD5 해시, TTL 3600s)
- VectorDB 유사 Playbook 검색 (pgvector cosine similarity)
- V2 압축 프롬프트 적용 (토큰 절감)
- 보안 어시스턴트 챗봇 (Function Calling)
- rollback 분기 (llm_action 기준 restart/stop/ignore)
- CSV 리포트 다운로드

---

## 8. 초기 Playbook seed 5개

| Rule | Action |
|---|---|
| Drop and execute new binary in container | stop |
| Run shell untrusted | stop |
| Netcat Remote Code Execution in Container | stop |
| PTRACE attached to process | stop |
| Read sensitive file untrusted | alert |

---

## 9. 보안 어시스턴트 사용 예시

```
"방금 탐지된 이벤트 설명해줘"
"EV-XXXXXX 승인해줘"
"EV-XXXXXX rollback하고 stop으로 바꿔줘"
```

---

## 10. rollback 분기

| llm_action | 원상 복구 동작 |
|---|---|
| stop | restart (컨테이너 재시작) |
| alert | 모달에서 stop / ignore 선택 |
| ignore | stop (컨테이너 중지) |

---

## 11. 실제 대응 테스트

```bash
REMEDIATION_DRY_RUN=false docker compose up -d --build bridge
docker run -d --name demo-target nginx
docker exec demo-target sh -c "cat /etc/shadow"
docker ps -a | grep demo-target   # → Exited 확인
docker rm -f demo-target
```

---

## 12. 주요 API

| Method | Path |
|---|---|
| GET | /api/v1/events |
| PATCH | /api/v1/events/{id}/decision |
| POST | /api/v1/llm/analyze |
| GET | /api/v1/playbooks |
| GET | /api/v1/dashboard/summary |
| POST | /api/v1/copilot/chat |
| GET | /api/v1/reports/export |

---

## 13. 참고

- `backend/.env`는 Git에 올리지 않습니다.
- `REMEDIATION_DRY_RUN=true`가 기본값입니다.
- allowlist: `falco`, `falcosidekick`, `backend`, `bridge`는 stop/restart 금지.
