import pytest

from pii_guard.detectors import (
    detect_all,
    detect_card,
    detect_fio,
    detect_inn,
    detect_passport,
    detect_phone,
    detect_snils,
    inn_is_valid,
    luhn_is_valid,
    snils_is_valid,
)


def types(text):
    return [e.type for e in detect_all(text)]


# ---------- контрольные суммы

def test_inn_checksum():
    assert inn_is_valid("5260181598")
    assert inn_is_valid("628194821977")
    assert not inn_is_valid("5260181597")
    assert not inn_is_valid("1234567890")


def test_snils_checksum():
    assert snils_is_valid("911-862-527 06")
    assert not snils_is_valid("911-862-527 07")


def test_luhn():
    assert luhn_is_valid("2200 2917 0342 3664")
    assert not luhn_is_valid("2200 2917 0342 3665")


# ---------- ФИО

@pytest.mark.parametrize("text", [
    "Иванов Иван Иванович",
    "от Смирнова Алексея Викторовича",
    "Анна Сергеевна Лебедева",
    "Смирнов А.В.",
    "О.П. Кузнецова",
    "Ковалёвой Марины Юрьевны",
])
def test_fio_found(text):
    assert detect_fio(text), text


def test_fio_same_person_same_key():
    full = detect_fio("Смирнова Алексея Викторовича")[0]
    short = detect_fio("Смирнов А.В.")[0]
    assert full.key == short.key


def test_fio_not_in_plain_text():
    assert detect_fio("Прошу Вас Рассмотреть претензию в установленный законом срок") == []


# ---------- телефоны

@pytest.mark.parametrize("text", ["+7 (916) 245-37-81", "8 903 512 44 09", "+79274418820", "8-912-604-71-23"])
def test_phone_formats(text):
    assert detect_phone(text)


def test_phone_8_and_plus7_same_key():
    assert detect_phone("89991204400")[0].key == detect_phone("+7 999 120-44-00")[0].key


# ---------- документы

def test_passport_needs_context():
    assert detect_passport("паспорт серия 45 18 № 734521")
    assert detect_passport("Номер заказа 4518 734521") == []


def test_snils_and_inn_and_card():
    assert detect_snils("СНИЛС 911-862-527 06")
    assert detect_inn("ИНН 628194821977")
    assert detect_card("карта 2200 2917 0342 3664")


# ---------- ложные срабатывания

@pytest.mark.parametrize("text", [
    "Стоимость товара 45 990 рублей, чек № 0042317",
    "Статья 18 Закона № 2300-1 от 07.02.1992",
    "Дело № А40-123456/2026",
    "Номер заказа в системе: 1000234567891",
    "Итого: 40 500 рублей до 31.12.2026",
])
def test_no_false_positives(text):
    assert types(text) == [], text


def test_address():
    found = detect_all("проживает: г. Казань, ул. Баумана, д. 17, кв. 5, телефон")
    assert [e.type for e in found] == ["ADDRESS"]
