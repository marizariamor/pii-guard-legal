"""Детекторы персональных данных (ПДн) для русскоязычных юридических документов.

Каждый детектор принимает текст и возвращает список найденных сущностей.
Числовые ПДн проверяются контрольной суммой, чтобы не путать их с суммами,
номерами договоров и статьями законов.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    type: str   # FIO, PHONE, EMAIL, PASSPORT, INN, SNILS, CARD, ACCOUNT, ADDRESS
    start: int
    end: int
    value: str
    key: str    # нормализованный ключ: одна сущность в разных формах -> один ключ


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


# ---------------------------------------------------------------- контрольные суммы

def inn_is_valid(inn: str) -> bool:
    d = [int(c) for c in inn]
    if len(d) == 10:
        w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        return sum(a * b for a, b in zip(w, d)) % 11 % 10 == d[9]
    if len(d) == 12:
        w11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        w12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        c11 = sum(a * b for a, b in zip(w11, d)) % 11 % 10
        c12 = sum(a * b for a, b in zip(w12, d)) % 11 % 10
        return c11 == d[10] and c12 == d[11]
    return False


def snils_is_valid(snils: str) -> bool:
    d = _digits(snils)
    if len(d) != 11:
        return False
    total = sum(int(c) * (9 - i) for i, c in enumerate(d[:9]))
    if total < 100:
        control = total
    elif total in (100, 101):
        control = 0
    else:
        control = total % 101
        if control == 100:
            control = 0
    return control == int(d[9:])


def luhn_is_valid(number: str) -> bool:
    d = [int(c) for c in _digits(number)]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(d)):
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# ---------------------------------------------------------------- детекторы

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<![\d+])(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")
_PASSPORT = re.compile(r"(?<!\d)\d{2}\s?\d{2}\s?(?:(?:№|номер)\s?)?\d{6}(?!\d)")
_PASSPORT_CONTEXT = re.compile(r"паспорт|серия", re.IGNORECASE)
_SNILS = re.compile(r"(?<!\d)\d{3}-\d{3}-\d{3}[\s-]\d{2}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d{4}[\s-]?){3}\d{1,7}(?!\d)")
_ACCOUNT = re.compile(r"(?<!\d)\d{20}(?!\d)")
_INN = re.compile(r"(?<!\d)(?:\d{12}|\d{10})(?!\d)")

_STREET = r"(?:ул\.|улица|пр-т|просп\.|проспект|пер\.|переулок|ш\.|шоссе|наб\.|набережная|б-р|бульвар|пл\.|площадь|мкр\.)"
_ADDRESS = re.compile(
    r"(?:(?:г\.|город)\s*[А-ЯЁ][а-яё]+(?:-[А-ЯЁа-яё][а-яё]+)*(?:\s[А-ЯЁ][а-яё]+)?,\s*)?"
    + _STREET
    + r"\s*[А-ЯЁ0-9][А-Яа-яЁё0-9\-\.\s]*?,\s*(?:д\.|дом)\s*\d+[а-яА-Я]?(?:/\d+)?"
    r"(?:,\s*(?:корп\.|к\.|стр\.)\s*\d+)?(?:,\s*(?:кв\.|квартира|оф\.|офис)\s*\d+)?"
)

_CAP = r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?"
_PATRONYMIC = r"[А-ЯЁ][а-яё]+(?:ович|евич|ич|овн|евн|ичн|инична|ична)(?:а|у|ем|е|ы|ой|ою)?"
_FIO_FULL = re.compile(rf"\b({_CAP})\s+({_CAP})\s+({_PATRONYMIC})\b")             # Фамилия Имя Отчество
_FIO_FULL_REV = re.compile(rf"\b({_CAP})\s+({_PATRONYMIC})\s+({_CAP})\b")         # Имя Отчество Фамилия
_FIO_INITIALS = re.compile(rf"\b({_CAP})\s+([А-ЯЁ])\.\s?([А-ЯЁ])\.")              # Фамилия И.О.
_FIO_INITIALS_REV = re.compile(rf"(?<![А-Яа-яЁё])([А-ЯЁ])\.\s?([А-ЯЁ])\.\s?({_CAP})\b")  # И.О. Фамилия

_SURNAME_STEM_LEN = 5


def _fio_key(surname: str, name_initial: str, patronymic_initial: str) -> str:
    """Один человек в разных падежах и формах -> один ключ."""
    return f"{surname[:_SURNAME_STEM_LEN].lower()}|{name_initial.upper()}|{patronymic_initial.upper()}"


def detect_fio(text: str) -> list[Entity]:
    found: list[Entity] = []
    for m in _FIO_FULL.finditer(text):
        s, n, p = m.groups()
        found.append(Entity("FIO", m.start(), m.end(), m.group(), _fio_key(s, n[0], p[0])))
    for m in _FIO_FULL_REV.finditer(text):
        n, p, s = m.groups()
        found.append(Entity("FIO", m.start(), m.end(), m.group(), _fio_key(s, n[0], p[0])))
    for m in _FIO_INITIALS.finditer(text):
        s, n, p = m.groups()
        found.append(Entity("FIO", m.start(), m.end(), m.group(), _fio_key(s, n, p)))
    for m in _FIO_INITIALS_REV.finditer(text):
        n, p, s = m.groups()
        found.append(Entity("FIO", m.start(), m.end(), m.group(), _fio_key(s, n, p)))
    return found


def _simple(pattern: re.Pattern, etype: str, text: str, check=None) -> list[Entity]:
    out = []
    for m in pattern.finditer(text):
        value = m.group()
        if check and not check(value):
            continue
        out.append(Entity(etype, m.start(), m.end(), value, _digits(value) or value.lower()))
    return out


def detect_email(text: str) -> list[Entity]:
    return _simple(_EMAIL, "EMAIL", text)


def detect_phone(text: str) -> list[Entity]:
    out = []
    for e in _simple(_PHONE, "PHONE", text):
        key = "7" + e.key[1:]  # 8XXX и +7XXX — один номер
        out.append(Entity(e.type, e.start, e.end, e.value, key))
    return out


def detect_passport(text: str) -> list[Entity]:
    out = []
    for m in _PASSPORT.finditer(text):
        window = text[max(0, m.start() - 40):m.start()]
        if not _PASSPORT_CONTEXT.search(window):
            continue
        out.append(Entity("PASSPORT", m.start(), m.end(), m.group(), _digits(m.group())))
    return out


def detect_snils(text: str) -> list[Entity]:
    return _simple(_SNILS, "SNILS", text, snils_is_valid)


def detect_card(text: str) -> list[Entity]:
    return _simple(_CARD, "CARD", text, luhn_is_valid)


def detect_account(text: str) -> list[Entity]:
    return _simple(_ACCOUNT, "ACCOUNT", text)


def detect_inn(text: str) -> list[Entity]:
    return _simple(_INN, "INN", text, inn_is_valid)


def detect_address(text: str) -> list[Entity]:
    return [Entity("ADDRESS", m.start(), m.end(), m.group(), m.group().lower()) for m in _ADDRESS.finditer(text)]


DETECTORS = [
    detect_email,
    detect_phone,
    detect_snils,
    detect_passport,
    detect_account,
    detect_card,
    detect_inn,
    detect_address,
    detect_fio,
]

# При пересечении сущностей выигрывает более длинная, при равной длине — с большим приоритетом.
_PRIORITY = {"EMAIL": 9, "SNILS": 8, "PASSPORT": 7, "ACCOUNT": 6, "CARD": 5, "INN": 4, "PHONE": 3, "ADDRESS": 2, "FIO": 1}


def detect_all(text: str) -> list[Entity]:
    """Все ПДн в тексте без пересечений, отсортированные по позиции."""
    candidates = [e for detector in DETECTORS for e in detector(text)]
    candidates.sort(key=lambda e: (-(e.end - e.start), -_PRIORITY[e.type], e.start))
    chosen: list[Entity] = []
    for e in candidates:
        if all(e.end <= c.start or e.start >= c.end for c in chosen):
            chosen.append(e)
    return sorted(chosen, key=lambda e: e.start)
