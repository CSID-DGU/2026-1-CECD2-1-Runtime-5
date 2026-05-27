# Runtime Security Service

컨테이너 런타임 보안 이벤트 탐지 및 자동 대응 서비스.
Falco가 위협을 탐지하면 LLM이 action을 추천하고,
보안 담당자가 승인한 결과는 Playbook으로 축적되어
이후 동일 공격에 LLM 없이 즉시 대응합니다.

## 폴더 구조

```text
runtime-service/
├── backend/             # FastAPI 백엔드
├── bridge/              # Falcosidekick webhook 수신 서비스
├── frontend/            # React + Vite 프론트엔드
├── docker-compose.yml   # backend, bridge, Chroma, Falco 실행 설정
└── README.md
```

## 사전 준비

`backend/.env` 파일을 생성하고 아래 값을 설정합니다.

```env
OPENAI_API_KEY=sk-...
DATABASE_URL=./runtime.db
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_COLLECTION=runtime_playbooks
```

## 실행 방법

### 1. Docker 서비스 실행

프로젝트 루트에서 실행합니다.

```bash
docker compose up --build
```

### 2. Frontend 실행

frontend 브랜치에서 코드 가져오기
새 터미널에서 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

### 3. 테스트 이벤트 생성

새 터미널에서 Falco 테스트 이벤트를 생성합니다.

```bash
docker compose --profile datagen run --rm event-generator run syscall --sleep 3s
```

이후, Frontend 페이지를 통해 들어오는 이벤트를 확인하고 보안관리자의 조치를 취합니다.

## 주요 접속 주소

| 서비스 | 주소 |
| --- | --- |
| Frontend | `http://localhost:5173` |
| Backend API | `http://localhost:8081` |
| Bridge | `http://localhost:5001` |
| Chroma | `http://localhost:8000` |
| Falcosidekick | `http://localhost:2801` |
