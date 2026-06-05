# 저장된 JSONL 이벤트를 지정한 실험 모드로 bridge에 재전송

import json
import argparse
import datetime
import time
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JSONL 이벤트 파일을 bridge webhook으로 재전송"
    )
    parser.add_argument("--dataset", required=True,
                        help="JSONL 이벤트 파일 (falco_events.jsonl 등)")
    parser.add_argument("--mode", required=True,
                        help="실험 모드 (bridge의 EXPERIMENT_MODE와 일치해야 함)")
    parser.add_argument("--webhook", default="http://localhost:5000/webhook",
                        help="bridge webhook URL")
    parser.add_argument("--delay", type=float, default=0.05,
                        help="이벤트 간 딜레이(초), 기본 0.05")
    parser.add_argument("--warmup-delay", type=float, default=0.0,
                        help="proposed 모드용: 각 룰의 첫 이벤트 후 대기 시간(초). "
                             "LLM 응답 시간보다 길게 설정해야 캐시 경쟁 조건 방지. "
                             "설정 시 데이터셋을 룰명 기준으로 정렬 후 재전송.")
    args = parser.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    # warmup-delay 설정 시: 룰별로 정렬해 같은 룰 이벤트가 연속되도록 함
    if args.warmup_delay > 0:
        records.sort(key=lambda r: r.get("payload", r).get("rule", ""))
        print(f"[warmup] 룰 기준 정렬 완료, 첫 이벤트 후 {args.warmup_delay}s 대기")

    out_dir = Path("datasets/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"{args.mode}_{ts}.jsonl"

    sent   = 0
    errors = 0
    seen_rules: set[str] = set()

    print(f"[{args.mode}] {args.dataset} → {args.webhook}")
    print(f"결과 저장: {out_file}\n")

    with open(out_file, "w", encoding="utf-8") as out:
        for lineno, record in enumerate(records, 1):
            payload = record.get("payload", record)
            rule    = payload.get("rule", "")
            is_first_of_rule = rule not in seen_rules
            seen_rules.add(rule)

            try:
                resp = httpx.post(
                    args.webhook,
                    json=payload,
                    timeout=30.0,
                )
                resp.raise_for_status()
                bridge_resp = resp.json()
                out.write(json.dumps({
                    "original":        record,
                    "bridge_response": bridge_resp,
                }, ensure_ascii=False) + "\n")
                sent += 1
                if sent % 50 == 0:
                    print(f"  전송 {sent}개 완료...")
            except Exception as exc:
                errors += 1
                out.write(json.dumps({
                    "original": record,
                    "error":    str(exc),
                }, ensure_ascii=False) + "\n")
                print(f"  [오류] 라인 {lineno}: {exc}")

            if args.warmup_delay > 0 and is_first_of_rule:
                time.sleep(args.warmup_delay)
            elif args.delay > 0:
                time.sleep(args.delay)

    print(f"\n[{args.mode}] 완료: 성공 {sent}개, 실패 {errors}개 → {out_file}")


if __name__ == "__main__":
    main()
