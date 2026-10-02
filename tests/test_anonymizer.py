import pytest

from pii_guard.anonymizer import PIILeakError, anonymize, deanonymize, find_leaks, safe_prompt

DOC = (
    "Я, Смирнов Алексей Викторович, тел. +7 (916) 245-37-81, прошу вернуть деньги. "
    "Подпись: Смирнов А.В. Почта a.smirnov.test@mail.ru"
)


def test_masks_all_pii():
    result = anonymize(DOC)
    assert "Смирнов" not in result.text
    assert "245-37-81" not in result.text
    assert "a.smirnov.test@mail.ru" not in result.text
    assert find_leaks(result.text) == []


def test_same_person_gets_same_label():
    result = anonymize(DOC)
    assert result.text.count("[ФИО_1]") == 2
    assert "[ФИО_2]" not in result.text


def test_mapping_keeps_full_form():
    result = anonymize(DOC)
    assert result.mapping["[ФИО_1]"] == "Смирнов Алексей Викторович"


def test_deanonymize_llm_answer():
    result = anonymize(DOC)
    llm_answer = "Уважаемый [ФИО_1]! Мы свяжемся с вами по номеру [ТЕЛЕФОН_1]."
    restored = deanonymize(llm_answer, result.mapping)
    assert restored == "Уважаемый Смирнов Алексей Викторович! Мы свяжемся с вами по номеру +7 (916) 245-37-81."


def test_roundtrip_when_single_form():
    text = "Клиент Орлова Татьяна Михайловна, ИНН 0830166130, тел. +7-937-215-60-08."
    result = anonymize(text)
    assert deanonymize(result.text, result.mapping) == text


def test_prefers_nominative_form_for_substitution():
    text = "Директору от Смирнова Алексея Викторовича. Я, Смирнов Алексей Викторович, прошу. Смирнов А.В."
    result = anonymize(text)
    assert result.mapping["[ФИО_1]"] == "Смирнов Алексей Викторович"


def test_unknown_labels_untouched():
    assert deanonymize("[ФИО_9] и [ТЕЛЕФОН_3]", {}) == "[ФИО_9] и [ТЕЛЕФОН_3]"


def test_safe_prompt_ok():
    assert safe_prompt(DOC).text.startswith("Я, [ФИО_1]")


def test_safe_prompt_blocks_leaks(monkeypatch):
    import pii_guard.anonymizer as mod

    monkeypatch.setattr(mod, "anonymize", lambda t: mod.AnonymizationResult(t, {}, []))
    with pytest.raises(PIILeakError):
        mod.safe_prompt(DOC)


def test_stats():
    assert anonymize(DOC).stats() == {"ФИО": 1, "ТЕЛЕФОН": 1, "EMAIL": 1}
