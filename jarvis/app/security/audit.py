"""Cryptographically-chained Immutable Security Audit Ledger (Spec §63).

Maintains a tamper-evident SHA-256 chained hash log of all critical security events,
tool runs, threat blocks, and permission grants.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

from app.core.logging import get_logger
from app.utils.paths import get_paths

log = get_logger("security.audit")


class AuditLedger:
    def __init__(self, ledger_path: Optional[Path] = None) -> None:
        self.ledger_path = ledger_path or (get_paths().logs / "security_audit.jsonl")
        self._last_hash = self._get_tail_hash()

    def _get_tail_hash(self) -> str:
        """Read the hash of the last entry in the ledger, or return genesis hash."""
        if not self.ledger_path.exists():
            return "0" * 64
        try:
            lines = self.ledger_path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                last_record = json.loads(lines[-1])
                return last_record.get("entry_hash", "0" * 64)
        except Exception:
            pass
        return "0" * 64

    def record_event(self, event_type: str, details: dict[str, Any], status: str = "SUCCESS") -> str:
        """Append a cryptographically signed event to the security audit ledger."""
        timestamp = time.time()
        canonical_details = json.dumps(details, sort_keys=True)

        payload_to_hash = f"{self._last_hash}:{timestamp}:{event_type}:{status}:{canonical_details}"
        entry_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()

        record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "status": status,
            "prev_hash": self._last_hash,
            "entry_hash": entry_hash,
            "details": details,
        }

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        self._last_hash = entry_hash
        log.debug("audit record logged: %s [%s] -> %s", event_type, status, entry_hash[:12])
        return entry_hash

    def verify_ledger_integrity(self) -> tuple[bool, int]:
        """Validate the entire cryptographic hash chain to detect any tampering."""
        if not self.ledger_path.exists():
            return True, 0

        prev_hash = "0" * 64
        count = 0
        try:
            for line_idx, line in enumerate(self.ledger_path.read_text(encoding="utf-8").splitlines()):
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("prev_hash") != prev_hash:
                    log.error("LEDGER INTEGRITY FAILED at line %d: broken prev_hash chain", line_idx)
                    return False, count

                canonical_details = json.dumps(record["details"], sort_keys=True)
                payload = f"{prev_hash}:{record['timestamp']}:{record['event_type']}:{record['status']}:{canonical_details}"
                expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

                if record.get("entry_hash") != expected_hash:
                    log.error("LEDGER INTEGRITY FAILED at line %d: invalid entry_hash", line_idx)
                    return False, count

                prev_hash = expected_hash
                count += 1
            return True, count
        except Exception as exc:
            log.error("error verifying ledger integrity: %s", exc)
            return False, count
