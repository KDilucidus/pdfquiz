import fitz  # PyMuPDF
import re
import random
import streamlit as st

# === Ligatur-Fix ===
def normalize_ligatures(text):
    return (text.replace("ﬀ", "ff")
                .replace("ﬁ", "fi")
                .replace("ﬂ", "fl")
                .replace("ﬃ", "ffi")
                .replace("ﬄ", "ffl"))

# === PDF-Verarbeitung ===
def extract_questions_with_colors(pdf_file):
    if isinstance(pdf_file, str):
        doc = fitz.open(pdf_file)
    else:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")

    questions = []
    current_question = None
    display_answer_parts = []
    full_answer_parts = []
    collecting_answer = False
    collecting_question = False
    stop_collecting_display = False
    disallowed_color = 7631988
    question_counter = 0

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = normalize_ligatures("".join(s["text"] for s in spans).strip())
                if not line_text:
                    continue

                q_match = re.match(r"^(\d+)\)\s*(.+)", line_text)
                if q_match:
                    stop_collecting_display = False
                    if current_question:
                        if display_answer_parts:
                            current_question["answers"].append({
                                "display_parts": display_answer_parts,
                                "full_parts": full_answer_parts,
                                "correct": any(c != 0 for _, c in display_answer_parts)  # fix
                            })
                        questions.append(current_question)

                    question_counter += 1
                    current_question = {
                        "question": normalize_ligatures(q_match.group(2).strip()),
                        "answers": [],
                        "id": question_counter
                    }
                    display_answer_parts = []
                    full_answer_parts = []
                    collecting_answer = False
                    collecting_question = True
                    continue

                a_match = re.match(r"^([a-zA-Z])\)\s*(.+)", line_text)
                if a_match and current_question:
                    stop_collecting_display = False
                    if display_answer_parts:
                        current_question["answers"].append({
                            "display_parts": display_answer_parts,
                            "full_parts": full_answer_parts,
                            "correct": any(c != 0 for _, c in display_answer_parts)  # fix
                        })
                    display_answer_parts = []
                    full_answer_parts = []
                    for span in spans:
                        text = normalize_ligatures(span["text"].strip())
                        if text and span["color"] != disallowed_color:
                            full_answer_parts.append((text, span["color"]))

                    temp_display_parts = []
                    for text, color in full_answer_parts:
                        if "->" in text or "→" in text:
                            before_arrow = text.split("->")[0].split("→")[0].strip()
                            temp_display_parts.append((before_arrow, color))
                            stop_collecting_display = True
                            break
                        else:
                            temp_display_parts.append((text, color))
                    display_answer_parts = temp_display_parts

                    collecting_answer = True
                    collecting_question = False
                    continue

                if collecting_question and current_question:
                    current_question["question"] += " " + line_text
                elif collecting_answer:
                    for span in spans:
                        text = normalize_ligatures(span["text"].strip())
                        if text and span["color"] != disallowed_color:
                            full_answer_parts.append((text, span["color"]))
                    if not stop_collecting_display:
                        for span in spans:
                            text = normalize_ligatures(span["text"].strip())
                            if "->" in text or "→" in text:
                                before_arrow = text.split("->")[0].split("→")[0].strip()
                                display_answer_parts.append((before_arrow, span["color"]))
                                stop_collecting_display = True
                                break
                            else:
                                display_answer_parts.append((text, span["color"]))

    if current_question:
        if display_answer_parts:
            current_question["answers"].append({
                "display_parts": display_answer_parts,
                "full_parts": full_answer_parts,
                "correct": any(c != 0 for _, c in display_answer_parts)  # fix
            })
        questions.append(current_question)

    random.shuffle(questions)
    return questions

# === Hilfsfunktionen ===
def int_to_rgb(color_int):
    r = (color_int >> 16) & 255
    g = (color_int >> 8) & 255
    b = color_int & 255
    return r, g, b

def int_to_hex(color_int):
    r, g, b = int_to_rgb(color_int)
    return f"#{r:02x}{g:02x}{b:02x}"


# === Streamlit Quiz App ===
def main():
    st.set_page_config(page_title="PDF Quiz", layout="wide")

    st.title("📘 Interaktives PDF-Quiz")
    uploaded_file = st.file_uploader("📄 Wähle eine PDF-Datei", type=["pdf"])
    if uploaded_file is None:
        st.info("⬆️ Bitte lade eine PDF-Datei hoch.")
        return

    if "questions" not in st.session_state:
        st.session_state.questions = extract_questions_with_colors(uploaded_file)
        st.session_state.index = 0
        st.session_state.score = 0
        st.session_state.wrong = 0
        st.session_state.answered = 0
        st.session_state.submitted = False

    questions = st.session_state.questions

    if st.session_state.index >= len(questions):
        st.success(f"🎉 Quiz beendet!\nRichtig: {st.session_state.score}, Falsch: {st.session_state.wrong}")
        if st.button("🔁 Neustart"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
        return

    q = questions[st.session_state.index]
    total = len(questions)
    current = st.session_state.index + 1
    correct = st.session_state.score
    answered = st.session_state.answered

    st.markdown(f"### 🧠 Frage {current} von {total}  |  ✅ {correct} von {answered} richtig beantwortet")
    st.subheader(q["question"])

    selected_options = []
    for i, a in enumerate(q["answers"]):
        answer_text = " ".join(normalize_ligatures(t) for t, _ in a["display_parts"])
        selected = st.checkbox(answer_text, key=f"{st.session_state.index}_{i}")
        selected_options.append((selected, a))

    if st.button("✅ Antwort prüfen"):
        st.session_state.submitted = True

    if st.session_state.submitted:
        selected_set = {tuple(a["display_parts"]) for selected, a in selected_options if selected}
        correct_set = {tuple(a["display_parts"]) for a in q["answers"] if a["correct"]}

        if not st.session_state.get(f"answered_{st.session_state.index}", False):
            st.session_state.answered += 1
            st.session_state[f"answered_{st.session_state.index}"] = True

            if selected_set == correct_set:
                st.success("✅ Richtig!")
                st.session_state.score += 1
            else:
                st.error("❌ Falsch.")
                st.session_state.wrong += 1
        else:
            st.info("✅ Diese Frage wurde bereits bewertet.")

        st.markdown("### 🔍 Lösung:")
        for a in q["answers"]:
            colored_text = " ".join(
                f"<span style='color:{int_to_hex(c)}'>{normalize_ligatures(t)}</span>" for t, c in a["full_parts"]
            )
            st.markdown(f"- {colored_text}", unsafe_allow_html=True)

        if st.button("➡️ Nächste Frage"):
            st.session_state.index += 1
            st.session_state.submitted = False
            st.rerun()

if __name__ == "__main__":
    main()
