import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from io import BytesIO
import altair as alt

# ---------- Styling ----------
STYLE = """
<style>
.rounded-box {
    padding: 15px;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    background-color: #fbfbfb;
}
</style>
"""
st.set_page_config(page_title="LAB MIS Dashboard", layout="wide")
st.markdown(STYLE, unsafe_allow_html=True)

# ---------- Shared helpers ----------
def extract_date_from_text(text):
    for line in text.split('\n')[:6]:
        m = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})', line)
        if m:
            d, t = m.groups()
            try:
                return datetime.strptime(f"{d} {t}", "%d/%m/%Y %H:%M")
            except Exception:
                continue
    return None

def _split_head_text_numeric(line):
    """Return (text_part, numeric_tokens_list) from a data line."""
    tokens = re.split(r"\s+", line.strip())
    num_start = None
    for idx, tok in enumerate(tokens):
        if re.fullmatch(r"[+-]?\d+", tok):
            num_start = idx
            break
    if num_start is None:
        return None, []
    text_part = " ".join(tokens[:num_start]).strip()
    nums = tokens[num_start:]
    return text_part, nums

# ---------- Test Counter (fixed header text, flexible spaces) ----------
def parse_test_counter(pdf_bytes):
    header_re = re.compile(
        r"^Test\s+ACN\s+Routine\s+Calib\.\s+QC\s+Rerun\s+STAT\s+Total\s+Count\s*$"
    )
    headers = ["Test", "ACN", "Routine", "Calib.", "QC", "Rerun", "STAT", "Total Count"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            date = extract_date_from_text(text)
            for i, line in enumerate(lines):
                if header_re.match(line.strip()):
                    for dl in lines[i+1:]:
                        dl = dl.strip()
                        if not dl or dl.lower().startswith(("total", "unit:", "system:")):
                            break
                        test_name, nums = _split_head_text_numeric(dl)
                        if not test_name or len(nums) < 7:
                            continue
                        nums = nums[:7]
                        row = dict(zip(headers, [test_name] + nums))
                        row["Date"] = date
                        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for c in df.columns:
            if c not in ["Date", "Test"]:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df

# ---------- Sample Counter ----------
def parse_sample_counter(pdf_bytes):
    header_re = re.compile(
        r"^Unit:?\s+Routine\s+Rerun\s+STAT\s+Total\s+Count\s*$",
        re.IGNORECASE,
    )
    headers = ["Unit", "Routine", "Rerun", "STAT", "Total Count"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            date = extract_date_from_text(text)
            for i, line in enumerate(lines):
                if header_re.match(line.strip()):
                    for dl in lines[i+1:]:
                        dl = dl.strip()
                        if not dl or dl.lower().startswith(("total", "unit:", "system:")):
                            break
                        unit_text, nums = _split_head_text_numeric(dl)
                        if not unit_text or len(nums) < 4:
                            continue
                        nums = nums[:4]
                        row = dict(zip(headers, [unit_text] + nums))
                        row["Date"] = date
                        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for c in df.columns:
            if c not in ["Date", "Unit"]:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df

# ---------- Measuring Cells Counter ----------
def parse_mc_counter(pdf_bytes):
    header_re = re.compile(
        r"^Unit:?\s+Count\s+after\s+Reset\s+Total\s+Count\s+MC\s+Serial\s+No\.\s+Last\s+Reset\s*$",
        re.IGNORECASE,
    )
    headers = ["Unit", "Count after Reset", "Total Count", "MC Serial No.", "Last Reset"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            date = extract_date_from_text(text)
            for i, line in enumerate(lines):
                if header_re.match(line.strip()):
                    for dl in lines[i+1:]:
                        dl = dl.strip()
                        if (not dl or
                            dl.lower().startswith(("electrodes", "unit:", "system:", "total"))):
                            break
                        tokens = re.split(r"\s+", dl)
                        if len(tokens) < 4:
                            continue
                        unit = tokens[0]
                        nums = []
                        idx = 1
                        while idx < len(tokens) and len(nums) < 2:
                            if re.fullmatch(r"[+-]?\d+", tokens[idx]):
                                nums.append(tokens[idx])
                            else:
                                break
                            idx += 1
                        if len(nums) < 2 or idx >= len(tokens):
                            continue
                        mc_serial = tokens[idx]
                        last_reset = " ".join(tokens[idx+1:]).strip()
                        row = dict(zip(headers, [unit]
