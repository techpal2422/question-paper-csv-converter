import io, re, zipfile, xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Question Paper → CSV Converter", page_icon="📝", layout="wide")

def read_docx(uploaded):
    with zipfile.ZipFile(io.BytesIO(uploaded.getvalue())) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for p in root.findall(".//w:p", ns):
        parts = []
        for n in p.iter():
            if n.tag == f"{{{ns['w']}}}t" and n.text:
                parts.append(n.text)
            elif n.tag == f"{{{ns['w']}}}tab":
                parts.append(" ")
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs

def parse_questions(paragraphs):
    text = re.sub(r"\s+", " ", " ".join(paragraphs)).strip()
    chunks = [x.strip() for x in re.split(r"(?=\b\d+\.\s*)", text) if re.match(r"^\d+\.\s*", x)]
    rows, warnings = [], []
    for n, chunk in enumerate(chunks, 1):
        chunk = re.sub(r"^\d+\.\s*", "", chunk).strip()
        markers = list(re.finditer(r"\(\s*([a-dA-D])\s*\)", chunk))
        if not markers:
            warnings.append(f"Question {n}: no options detected.")
            rows.append({"question": chunk, "option_1":"","option_2":"","option_3":"","option_4":"","answer":""})
            continue
        question = chunk[:markers[0].start()].strip()
        opts = {}
        for i, m in enumerate(markers):
            end = markers[i+1].start() if i+1 < len(markers) else len(chunk)
            opts[m.group(1).lower()] = chunk[m.end():end].strip()
        answer = ""
        am = re.search(r"(?:answer|ans)\s*[:\-]?\s*\(?([a-dA-D])\)?\s*$", chunk, re.I)
        if am:
            answer = am.group(1).upper()
        if "d" not in opts: warnings.append(f"Question {n}: Option D not detected.")
        if not answer: warnings.append(f"Question {n}: answer not detected.")
        rows.append({"question":question,"option_1":opts.get("a",""),"option_2":opts.get("b",""),
                     "option_3":opts.get("c",""),"option_4":opts.get("d",""),"answer":answer})
    return rows, warnings

st.title("📝 Question Paper → CSV Converter")
st.caption("Convert Microsoft Word multiple-choice questions into a structured CSV file.")

with st.sidebar:
    st.header("Question Settings")
    group = st.text_input("Question Group", "119")
    qtype = st.selectbox("Question Type", ["single_choice","multiple_choice","true_false","short_answer","essay"])
    level = st.selectbox("Question Level", ["easy","medium","hard"])
    marks = st.number_input("Marks", min_value=0, value=1, step=1)

uploaded = st.file_uploader("Upload Microsoft Word document (.docx)", type=["docx"])

if uploaded and st.button("🚀 Convert Questions", type="primary", use_container_width=True):
    try:
        rows, warnings = parse_questions(read_docx(uploaded))
        if not rows:
            st.error("No questions could be detected.")
        else:
            df = pd.DataFrame(rows)
            df.insert(0, "marks", marks)
            df.insert(0, "question_level", level)
            df.insert(0, "question_group", group)
            df.insert(0, "question_type", qtype)
            st.session_state.df = df
            st.session_state.warnings = warnings
            st.session_state.filename = uploaded.name
    except Exception as e:
        st.error(f"Could not process the document: {e}")

if "df" in st.session_state:
    df = st.session_state.df
    warnings = st.session_state.warnings
    st.divider()
    st.subheader(f"Preview — {len(df)} questions detected")
    if warnings:
        with st.expander(f"⚠️ {len(warnings)} validation notices"):
            for w in warnings: st.write("• " + w)
    st.dataframe(df, use_container_width=True, hide_index=True)
    name = re.sub(r"\.docx$", "", st.session_state.filename, flags=re.I) + "_converted.csv"
    st.download_button("⬇️ Download CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=name, mime="text/csv", type="primary", use_container_width=True)
    st.info("Missing options or answers are left blank; the app does not guess them.")
