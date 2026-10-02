"""Обезличивание текста, обратная подстановка и финальная проверка перед отправкой в LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .detectors import Entity, detect_all

LABELS_RU = {
    "FIO": "ФИО",
    "PHONE": "ТЕЛЕФОН",
    "EMAIL": "EMAIL",
    "PASSPORT": "ПАСПОРТ",
    "INN": "ИНН",
    "SNILS": "СНИЛС",
    "CARD": "КАРТА",
    "ACCOUNT": "СЧЁТ",
    "ADDRESS": "АДРЕС",
}

_LABEL_RE = re.compile(r"\[[А-ЯЁA-Z]+_\d+\]")


@dataclass
class AnonymizationResult:
    text: str                                    # обезличенный текст — только он уходит в LLM
    mapping: dict[str, str]                      # метка -> исходное значение (хранится локально)
    entities: list[Entity] = field(default_factory=list)

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for label in self.mapping:
            kind = label.strip("[]").rsplit("_", 1)[0]
            counts[kind] = counts.get(kind, 0) + 1
        return counts


_NOMINATIVE_PATRONYMIC = re.compile(r"(?:ович|евич|ич|овна|евна|ична|инична)\b")


def _canonical_score(entity: Entity) -> tuple[int, int]:
    """Какую форму сущности подставлять обратно: для ФИО — полную в именительном падеже."""
    if entity.type == "FIO":
        nominative = 1 if _NOMINATIVE_PATRONYMIC.search(entity.value) else 0
        full = 1 if "." not in entity.value else 0
        return (full * 2 + nominative, len(entity.value))
    return (0, len(entity.value))


def anonymize(text: str) -> AnonymizationResult:
    """Заменяет ПДн метками вида [ФИО_1]. Одна и та же сущность получает одну метку."""
    entities = detect_all(text)
    key_to_label: dict[tuple[str, str], str] = {}
    counters: dict[str, int] = {}
    mapping: dict[str, str] = {}
    best: dict[str, Entity] = {}

    parts: list[str] = []
    pos = 0
    for e in entities:
        k = (e.type, e.key)
        if k not in key_to_label:
            counters[e.type] = counters.get(e.type, 0) + 1
            label = f"[{LABELS_RU[e.type]}_{counters[e.type]}]"
            key_to_label[k] = label
            best[label] = e
        elif _canonical_score(e) > _canonical_score(best[key_to_label[k]]):
            best[key_to_label[k]] = e
        mapping[key_to_label[k]] = best[key_to_label[k]].value
        parts.append(text[pos:e.start])
        parts.append(key_to_label[k])
        pos = e.end
    parts.append(text[pos:])
    return AnonymizationResult("".join(parts), mapping, entities)


def deanonymize(text: str, mapping: dict[str, str]) -> str:
    """Возвращает исходные значения на место меток (например, в ответе LLM)."""
    return _LABEL_RE.sub(lambda m: mapping.get(m.group(), m.group()), text)


def find_leaks(masked_text: str) -> list[Entity]:
    """Финальная проверка: ПДн, оставшиеся в тексте перед отправкой. Пустой список = можно отправлять."""
    return detect_all(masked_text)


class PIILeakError(RuntimeError):
    pass


def safe_prompt(text: str) -> AnonymizationResult:
    """Обезличивает текст и гарантирует отсутствие утечек; иначе бросает PIILeakError."""
    result = anonymize(text)
    leaks = find_leaks(result.text)
    if leaks:
        raise PIILeakError(f"Найдены необезличенные ПДн: {[(e.type, e.value) for e in leaks]}")
    return result
