import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="LAB MIS Debug", layout="wide")

# ---------- helpers ----------
def extract_date_from_text(text: str):
    for line in text.split("\n")[:6]:
        match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})", line)
        if match:
            date_str, time_str = match.groups()
            try:
                return datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            except Exception:
                continue
    return None

# === WORKING TEST COUNTER PARSER (FROM YOUR OTHER TOOL) ===
def parse_test_counter(pdf_bytes: bytes) -> pd.DataFrame:
    headers = ["Test", "ACN", "Routine", "Rerun", "STAT", "Calibrator", "QC", "Total Count"]
    header_pattern = r"Test\s+ACN.*Total\s*Count"
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            date = extract_date_from_text(text)
            lines = text.split("\n")

            for i, line in enumerate(lines):
                if re.search(header_pattern, line, re.IGNORECASE):
                    for data_line in lines[i + 1:]:
                        data_line = data_line.strip()
                        if not data_line or data_line.lower().startswith(("total", "unit:", "system:")):
                            break

                        parts = re.split(r"\s+", data_line)
                        if len(parts) < 8:
                            continue

                        nums = parts[-6:]
                        acn = parts[-7]
                        test_name = " ".join(parts[:-7]).strip()
                        if not test_name:
                            continue

                        row = {
                            "Test": test_name,
                            "ACN": acn,
                            "Routine": nums[0],
                            "Rerun": nums[1],
                            "STAT": nums[2],
                            "Calibrator": nums[3],
                            "QC": nums[4],
                            "Total Count": nums[5],
                            "Date": date,
                        }
                        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Routine", "Rerun", "STAT", "Calibrator", "QC", "Total Count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# === SAMPLE COUNTER PARSER (NEW, MATCHES SAME PDF) ===
def parse_sample_counter(pdf_bytes: bytes) -> pd.DataFrame:
    header_pattern = r"Unit:?\s+Routine\s+Rerun\s+STAT\s+Total\s*Count"
    headers = ["Unit", "Routine", "Rerun", "STAT", "Total Count"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            date = extract_date_from_text(text)
            lines = text.split("\n")

            for i, line in enumerate(lines):
                if re.search(header_pattern, line, re.IGNORECASE):
                    for data_line in lines[i + 1:]:
                        data_line = data_line.strip()
                        if not data_line or data_line.lower().startswith(("total", "unit:", "system:")):
                            break

                        parts = re.split(r"\s+", data_line)
                        if len(parts) < 5:
                            continue

                        nums = parts[-4:]
                        unit_name = " ".join(parts[:-4]).strip()
                        if not unit_name:
                            continue

                        row = {
                            "Unit": unit_name,
                            "Routine": nums[0],
                            "Rerun": nums[1],
                            "STAT": nums[2],
                            "Total Count": nums[3],
                            "Date": date,
                        }
                        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Routine", "Rerun", "STAT", "Total Count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# === MEASURING CELLS COUNTER PARSER (NEW) ===
def parse_mc_counter(pdf_bytes: bytes) -> pd.DataFrame:
    header_pattern = (
        r"Unit:?\s+Count\s+after\s+Reset\s+Total\s+Count\s+MC\s+Serial\s+No\.\s+Last\s+Reset"
    )
    headers = ["Unit", "Count after Reset", "Total Count", "MC Serial No.", "Last Reset"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            date = extract_date_from_text(text)
            lines = text.split("\n")

            for i, line in enumerate(lines):
                if re.search(header_pattern, line, re.IGNORECASE):
                    for data_line in lines[i + 1:]:
                        data_line = data_line.strip()
                        if (not data_line or
                            data_line.lower().startswith(("electrodes", "unit:", "system:", "total"))):
                            break

                        parts = re.split(r"\s+", data_line)
                        if len(parts) < 4:
                            continue

                        unit = parts[0]
                        nums = []
                        idx = 1
                        while idx < len(parts) and len(nums) < 2:
                            if re.fullmatch(r"[+-]?\d+", parts[idx]):
                                nums.append(parts[idx])
                            else:
                                break
                            idx += 1
                        if len(nums) < 2 or idx >= len(parts):
                            continue

                        mc_serial = parts[idx]
                        last_reset = " ".join(parts[idx + 1:]).strip()

                        row = {
                            "Unit": unit,
                            "Count after Reset": nums[0],
                            "Total Count": nums[1],
                            "MC Serial No.": mc_serial,
                            "Last Reset": last_reset,
                            "Date": date,
                        }
                        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Count after Reset", "Total Count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# ---------- SIMPLE DEBUG UI (tables only) ----------
st.title("LAB MIS – Parsing Debug View")

uploaded_file = st.sidebar.file_uploader("Upload Detailed Test Counter PDF", type=["pdf"])

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    with st.spinner("Parsing Test Counter..."):
        test_df = parse_test_counter(pdf_bytes)
    with st.spinner("Parsing Sample Counter..."):
        sample_df = parse_sample_counter(pdf_bytes)
    with st.spinner("Parsing Measuring Cells Counter..."):
        mc_df = parse_mc_counter(pdf_bytes)

    st.subheader("Test Counter Data (raw)")
    st.write(test_df.head(20))

    st.subheader("Sample Counter Data (raw)")
    st.write(sample_df.head(20))

    st.subheader("Measuring Cells Counter Data (raw)")
    st.write(mc_df.head(20))
else:
    st.info("Upload a Detailed Test Counter PDF to see parsed tables.")
