# 컨테이너 보안 대응을 위한 LLM 프롬프트 최적화 (Prompt Optimization)

이 프로젝트는 컨테이너 런타임 보안 도구인 **Falco**의 이벤트를 LLM(Large Language Model)이 분석하여 자동 대응할 때 발생하는 **토큰 비용**과 **응답 지연(Latency)** 문제를 해결하기 위해 프롬프트 최적화를 수행한 결과물입니다.

## 1. 개요
보안 이벤트는 실시간으로 대량 발생하므로, 매번 방대한 자연어 프롬프트를 LLM에 전달하는 것은 비효율적입니다. 본 프로젝트에서는 동일한 판단 성능을 유지하면서 토큰 사용량을 극소화하는 3단계 프롬프트 진화 과정을 설계하고 실험하였습니다.

## 2. 프롬프트 버전별 전략

### [V1] Standard (기본형)
- **특징**: 풍부한 자연어 설명과 컨텍스트 포함.
- **구조**: 분석가 역할 부여, 상세 규칙 설명, 전체 JSON 필드 구조 명시.
- **장점**: 모델의 이해도가 높고 안정적인 결과 반환.
- **단점**: 토큰 소모가 매우 큼 (평균 수백 토큰).

### [V2] Compressed (압축형)
- **특징**: 불필요한 미사여구 및 자연어 가이드 제거.
- **구조**: 핵심 태스크와 핵심 필드(Rule, Priority, Command)만 전달.
- **최적화**: 지시문 초간결화, 응답 형식 최소화.

### [V3] Ultra-Compressed (초압축형)
- **특징**: 토큰 효율을 극대화하기 위해 키 매핑(Key Mapping) 도입.
- **구조**: 필드명을 1바이트 문자로 축약 (`action` → `a`, `threat_level` → `t`, `reason` → `r`).
- **최적화**: 자연어 문장 없이 기호와 약어 위주로 구성하여 최소 토큰으로 데이터 전달.

---

## 3. 실험 결과 및 시각화

프롬프트 버전에 따른 성능 비교 데이터는 `datasets/results/` 폴더 내의 이미지와 CSV를 통해 확인할 수 있습니다.

### 토큰 압축 효율 (Token Compression Graph)
V1 대비 V2, V3에서 프롬프트 토큰 수가 급격히 감소하는 것을 확인할 수 있습니다. 
- **관련 이미지**: `datasets/results/token_compression_graph.png`
- **관련 데이터**: `datasets/results/comparison.csv`

### 지연 시간 단축 (Latency Reduction)
토큰 수가 줄어듦에 따라 LLM의 추론 시간 및 네트워크 전송 시간이 단축되어 전체적인 대응 속도가 향상되었습니다.
- **관련 이미지**: `datasets/results/v1~3.png`

---

## 4. 사용 방법

프롬프트 버전은 환경 변수를 통해 간편하게 변경할 수 있습니다.

```bash
# V3 초압축 프롬프트 사용 예시
export PROMPT_VERSION=v3
docker compose up -d python-bridge
```

### 프롬프트 빌더 코드 (`bridge/prompts.py`)
```python
if version == "v3":
    # 초압축 프롬프트 (V3) - 토큰 극소화
    return f"Task: Container Sec. Output: {{\"a\":\"stop|pause|alert|ignore\",\"t\":\"h|m|l|n\",\"r\":\"str\"}}\nEvt: R:{rule},P:{priority},C:{cmdline}"
```

---

## 5. 결론 및 기대 효과
- **비용 절감**: V1 대비 V3 적용 시 토큰 비용을 최대 **80% 이상 절감** 가능.
- **성능 유지**: 압축된 프롬프트에서도 LLM(qwen2.5:0.5b 등)이 보안 위협을 정확히 판단함을 확인.
- **실시간성 확보**: 감소한 지연 시간 덕분에 실제 보안 침해 사고 발생 시 더 빠른 자동 대응이 가능.
