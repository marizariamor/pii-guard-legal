"""Eval-гейт: проверка качества обезличивания на эталонных документах.

Запуск: python evals/run_eval.py
Код возврата 1, если нарушен хотя бы один порог — CI блокирует изменение.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from pii_guard import anonymize, detect_all, find_leaks  # noqa: E402

MAX_LEAKS = 0
MIN_RECALL = 0.95
MAX_FALSE_POSITIVES = 0


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    total, detected, leaks, wrong_type = 0, 0, [], []
    per_type: dict[str, list[int]] = {}

    for doc in sorted((ROOT / "golden").glob("*.txt")):
        text = doc.read_text(encoding="utf-8")
        expected = json.loads(doc.with_suffix(".json").read_text(encoding="utf-8"))
        result = anonymize(text)
        entities = result.entities

        for item in expected:
            total += 1
            stats = per_type.setdefault(item["type"], [0, 0])
            stats[1] += 1
            covering = [e for e in entities if item["value"] in e.value or e.value in item["value"] and len(e.value) >= len(item["value"]) * 0.8]
            if covering:
                detected += 1
                stats[0] += 1
                if all(e.type != item["type"] for e in covering):
                    wrong_type.append((doc.name, item))
            if item["value"] in result.text:
                leaks.append((doc.name, item))

        for leftover in find_leaks(result.text):
            leaks.append((doc.name, {"type": leftover.type, "value": leftover.value}))

    false_positives = []
    for doc in sorted((ROOT / "clean").glob("*.txt")):
        for e in detect_all(doc.read_text(encoding="utf-8")):
            false_positives.append((doc.name, e.type, e.value))

    recall = detected / total if total else 1.0

    print("=== PII Guard eval ===")
    print(f"Документов с ПДн: {len(list((ROOT / 'golden').glob('*.txt')))} · ПДн в эталоне: {total}")
    print(f"Полнота обнаружения: {recall:.1%} (порог ≥ {MIN_RECALL:.0%})")
    for t, (ok, n) in sorted(per_type.items()):
        print(f"  {t:<9} {ok}/{n}")
    print(f"Утечки ПДн: {len(leaks)} (порог {MAX_LEAKS})")
    for name, item in leaks:
        print(f"  ✗ {name}: {item['type']} «{item['value']}»")
    print(f"Ложные срабатывания на чистых документах: {len(false_positives)} (порог {MAX_FALSE_POSITIVES})")
    for name, t, v in false_positives:
        print(f"  ✗ {name}: {t} «{v}»")
    if wrong_type:
        print(f"Предупреждение: найдено, но с другим типом: {len(wrong_type)}")
        for name, item in wrong_type:
            print(f"  ~ {name}: ожидали {item['type']} «{item['value']}»")

    failed = len(leaks) > MAX_LEAKS or recall < MIN_RECALL or len(false_positives) > MAX_FALSE_POSITIVES
    print("РЕЗУЛЬТАТ:", "❌ FAIL — изменение блокируется" if failed else "✅ PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
