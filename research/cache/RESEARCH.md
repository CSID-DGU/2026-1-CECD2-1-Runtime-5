# 컨테이너 런타임 보안 이벤트의 LLM 기반 자동 대응 비용 효율화

> 팀 브리핑 및 논문 작성용 문서  
> 데이터셋 · 구현 · 코드 설명 포함

---

## 1. 연구 배경 및 동기

### 문제 정의

컨테이너 환경에서 Falco 같은 런타임 탐지 도구는 수십 가지 보안 이벤트를 실시간으로 생성한다.
기존 **playbook 기반 자동 대응**은 사전 정의된 룰에만 반응하며, 새로운 위협 패턴에 유연하게 대처하지 못한다.

이를 보완하기 위해 **LLM을 활용한 동적 판단** 시스템이 제안되고 있으나 두 가지 문제가 있다.

| 문제 | 내용 |
|---|---|
| **비용** | 이벤트 발생마다 LLM을 호출하면 토큰 소비가 이벤트 수에 비례해 선형 증가 |
| **지연** | LLM 호출 평균 7초+ → 실시간 보안 대응에 부적합 |

### 핵심 관찰

실제 운영 환경에서 **동일 룰 유형의 이벤트는 반복 발생**한다.  
예: "Execution from /dev/shm"이 하루에 수십 번 탐지될 때, 매번 LLM을 호출하는 것은 낭비다.  
동일 룰이면 LLM의 판단도 동일하다 → **캐시로 재사용 가능**.

---

## 2. 제안 방법

### 2단계 대응 구조

```
Falco 탐지 이벤트
        ↓
  [1단계] playbook 매핑?
   ┌─────┴─────┐
  Yes          No
   ↓            ↓
즉시 대응   [2단계] Semantic Cache 확인
(stop/alert)    ┌──────┴──────┐
              Hit            Miss
               ↓               ↓
           캐시 반환       Ollama LLM 호출
           (즉시)              ↓
                          결과 캐시 저장
```

### Semantic Cache 원리

- **캐시 키**: `rule + priority` 조합 → MD5 해시
- **동작**: 동일 키가 TTL 내 재발생하면 LLM 재호출 없이 이전 결과 반환
- **근거**: 동일 룰·동일 우선순위 이벤트는 LLM 판단도 항상 동일하다

### 실험 모드 3가지

| 모드 | 설명 | 역할 |
|---|---|---|
| `baseline_a` | 모든 미매핑 이벤트에 LLM 호출 | 비용 상한 기준선 |
| `baseline_b` | LLM 없음, playbook만 대응 | 비용 하한 기준선 |
| `proposed` | Semantic Cache 적용 | 제안 방법 |

---

## 3. 시스템 구성 및 파이프라인

```
falcosecurity/event-generator
          ↓  (syscall 트리거 → 실제 보안 이벤트 생성)
        Falco
          ↓  (룰 매칭 → 이벤트 탐지)
     falcosidekick
          ↓  (HTTP webhook 전달)
      python-bridge  ←──── 실험 핵심
          ↓
    bridge_data/ 기록
    (security_stats.csv, falco_events.jsonl)
```

### 인프라 컴포넌트

| 컴포넌트 | 이미지 | 역할 |
|---|---|---|
| Falco | falcosecurity/falco | 커널 syscall 모니터링 및 룰 기반 이벤트 탐지 |
| falcosidekick | falcosecurity/falcosidekick | Falco 이벤트를 HTTP webhook으로 중계 |
| python-bridge | 자체 빌드 | 실험 파이프라인 핵심 서버 (FastAPI) |
| Ollama (qwen2.5:0.5b) | ollama/ollama | 로컬 LLM 추론 |
| event-generator | falcosecurity/event-generator | Falco 룰 트리거용 공격 시뮬레이터 |

---

## 4. 데이터셋

### 수집 방법

`event-generator`가 컨테이너 내에서 실제 syscall을 실행해 Falco 룰을 트리거한다.  
Falco가 탐지 → falcosidekick이 python-bridge로 전달 → bridge가 `falco_events.jsonl`에 기록.

수집 시 LLM 호출 없이 빠르게 쌓기 위해 **baseline_b 모드**를 사용한다.

### 데이터셋 구성

- **파일**: `datasets/raw/experiment_dataset.jsonl`
- **크기**: 200개 이벤트 고정 스냅샷
- **출처**: falcosecurity/event-generator `run syscall --loop`

| 구분 | 수 | 비율 |
|---|---|---|
| playbook 매핑 이벤트 | 47 | 23.5% |
| LLM 라우팅 이벤트 | 153 | 76.5% |

### playbook 매핑 5개 (event-generator 실제 트리거 기준)

| 룰 | MITRE | 대응 | 수 |
|---|---|---|---|
| Drop and execute new binary in container | T1485 | stop | 10 |
| PTRACE attached to process | T1068 | stop | 10 |
| Netcat Remote Code Execution in Container | T1059 | stop | 9 |
| Read sensitive file untrusted | T1083 | alert | 9 |
| Run shell untrusted | T1059 | stop | 9 |

### LLM 라우팅 대상 14종 (데이터셋 내 분포)

| 룰 | Priority | 수 |
|---|---|---|
| Execution from /dev/shm | Warning | 22 |
| Read sensitive file trusted after startup | Warning | 11 |
| Disallowed SSH Connection Non Standard Port | Notice | 11 |
| Find AWS Credentials | Warning | 11 |
| Remove Bulk Data from Disk | Warning | 11 |
| Clear Log Activities | Warning | 11 |
| Create Symlink Over Sensitive Files | Warning | 10 |
| Directory traversal monitored file read | Warning | 10 |
| PTRACE anti-debug attempt | Notice | 10 |
| Search Private Keys or Passwords | Warning | 10 |
| Packet socket created in container | Notice | 9 |
| Fileless execution via memfd_create | Critical | 9 |
| Create Hardlink Over Sensitive Files | Warning | 9 |
| System user interactive | Informational | 9 |

### JSONL 이벤트 구조

`falco_events.jsonl` 한 줄의 구조 (bridge가 기록하는 형식):

```json
{
  "timestamp": "2026-05-17T05:31:42",
  "payload": {
    "rule": "Execution from /dev/shm",
    "priority": "Warning",
    "output": "...",
    "output_fields": {
      "container.id": "d15950a38059",
      "container.name": "falco-event-generator",
      "proc.cmdline": "sh -c /dev/shm/...",
      "proc.name": "sh"
    },
    "tags": ["T1059.004", "container"]
  },
  "remediation": { "status": "ignored", "reason": "No MITRE mapping matched" },
  "event_type": "ignored",
  "latency_ms": 0,
  "experiment_mode": "baseline_b",
  "ground_truth": "true",
  "rule_matched": 0,
  "llm_called": 0,
  "cache_hit": 0,
  "gate_decision": "ignored",
  "llm_result": {}
}
```

---

## 5. 코드 설명

### 디렉토리 구조

```
bridge/
├── main.py          ← 웹훅 핸들러 + 3개 실험 모드 분기 (핵심)
├── remediation.py   ← playbook 매핑 엔진
├── cache.py         ← Semantic Cache
├── prompts.py       ← LLM 프롬프트 빌더
└── Dockerfile

experiments/
├── replay_experiment.py  ← 데이터셋을 모드별로 bridge에 재전송
└── eval.py               ← 결과 집계 및 비교표 출력
```

---

### `bridge/main.py` — 실험 파이프라인 핵심

FastAPI 서버. falcosidekick으로부터 POST `/webhook`으로 Falco 이벤트를 받아 처리한다.

**처리 흐름 (handle_falco_alert 함수)**

```python
# Step 1: playbook 매핑 확인
remediation_result = remediator.remediate(payload)
rule_matched = remediation_result.get("status") != "ignored"

if rule_matched:
    # playbook 매핑 → LLM 없이 즉시 대응
    gate_decision = "rule"

else:
    # Step 2: 실험 모드별 분기
    if EXPERIMENT_MODE == "baseline_a":
        llm_result = await call_llm(...)      # 항상 LLM 호출

    elif EXPERIMENT_MODE == "baseline_b":
        pass                                   # 아무것도 하지 않음

    elif EXPERIMENT_MODE == "proposed":
        cached = event_cache.get(payload)
        if cached:
            llm_result = cached["result"]      # 캐시 히트
        else:
            llm_result = await call_llm(...)   # 캐시 미스 → LLM 호출 후 저장
            event_cache.set(payload, llm_result)
```

**기록 항목** (처리 후 CSV + JSONL에 동시 append)

| 컬럼 | 내용 |
|---|---|
| `experiment_mode` | baseline_a / baseline_b / proposed |
| `rule_matched` | playbook 매핑 여부 (0/1) |
| `llm_called` | LLM 호출 여부 (0/1) |
| `cache_hit` | 캐시 히트 여부 (0/1) |
| `gate_decision` | rule / llm / cache-hit / ignored |
| `prompt_tokens` | LLM 프롬프트 토큰 수 |
| `completion_tokens` | LLM 응답 토큰 수 |
| `latency_ms` | 처리 지연 시간 (ms) |
| `llm_action` | LLM이 결정한 대응 (stop/alert/ignore 등) |

**환경변수**

| 변수 | 기본값 | 설명 |
|---|---|---|
| `EXPERIMENT_MODE` | `baseline_a` | 실험 모드 |
| `CACHE_TTL` | `60` | 캐시 유효 시간 (초) |
| `REMEDIATION_DRY_RUN` | `true` | true면 컨테이너 실제 중단 안 함 |
| `IS_ATTACK` | `true` | 수집 시 ground_truth 레이블 |

---

### `bridge/remediation.py` — Playbook 매핑 엔진

Falco 이벤트의 `rule` 필드를 소문자로 정규화하여 5개 playbook 패턴과 매칭한다.

```python
def _classify(self, payload) -> RemediationDecision | None:
    rule_name = str(payload.get("rule", "")).lower()

    def match(pattern):
        return pattern in rule_name  # 부분 문자열 매칭

    if match("drop and execute new binary in container"):
        return RemediationDecision(
            technique_id="T1485", action="stop", ...
        )
    # ... 나머지 4개
    return None  # 미매핑 → main.py에서 LLM으로 라우팅
```

**매핑되면** `remediate()`가 Docker SDK로 컨테이너를 stop/pause/alert 처리.  
**미매핑이면** `{"status": "ignored"}` 반환 → main.py에서 LLM 라우팅.

`REMEDIATION_DRY_RUN=true`이면 실제 Docker 조작 없이 `{"status": "dry-run"}` 반환 (실험 환경 기본값).

> **확장 포인트**: 새 룰을 추가하려면 `_classify()` 메서드에 `if match(...)` 블록 추가.

---

### `bridge/cache.py` — Semantic Cache

인메모리 딕셔너리 기반 TTL 캐시. bridge 프로세스가 살아있는 동안 유지된다.

```python
def _key(self, payload) -> str:
    sig = f"{payload.get('rule', '')}:{payload.get('priority', '')}"
    return hashlib.md5(sig.encode()).hexdigest()
```

- **캐시 키**: `rule명:priority` → MD5 (예: `"Execution from /dev/shm:Warning"`)
- **저장**: LLM 결과 dict + 저장 시각(ts)
- **조회**: 키 존재 + `(현재시각 - ts) < TTL`이면 히트

```python
def get(self, payload) -> dict | None:
    entry = self._store.get(key)
    if entry and (time.time() - entry["ts"]) < self.ttl:
        self.hits += 1
        return {"result": entry["result"], "cache_key": key}
    self.misses += 1
    return None
```

> **주의**: 인메모리 구조라 bridge 재시작 시 캐시 초기화됨.  
> **확장 포인트**: Redis로 교체하면 프로세스 재시작 후에도 캐시 유지 가능.

---

### `bridge/prompts.py` — LLM 프롬프트 빌더

Falco 이벤트 dict에서 주요 필드를 추출해 LLM 프롬프트 문자열을 생성한다.

```python
def build_prompt(payload) -> str:
    # 추출 필드: rule, priority, container명, proc.cmdline, output
    return f"""You are a container runtime security analyst.
Falco detected: Rule={rule}, Priority={priority}, ...
Respond in JSON: {{"action": "stop|pause|alert|ignore", ...}}"""
```

LLM은 반드시 JSON으로 응답해야 하며, `main.py`의 `call_llm()`이 응답에서 `{...}` 블록을 파싱한다.  
파싱 실패 시 `{"action": "ignore"}` 폴백.

> **확장 포인트**: 프롬프트에 컨테이너 이미지 정보, 과거 이벤트 이력 등을 추가하면 LLM 판단 품질 향상 가능.

---

### `experiments/replay_experiment.py` — 실험 재현 스크립트

수집된 고정 데이터셋(`experiment_dataset.jsonl`)을 읽어 각 이벤트의 `payload`를 bridge에 재전송한다.

```python
record = json.loads(line)
payload = record.get("payload", record)  # 중첩 구조에서 원본 Falco 이벤트 추출

resp = httpx.post(webhook_url, json=payload, timeout=30.0)
```

- 이벤트 간 `--delay 0.1`초 대기 (기본값)
- 전송 결과를 `datasets/results/{mode}_{timestamp}.jsonl`에 저장
- bridge의 `EXPERIMENT_MODE`와 `--mode` 인자가 일치해야 정확한 실험

> **주의**: 전송 중 bridge가 `falco_events.jsonl`에 append하므로, 데이터셋 파일은 반드시 별도 스냅샷(`experiment_dataset.jsonl`)을 사용해야 함.

---

### `experiments/eval.py` — 결과 집계

`security_stats.csv`를 읽어 `experiment_mode`별로 그룹핑 후 비교표를 출력한다.

```python
# 핵심 집계 지표
llm_calls   = sum(llm_called for r in rows)
total_toks  = sum(prompt_tokens + completion_tokens for r in rows)
cache_hits  = sum(cache_hit for r in rows)

# baseline_a 대비 감소율 계산
token_reduction = f"{(base_tokens - mode_tokens) / base_tokens:.1%} ↓"
```

출력 지표: LLM 호출 수, LLM 비율, LLM 감소율, 토큰 수, 토큰 감소율, 평균 지연, 캐시 히트, 캐시율.

---

## 6. 실험 결과

> **실험 조건**: n=200, 이벤트 간 딜레이 1.5s  
> playbook 매핑 47건(23.5%) + LLM 라우팅 153건(76.5%)  
> 데이터 수집: baseline_b 모드로 event-generator 실행 → 200개 고정 스냅샷 → 3개 모드 replay

### Table 1 — LLM 효율 비교 (baseline_a 기준, n=200, CACHE_TTL=3600s)

| 모드 | LLM 호출 | LLM 비율 | LLM 감소율 | 총 토큰 | 토큰 감소율 | 평균 지연 | 캐시 히트 | 캐시율 |
|---|---|---|---|---|---|---|---|---|
| baseline_a | 153 | 76.5% | 기준 | 67,740 | 기준 | 6,783 ms | 0 | 0% |
| baseline_b | 0 | 0% | 100% ↓ | 0 | 100% ↓ | 0 ms | 0 | 0% |
| **proposed** | **14** | **7.0%** | **90.8% ↓** | **6,061** | **91.1% ↓** | **606 ms** | **139** | **69.5%** |

### 결과 해석

- **proposed**는 14종 룰의 **첫 이벤트(14회)만 LLM 호출**, 나머지 **139회는 캐시**로 처리
- LLM 호출 90.8% 감소, 토큰 91.1% 감소, 지연 91.1% 단축
- **baseline_b**는 LLM 비용 0이지만 playbook 미매핑 이벤트(76.5%)에 전혀 대응 못함
- **proposed**는 baseline_a와 동일한 LLM 판단 결과를 제공하면서 비용만 절감

> proposed의 캐시 결과 = baseline_a의 LLM 결과이므로 대응 품질은 동일하다.

---

## 7. 논문 핵심 주장

> 실제 보안 운영에서 playbook은 확신도 높은 위협만 커버한다.  
> Falco가 탐지한 나머지 이벤트를 LLM이 판단하되,  
> Semantic Cache로 동일 룰 유형의 반복 이벤트에 대한 LLM 재호출을 제거한다.  
> 이를 통해 LLM 호출 횟수를 **90% 이상 줄이면서** 대응 품질은 baseline_a와 동일하게 유지한다.

### 기여점

1. **Playbook + LLM 혼합 아키텍처**: 확신도 높은 위협은 playbook, 나머지는 LLM
2. **Semantic Cache**: rule+priority 기반 캐시로 LLM 반복 호출 제거
3. **정량 검증**: 실제 Falco 이벤트 기반 200개 데이터셋으로 3개 모드 비교 실험

---

## 8. Ablation Study

### 8-1. Cache TTL Ablation (완료)

동일 데이터셋(n=200)에서 CACHE_TTL만 변경하며 캐시 효율 변화를 측정.

#### Table 2 — TTL별 proposed 모드 성능 (baseline_a 기준)

| TTL | LLM 호출 | LLM 비율 | LLM 감소율 | 총 토큰 | 토큰 감소율 | 평균 지연 | 캐시 히트 | 캐시율 |
|---|---|---|---|---|---|---|---|---|
| 30s | 137 | 68.5% | 10.5% ↓ | 60,084 | 11.3% ↓ | 6,107 ms | 16 | 8.0% |
| 60s | 133 | 66.5% | 13.1% ↓ | 58,258 | 14.0% ↓ | 6,051 ms | 20 | 10.0% |
| 300s | 28 | 14.0% | 81.7% ↓ | 12,395 | 81.7% ↓ | 1,230 ms | 125 | 62.5% |
| **3600s** | **14** | **7.0%** | **90.8% ↓** | **6,061** | **91.1% ↓** | **606 ms** | **139** | **69.5%** |

#### TTL 분석

- **TTL=30~60s**: 캐시 거의 무효 (8~10%). 같은 룰 재발 간격(~36s)이 TTL을 초과해 대부분 만료됨
- **TTL=300s**: 성능 급격히 개선 (62.5% 캐시율). TTL이 재발 간격을 충분히 포괄
- **TTL=3600s**: 최적 (69.5% 캐시율, 90.8% LLM 감소). 1시간 내 동일 룰 재발 시 LLM 재호출 없음
- **결론**: TTL ≥ 300s 이상에서 실질적 효과 발생. 운영 환경에서는 3600s(1시간) 권장

### 8-2. Playbook 크기 Ablation (계획)

Playbook 크기와 LLM 호출률의 상관관계를 측정한다.

| Playbook 크기 | LLM 라우팅 비율 | 캐시 효과 |
|---|---|---|
| 5개 (현재) | ~76.5% | 극대 |
| 10개 | ~60% | 중간 |
| 22개 (전체) | ~32% | 소폭 |

`remediation.py`의 `_classify()`에 룰을 추가하고 동일 데이터셋으로 재실험하면 된다.

---

## 9. 실험 재현 방법

### 환경 요구사항

- Docker + Docker Compose
- Ollama에 `qwen2.5:0.5b` 모델 로드 (`docker compose up -d ollama` 후 `docker exec ollama ollama pull qwen2.5:0.5b`)
- Python 3.10+ (호스트에서 실험 스크립트 실행용)

### Step 1 — 인프라 시작

```bash
docker compose up -d falco falcosidekick ollama python-bridge
```

### Step 2 — 데이터 수집 (baseline_b 모드)

`docker-compose.yml`에서 `EXPERIMENT_MODE=baseline_b` 확인 후:

```bash
# falcosidekick 켠 상태에서 event-generator 실행
docker compose --profile datagen up -d event-generator

# 200개 수집될 때까지 대기
watch -n 5 'wc -l bridge_data/falco_events.jsonl'

# 200개 도달 후 수집 중단
docker compose stop event-generator falcosidekick
```

### Step 3 — 데이터셋 확정

```bash
python3 -c "
import json
events = []
with open('bridge_data/falco_events.jsonl') as f:
    for line in f:
        d = json.loads(line)
        if d.get('experiment_mode') == 'baseline_b' and d.get('event_type') in ('ignored', 'rule-matched'):
            events.append(line)
with open('datasets/raw/experiment_dataset.jsonl', 'w') as f:
    for line in events[:200]:
        f.write(line)
print(f'데이터셋 확정: {min(len(events),200)}개')
"
```

### Step 4 — 실험 실행 (3개 모드)

falcosidekick을 내린 상태에서 모드별로 진행한다.

```bash
# security_stats.csv 초기화
python3 -c "
import csv
headers = ['timestamp','event_type','rule_name','priority','prompt_tokens','completion_tokens',
           'latency_ms','remediation_status','remediation_action','mitre_technique',
           'target_container','attack_source','attack_label','attack_id','container_id',
           'container_image','event_source','experiment_mode','ground_truth','rule_matched',
           'llm_called','cache_hit','cache_key','gate_decision','llm_action','llm_threat_level','cache_ttl']
with open('bridge_data/security_stats.csv', 'w', newline='') as f:
    csv.writer(f).writerow(headers)
"

# 각 모드별 실행 (docker-compose.yml의 EXPERIMENT_MODE 변경 후 bridge 재시작)
for MODE in baseline_a baseline_b proposed; do
    sed -i "s/EXPERIMENT_MODE=.*/EXPERIMENT_MODE=${MODE}/" docker-compose.yml
    docker compose up -d --force-recreate python-bridge
    sleep 4
    python3 experiments/replay_experiment.py \
        --dataset datasets/raw/experiment_dataset.jsonl \
        --mode $MODE \
        --delay 1.5
done
```

> **주의**: `proposed` 모드는 `CACHE_TTL=3600`으로 설정해야 정상 캐시 효과 측정 가능.

### Step 5 — 결과 집계

```bash
python3 experiments/eval.py \
    --csv bridge_data/security_stats.csv \
    --out datasets/results/comparison.csv
```

### 재현 가능성 참고

| 지표 | 재현 가능 여부 |
|---|---|
| LLM 호출 수 · 캐시 히트 수 · rule_matched 수 | ✅ 동일 (결정론적) |
| 토큰 수 (prompt/completion) | ⚠️ LLM 응답 길이 미세 변동 |
| 평균 지연 (latency_ms) | ⚠️ 시스템 부하에 따라 변동 |

---

## 10. 향후 연구 방향

| 항목 | 현재 | 개선 방향 |
|---|---|---|
| **LLM 모델** | qwen2.5:0.5b (로컬) | GPT-4o, Claude 등 실제 API 비용 측정 |
| **캐시 키 정밀도** | rule + priority | 컨테이너 유형, 프로세스 이름 추가 |
| **캐시 저장소** | 인메모리 (재시작 시 초기화) | Redis로 교체 → 영속성 확보 |
| **캐시 TTL** | 3600s (고정, ablation 완료) | 이벤트 도착 간격 기반 동적 TTL |
| **데이터셋 규모** | 200개 | 실제 운영 환경 대규모 이벤트 |
| **대응 검증** | DRY_RUN (실제 중단 없음) | 실 환경 컨테이너 대응 검증 |
