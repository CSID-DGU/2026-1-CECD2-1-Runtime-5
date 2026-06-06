# Runtime Security & LLM Optimization Project (Runtime-5)

본 프로젝트는 컨테이너 런타임 보안 도구인 **Falco**에서 발생하는 보안 이벤트를 **LLM(Large Language Model)** 으로 분석하고 대응하는 과정에서, **비용 절감(Token Efficiency)** 과 **응답 속도 향상(Latency Reduction)** 을 달성하기 위한 연구 및 실제 시스템 구현을 포함합니다.

---

## 📂 프로젝트 구조

프로젝트는 크게 **연구(Research)** 와 **시스템(System)** 두 개의 영역으로 나뉩니다.

### 🔬 [Research](./research) — 효율화 연구 및 실험
LLM 호출을 최소화하고 응답 성능을 극대화하기 위한 실험 환경입니다.
- **[Cache Optimization](./research/cache)**: **Semantic Cache**를 활용하여 동일하거나 유사한 보안 이벤트에 대해 LLM 재호출 없이 즉각적인 대응 결과를 반환하는 연구를 수행합니다.
- **[Prompt Optimization](./research/prompt)**: 보안 컨텍스트를 유지하면서도 토큰 소비를 극소화하는 **프롬프트 압축 전략(V1~V3)**을 설계하고 성능을 검증합니다.

### 🚀 [System](./system) — 통합 보안 서비스 구현
연구 결과를 바탕으로 구축된 실제 운영 가능한 보안 탐지 및 대응 서비스입니다.
- **[Backend](./system/backend)**: 연구된 캐시 로직과 프롬프트 최적화가 적용된 통합 백엔드 서비스입니다. Falco 이벤트를 수신하여 분석하고, Playbook 기반의 자동 대응 및 AI 인사이트를 제공합니다.
- **[Frontend](./system/frontend)**: 보안 이벤트를 실시간으로 모니터링하고, AI 분석 결과 확인 및 자동 대응 결과를 관리자가 제어할 수 있는 대시보드 웹 서비스입니다.

---

## 🛠 주요 기술 스택

- **Runtime Detection**: Falco, Falcosidekick
- **LLM / AI**: OpenAI (GPT-4o), Ollama (Qwen 2.5), Semantic Cache, VectorDB (pgvector)
- **Backend**: FastAPI (Python), Redis (Cache), PostgreSQL (Database)
- **Frontend**: React (Vite), Axios, TailwindCSS (Styled-components)
- **Environment**: Docker, Docker Compose

---

## 🔄 데이터 흐름 (System Flow)

1. **탐지**: `Falco`가 컨테이너 내 이상 징후(Syscall)를 감지합니다.
2. **중계**: `Falcosidekick`이 감지된 이벤트를 `System Backend`로 전송합니다.
3. **분석**:
   - **Playbook Match**: 기정의된 대응 규칙이 있는지 확인합니다.
   - **Semantic Cache**: 기존에 동일한 룰에 대한 분석 결과가 캐시에 있는지 확인합니다.
   - **LLM Analysis**: 캐시가 없을 경우 최적화된 프롬프트로 LLM에 분석을 요청합니다.
4. **대응**: 분석 결과에 따라 즉시 컨테이너 중지(`stop`) 또는 관리자 알림(`alert`)을 실행합니다.
5. **학습**: 관리자의 최종 승인 결과는 다시 Playbook 및 VectorDB에 반영되어 다음 탐지 시 효율을 높입니다.

---

## 🚀 시작하기

각 폴더 내의 `README.md` 파일을 참조하여 개별 구성 요소의 설치 및 실행 방법을 확인하세요.

- [연구 환경 설정 가이드](./research/cache/README.md)
- [시스템 백엔드 설정 가이드](./system/backend/README.md)
- [프론트엔드 설정 가이드](./system/frontend/README.md)
