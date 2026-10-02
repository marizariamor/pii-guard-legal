"""Веб-демо: streamlit run app.py"""

from pathlib import Path

import streamlit as st

from pii_guard import anonymize, deanonymize, find_leaks

st.set_page_config(page_title="PII Guard Legal", page_icon="🛡️", layout="wide")
st.title("🛡️ PII Guard Legal")
st.caption("Обезличивание персональных данных в юридических документах перед отправкой в LLM. Все данные в примерах синтетические.")

examples = {p.stem: p.read_text(encoding="utf-8") for p in sorted(Path("evals/golden").glob("*.txt"))}
choice = st.selectbox("Пример документа", ["— свой текст —", *examples])
text = st.text_area("Исходный документ", examples.get(choice, ""), height=260)

if text.strip():
    result = anonymize(text)
    leaks = find_leaks(result.text)

    left, right = st.columns(2)
    with left:
        st.subheader("Уходит в LLM")
        st.code(result.text, language=None)
    with right:
        st.subheader("Остаётся локально")
        st.json(result.mapping)

    c1, c2 = st.columns(2)
    c1.metric("Найдено ПДн", sum(result.stats().values()))
    c2.metric("Утечек после обезличивания", len(leaks))
    if leaks:
        st.error("Отправка в модель заблокирована: найдены необезличенные ПДн.")
    else:
        st.success("Текст безопасно отправлять в модель.")

    st.subheader("Обратная подстановка в ответ модели")
    answer = st.text_area("Ответ LLM с метками", "Уважаемый [ФИО_1]! Ваше обращение принято, ответ направим на [EMAIL_1].")
    st.write(deanonymize(answer, result.mapping))
