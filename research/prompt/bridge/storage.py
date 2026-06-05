import os
import csv
import json
import datetime
import logging

logger = logging.getLogger(__name__)

class EventStorage:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.csv_file = os.path.join(data_dir, "security_stats.csv")
        self.jsonl_file = os.path.join(data_dir, "falco_events.jsonl")
        
        os.makedirs(data_dir, exist_ok=True)
        self._ensure_csv_header()

    def _ensure_csv_header(self):
        csv_headers = [
            "timestamp", "event_type", "rule_name", "priority",
            "prompt_tokens", "completion_tokens", "latency_ms",
            "remediation_status", "remediation_action", "mitre_technique",
            "target_container", "attack_source", "attack_label",
            "attack_id", "container_id", "container_image", "event_source",
            "experiment_mode", "ground_truth", "rule_matched",
            "llm_called", "cache_hit", "cache_key",
            "gate_decision", "llm_action", "llm_threat_level",
            "cache_ttl",
        ]
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(csv_headers)

    def log_event(self, event_data: dict, csv_row: list):
        # JSONL 기록
        try:
            with open(self.jsonl_file, mode="a", encoding="utf-8") as f:
                f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to JSONL: {e}")

        # CSV 기록
        try:
            with open(self.csv_file, mode='a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(csv_row)
        except Exception as e:
            logger.error(f"Failed to write to CSV: {e}")
