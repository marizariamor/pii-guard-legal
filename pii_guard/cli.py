"""Командная строка: python -m pii_guard документ.txt"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .anonymizer import find_leaks, anonymize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Обезличивание ПДн в документе перед отправкой в LLM")
    parser.add_argument("file", help="путь к .txt файлу (или '-' для stdin)")
    parser.add_argument("--mapping", help="сохранить таблицу соответствий в JSON (хранить локально!)")
    args = parser.parse_args(argv)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    result = anonymize(text)
    print(result.text)

    leaks = find_leaks(result.text)
    print(f"\n--- найдено ПДн: {result.stats()} | утечек после обезличивания: {len(leaks)}", file=sys.stderr)

    if args.mapping:
        Path(args.mapping).write_text(json.dumps(result.mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
