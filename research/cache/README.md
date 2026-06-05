# 컨테이너 보안 이벤트 LLM 효율화 연구

---

## 팀원 실행 가이드

### 사전 조건

| 항목 | 확인 방법 |
|---|---|
| Docker + Docker Compose | `docker compose version` |
| 여유 디스크 4GB 이상 | `df -h` |
| 여유 RAM 6GB 이상 | `free -h` |
| Linux 호스트 (Falco 필수) | WSL2 불가, Ubuntu VM 권장 |

> **주의**: Falco는 커널 모듈을 사용하므로 **Linux 네이티브 환경**에서만 정상 동작합니다.

---

### Step 1 — 저장소 클론 및 이동

```bash
git clone <저장소 URL>
cd 2025-2-CECD1-2-Runtime-5
```

---

### Step 2 — LLM 모델 준비 확인

`ollama_data/` 폴더에 모델이 이미 포함되어 있습니다. 없다면 아래 명령으로 다운로드:

```bash
# 스택 먼저 올린 후 모델 pull
docker compose up -d ollama
docker exec -it ollama ollama pull qwen2.5:0.5b
```

---

### Step 3 — 전체 스택 시작

```bash
docker compose up -d
```

컨테이너 상태 확인:

```bash
docker compose ps
```

아래 4개가 모두 `Up` 상태여야 합니다:

| 컨테이너 | 역할 |
|---|---|
| `ollama` | LLM 추론 엔진 |
| `falco` | 커널 syscall 탐지 |
| `falcosidekick` | Falco → bridge 이벤트 중계 |
| `python-bridge` | 실험 파이프라인 (webhook 수신) |

bridge 정상 기동 확인:

```bash
curl http://localhost:5000/status
```

---

### Step 4 — 데이터셋 준비

`datasets/raw/experiment_dataset.jsonl` 파일이 이미 **200개 고정 스냅샷**으로 포함되어 있습니다.  
새로 수집할 필요 없이 Step 5로 바로 이동하세요.

<details>
<summary>데이터를 새로 수집하고 싶다면 (선택 사항)</summary>

```bash
# 기존 데이터 초기화
head -1 bridge_data/security_stats.csv > /tmp/h.csv && mv /tmp/h.csv bridge_data/security_stats.csv
rm -f bridge_data/falco_events.jsonl

# LLM 없이 빠른 수집을 위해 baseline_b 모드로 전환
sed -i 's/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=baseline_b/' docker-compose.yml
docker compose up -d --force-recreate python-bridge

# 공격 이벤트 생성기 실행 (datagen 프로파일)
docker compose --profile datagen up -d event-generator

# 200줄 이상 수집될 때까지 대기
watch -n 3 'wc -l bridge_data/falco_events.jsonl'

# 200줄 이상 확인 후 중단 & 스냅샷 생성
docker compose stop event-generator
head -200 bridge_data/falco_events.jsonl > datasets/raw/experiment_dataset.jsonl
```

</details>

---

### Step 5 — 3개 모드 실험 실행

> **실험 전 반드시 CSV를 초기화**하세요. 이전 결과가 섞이면 집계가 틀립니다.

```bash
# CSV 초기화
head -1 bridge_data/security_stats.csv > /tmp/h.csv && mv /tmp/h.csv bridge_data/security_stats.csv

# 3개 모드 순서대로 실행
for mode in baseline_a baseline_b proposed; do
  echo "=== 모드: $mode ==="
  sed -i "s/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=$mode/" docker-compose.yml
  docker compose up -d --force-recreate python-bridge
  sleep 3
  python3 experiments/replay_experiment.py \
    --dataset datasets/raw/experiment_dataset.jsonl \
    --mode $mode \
    --webhook http://localhost:5000/webhook
done

# 완료 후 baseline_a로 원복
sed -i 's/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=baseline_a/' docker-compose.yml
docker compose up -d --force-recreate python-bridge
```

각 모드별 소요 시간 예상:
- `baseline_b`: ~10초 (LLM 호출 없음)
- `baseline_a`: ~18분 (153회 LLM 호출)
- `proposed`: ~2분 (14회만 LLM 호출)

---

### Step 6 — 결과 집계

```bash
python3 experiments/eval.py \
  --csv bridge_data/security_stats.csv \
  --out datasets/results/comparison.csv
```

터미널에 아래와 같은 비교표가 출력됩니다:

```
=== LLM 효율 비교 (baseline_a 기준) ===
mode            total   llm_calls   llm_rate   ...
------------------------------------------------
baseline_a      200     153         76.5%      ...
baseline_b      200     0           0.0%       ...
proposed        200     14          7.0%       ...
```

CSV 결과는 `datasets/results/comparison.csv`에 저장됩니다.

---

### 실험 중 상태 모니터링

```bash
# 현재 모드 및 캐시 상태 확인
curl http://localhost:5000/status

# bridge 실시간 로그
docker logs -f python-bridge

# 처리된 이벤트 수 확인
wc -l bridge_data/falco_events.jsonl
tail -f bridge_data/falco_events.jsonl | python3 -c "import sys,json; [print(json.loads(l)['event_type']) for l in sys.stdin]"
```

---

### 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `falco` 컨테이너가 바로 종료됨 | 커널 모듈 로드 실패 | `docker logs falco` 확인, Linux 네이티브 환경 필요 |
| `curl localhost:5000/status` 응답 없음 | bridge 기동 중 또는 실패 | `docker logs python-bridge` 확인 |
| LLM 호출 타임아웃 | Ollama 모델 미로드 | `docker exec ollama ollama list` 로 qwen2.5:0.5b 확인 |
| 실험 결과 행 수가 200이 안 됨 | webhook 전송 중 오류 | replay 스크립트 출력의 실패 건수 확인 |

---

Falco가 탐지한 런타임 보안 이벤트를 LLM으로 분석할 때,
**Semantic Cache**를 통해 LLM 호출 횟수와 토큰 소비를 줄이는 방법을 제안하는 연구입니다.

---

## 연구 핵심 주장

> playbook은 가장 확신도 높은 위협 5개만 자동 대응하고,
> 나머지 이벤트는 LLM이 판단한다.
> 동일 룰 유형의 이벤트는 Semantic Cache로 LLM 재호출 없이 처리하여
> 호출 횟수를 90% 이상 줄인다.

---

## 파이프라인

```
event-generator
      ↓ (syscall 트리거)
    Falco
      ↓ (이벤트 감지)
 falcosidekick
      ↓ (webhook 전달)
 python-bridge ──────────────────────────────────────┐
      │                                               │
      ├─ playbook 매핑? ──── Yes ──→ 즉시 대응 (stop/alert)
      │                                               │
      └─ No (LLM 라우팅)                              │
            │                                         │
     ┌──────┴──────┐                                  │
  cache hit?      No                                  │
     │             ↓                                  │
  캐시 반환    Ollama LLM 호출                         │
                   ↓                                  │
              결과 캐시 저장                            │
                                                      │
         bridge_data/ 기록 ←──────────────────────────┘
```

---

## 실험 모드 3가지

| 모드 | 설명 |
|---|---|
| `baseline_a` | playbook 미매핑 이벤트 전부 LLM 호출 (비교 기준) |
| `baseline_b` | LLM 없음, playbook 5개만 대응 |
| `proposed`   | Semantic Cache 적용 — 첫 이벤트만 LLM, 이후 캐시 재사용 |

---

## playbook 5개 (event-generator 실제 트리거 기준)

| 룰 | MITRE | 대응 |
|---|---|---|
| Drop and execute new binary in container | T1485 | stop |
| Run shell untrusted | T1059 | stop |
| Netcat Remote Code Execution in Container | T1059 | stop |
| PTRACE attached to process | T1068 | stop |
| Read sensitive file untrusted | T1083 | alert |

나머지 룰은 LLM으로 라우팅됩니다.

---

## 디렉토리 구조

```
.
├── bridge/                  # python-bridge 소스
│   ├── main.py              # 웹훅 핸들러 + 3개 실험 모드 분기
│   ├── remediation.py       # playbook 매핑 엔진
│   ├── cache.py             # Semantic Cache (rule+priority 기반)
│   ├── prompts.py           # LLM 프롬프트 빌더
│   └── Dockerfile
├── bridge_data/
│   ├── security_stats.csv   # 모드별 replay 결과 누적 → eval.py 입력 (실험 전 초기화 필수)
│   └── falco_events.jsonl   # bridge가 처리한 이벤트 전체 append 기록
├── datasets/
│   ├── raw/                 # experiment_dataset.jsonl — 수집 200개 고정 스냅샷 (실험 기준)
│   └── results/             # 모드별 replay 결과 + comparison.csv
├── experiments/
│   ├── replay_experiment.py # 데이터셋을 3개 모드로 재전송
│   └── eval.py              # LLM 효율 집계 및 비교표 출력
├── falco/                   # Falco 탐지 룰 설정
├── ollama_data/             # qwen2.5:0.5b 모델
└── docker-compose.yml
```

---

## 실행 방법

### 1. 스택 시작

```bash
docker compose up -d
```

### 2. 데이터 수집 (event-generator 기반)

```bash
# 수집 전 초기화
head -1 bridge_data/security_stats.csv > /tmp/h.csv && mv /tmp/h.csv bridge_data/security_stats.csv
rm -f bridge_data/falco_events.jsonl

# LLM 없이 빠르게 수집하기 위해 baseline_b 모드로 전환
sed -i 's/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=baseline_b/' docker-compose.yml
docker compose up -d --force-recreate python-bridge

# event-generator 실행 (datagen 프로파일)
docker compose --profile datagen up -d event-generator

# 200줄 이상 수집 확인
wc -l bridge_data/falco_events.jsonl

# event-generator 중단 후 고정 스냅샷 생성
docker compose stop event-generator
head -200 bridge_data/falco_events.jsonl > datasets/raw/experiment_dataset.jsonl
```

### 3. 3개 모드 실험

```bash
# CSV 초기화 (실험 전 필수 — 이전 실험 결과가 섞이지 않도록)
head -1 bridge_data/security_stats.csv > /tmp/h.csv && mv /tmp/h.csv bridge_data/security_stats.csv

for mode in baseline_a baseline_b proposed; do
  sed -i "s/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=$mode/" docker-compose.yml
  docker compose up -d --force-recreate python-bridge
  sleep 3
  python3 experiments/replay_experiment.py \
    --dataset datasets/raw/experiment_dataset.jsonl \
    --mode $mode \
    --webhook http://localhost:5000/webhook
done

# 완료 후 baseline_a로 원복
sed -i 's/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=baseline_a/' docker-compose.yml
docker compose up -d --force-recreate python-bridge
```

### 4. 결과 집계

```bash
python3 experiments/eval.py \
  --csv bridge_data/security_stats.csv \
  --out datasets/results/comparison.csv
```

---

## 실험 결과

### 모드별 비교 (n=200, CACHE_TTL=3600s)

| 모드 | LLM 호출 | LLM 비율 | LLM 감소율 | 총 토큰 | 토큰 감소율 | 평균 지연 | 캐시 히트 | 캐시율 |
|---|---|---|---|---|---|---|---|---|
| baseline_a | 153 | 76.5% | 기준 | 67,740 | 기준 | 6,783 ms | 0 | 0% |
| baseline_b | 0 | 0% | 100% ↓ | 0 | 100% ↓ | 0 ms | 0 | 0% |
| **proposed** | **14** | **7.0%** | **90.8% ↓** | **6,061** | **91.1% ↓** | **606 ms** | **139** | **69.5%** |

- proposed는 14종 룰의 **첫 이벤트(14회)만 LLM 호출**, 나머지 **139회는 캐시** 처리
- LLM 호출 **90.8% 감소**, 토큰 **91.1% 감소**, 지연 **91.1% 단축**
- baseline_b와 달리 playbook 미매핑 이벤트(76.5%)에도 LLM 판단 유지

---

### TTL Ablation (n=200, proposed 모드)

| CACHE_TTL | LLM 호출 | LLM 비율 | LLM 감소율 | 총 토큰 | 토큰 감소율 | 평균 지연 | 캐시 히트 | 캐시율 |
|---|---|---|---|---|---|---|---|---|
| 30s | 137 | 68.5% | 10.5% ↓ | 60,084 | 11.3% ↓ | 6,107 ms | 16 | 8.0% |
| 60s | 133 | 66.5% | 13.1% ↓ | 58,258 | 14.0% ↓ | 6,051 ms | 20 | 10.0% |
| 300s | 28 | 14.0% | 81.7% ↓ | 12,395 | 81.7% ↓ | 1,230 ms | 125 | 62.5% |
| **3600s** | **14** | **7.0%** | **90.8% ↓** | **6,061** | **91.1% ↓** | **606 ms** | **139** | **69.5%** |

- **TTL=30~60s**: 캐시 거의 무효 (8~10%). 동일 룰 재발 간격(~36s)이 TTL을 초과해 대부분 만료
- **TTL=300s**: 성능 급격히 개선 (62.5% 캐시율). TTL이 재발 간격을 충분히 포괄
- **TTL=3600s**: 최적 (69.5% 캐시율). 운영 환경 권장값
- **결론**: TTL ≥ 300s 이상에서 실질적 효과 발생

---

## 환경변수 (docker-compose.yml)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `EXPERIMENT_MODE` | `baseline_a` | 실험 모드 선택 |
| `CACHE_TTL` | `60` | 캐시 유효 시간 (초) |
| `REMEDIATION_DRY_RUN` | `true` | true면 컨테이너 실제 중단 안 함 |
| `IS_ATTACK` | `true` | 수집 데이터 ground_truth 레이블 |
