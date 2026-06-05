# 실험 결과 집계 및 비교표 출력 — LLM 호출·토큰 효율 중심

import csv
import argparse
from pathlib import Path
from collections import defaultdict

_MODES = ["baseline_a", "baseline_b"]  # proposed는 TTL별로 동적 추가


def _bool(val) -> bool:
    return str(val).lower() in ("true", "1", "yes")


def int_or(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _infer_mode(row: dict) -> str:
    mode = row.get("experiment_mode", "")
    if not mode or mode == "unknown":
        return "unknown"
    ttl = row.get("cache_ttl", "")
    if mode == "proposed" and ttl:
        return f"proposed(ttl={ttl}s)"
    return mode


def _infer_llm_called(row: dict) -> int:
    if "llm_called" in row and row["llm_called"] != "":
        return int_or(row["llm_called"])
    if "llm_skipped" in row and row["llm_skipped"] != "":
        return 0 if _bool(row["llm_skipped"]) else 1
    return 0


def _infer_cache_hit(row: dict) -> int:
    if "cache_hit" in row and row["cache_hit"] != "":
        return int_or(row["cache_hit"])
    return 0


def compute_metrics(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {}

    llm_calls   = sum(_infer_llm_called(r) for r in rows)
    cache_hits  = sum(_infer_cache_hit(r) for r in rows)
    prompt_toks = sum(int_or(r.get("prompt_tokens")) for r in rows)
    comp_toks   = sum(int_or(r.get("completion_tokens")) for r in rows)
    total_toks  = prompt_toks + comp_toks
    latencies   = [int_or(r.get("latency_ms")) for r in rows]
    avg_lat     = sum(latencies) / len(latencies) if latencies else 0

    return {
        "total":            n,
        "llm_calls":        llm_calls,
        "llm_rate":         f"{llm_calls / n:.1%}",
        "prompt_tokens":    prompt_toks,
        "completion_tokens": comp_toks,
        "total_tokens":     total_toks,
        "token_reduction":  "—",          # baseline_a 대비, 후처리로 채움
        "avg_latency_ms":   f"{avg_lat:.1f}",
        "cache_hits":       cache_hits,
        "cache_rate":       f"{cache_hits / n:.1%}",
    }


def print_table(title: str, results: dict, modes: list[str],
                fields: list[str], col_w: int = 18) -> None:
    print(f"\n=== {title} ===")
    header = f"{'mode':<16}" + "".join(f"{f:<{col_w}}" for f in fields)
    print(header)
    print("-" * len(header))
    for mode in modes:
        if mode not in results:
            continue
        r = results[mode]
        print(f"{mode:<16}" + "".join(f"{str(r.get(f, 'N/A')):<{col_w}}" for f in fields))


def main() -> None:
    parser = argparse.ArgumentParser(description="실험 결과 집계 — LLM 효율 중심")
    parser.add_argument("--csv", default="bridge_data/security_stats.csv")
    parser.add_argument("--out", default="datasets/results/comparison.csv")
    args = parser.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in [k for k in r if k is None]:
            del r[k]

    if not rows:
        print("데이터 없음")
        return

    print(f"총 {len(rows)}행 로드")

    mode_rows: dict[str, list] = defaultdict(list)
    for r in rows:
        mode_rows[_infer_mode(r)].append(r)

    proposed_modes = sorted(
        [m for m in mode_rows if m.startswith("proposed")],
        key=lambda m: int_or(m.split("ttl=")[-1].rstrip("s")) if "ttl=" in m else 0
    )
    modes = [m for m in _MODES if m in mode_rows] + proposed_modes
    modes += [m for m in mode_rows if m not in _MODES and not m.startswith("proposed")]

    results: dict[str, dict] = {m: compute_metrics(mode_rows[m]) for m in modes}

    # baseline_a 토큰을 기준으로 절감률 계산
    base_tokens = results.get("baseline_a", {}).get("total_tokens", 0)
    base_calls  = results.get("baseline_a", {}).get("llm_calls", 0)
    for mode, r in results.items():
        if mode == "baseline_a":
            r["token_reduction"] = "기준"
            r["llm_reduction"]   = "기준"
        elif base_tokens > 0:
            saved = base_tokens - r["total_tokens"]
            r["token_reduction"] = f"{saved / base_tokens:.1%} ↓"
            if base_calls > 0:
                call_saved = base_calls - r["llm_calls"]
                r["llm_reduction"] = f"{call_saved / base_calls:.1%} ↓"
            else:
                r["llm_reduction"] = "N/A"
        else:
            r["token_reduction"] = "N/A"
            r["llm_reduction"]   = "N/A"

    fields = [
        "total", "llm_calls", "llm_rate", "llm_reduction",
        "prompt_tokens", "completion_tokens", "total_tokens", "token_reduction",
        "avg_latency_ms", "cache_hits", "cache_rate",
    ]

    print_table("LLM 효율 비교 (baseline_a 기준)", results, modes, fields)

    # CSV 저장
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["mode"] + fields
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for mode in modes:
            w.writerow({"mode": mode, **results[mode]})
    print(f"\n결과 저장: {args.out}")


if __name__ == "__main__":
    main()
