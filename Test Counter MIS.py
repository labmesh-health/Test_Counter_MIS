import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from io import BytesIO
import altair as alt

st.set_page_config(page_title="LAB MIS Full Debug", layout="wide")
st.title("LAB MIS – Full Counter Parsing Debug")

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

# ---------- TEST COUNTER ----------
def parse_test_counter(pdf_bytes: bytes) -> pd.DataFrame:
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
                        if not data_line or data_line.lower().startswith(
                            ("total", "unit:", "system:")
                        ):
                            break

                        parts = re.split(r"\s+", data_line)
                        if len(parts) < 8:
                            continue

                        nums = parts[-6:]
                        acn = parts[-7]
                        test_name = " ".join(parts[:-7]).strip()
                        if not test_name:
                            continue

                        rows.append(
                            {
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
                        )

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Routine", "Rerun", "STAT", "Calibrator", "QC", "Total Count"]:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            )
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# ---------- SAMPLE COUNTER ----------
def parse_sample_counter(pdf_bytes: bytes) -> pd.DataFrame:
    header_line = "Unit: Routine Rerun STAT Total Count"
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            date = extract_date_from_text(text)
            lines = text.split("\n")

            for i, line in enumerate(lines):
                if line.strip() == header_line:
                    for data_line in lines[i + 1:]:
                        dl = data_line.strip()
                        if (
                            not dl
                            or dl.lower().startswith(
                                (
                                    "total count",
                                    "measuring cells counter",
                                    "system:",
                                    "unit:",
                                )
                            )
                        ):
                            break
                        parts = re.split(r"\s+", dl)
                        if len(parts) < 5:
                            continue
                        unit = parts[0]
                        routine = parts[1]
                        rerun = parts[2]
                        stat = parts[3]
                        total = parts[4]
                        rows.append(
                            {
                                "Unit": unit,
                                "Routine": routine,
                                "Rerun": rerun,
                                "STAT": stat,
                                "Total Count": total,
                                "Date": date,
                            }
                        )

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Routine", "Rerun", "STAT", "Total Count"]:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            )
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# ---------- MEASURING CELLS COUNTER ----------
def parse_mc_counter(pdf_bytes: bytes) -> pd.DataFrame:
    header_line = "Unit: MC Serial No. Last Reset Count after Reset Total Count"
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            date = extract_date_from_text(text)
            lines = text.split("\n")

            for i, line in enumerate(lines):
                if line.strip() == header_line:
                    for data_line in lines[i + 1:]:
                        dl = data_line.strip()
                        if (
                            not dl
                            or dl.lower().startswith(
                                (
                                    "electrodes counter",
                                    "system:",
                                    "unit:",
                                    "total",
                                )
                            )
                        ):
                            break
                        parts = re.split(r"\s+", dl)
                        # pattern: e8-2-1 01/01/1900 00:00:00 4032 4032
                        if len(parts) < 5:
                            continue
                        unit = parts[0]
                        last_reset = parts[1] + " " + parts[2]
                        count_after = parts[3]
                        total = parts[4]
                        rows.append(
                            {
                                "Unit": unit,
                                "MC Serial No.": "",
                                "Last Reset": last_reset,
                                "Count after Reset": count_after,
                                "Total Count": total,
                                "Date": date,
                            }
                        )

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in ["Count after Reset", "Total Count"]:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            )
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# ---------- ELECTRODES COUNTER ----------
def parse_electrode_counter(pdf_bytes: bytes) -> pd.DataFrame:
    header_line = "Electrode Total Count"
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            date = extract_date_from_text(text)
            lines = text.split("\n")
            current_unit = None

            for i, line in enumerate(lines):
                if line.strip().startswith("Unit:"):
                    parts = re.split(r"\s+", line.strip())
                    if len(parts) >= 2:
                        current_unit = parts[-1]

                if line.strip() == header_line:
                    for data_line in lines[i + 1:]:
                        dl = data_line.strip()
                        if not dl or dl.lower().startswith(
                            ("system:", "total", "unit:")
                        ):
                            break
                        parts = re.split(r"\s+", dl)
                        if len(parts) < 2:
                            continue
                        electrode = " ".join(parts[:-1])
                        total = parts[-1]
                        rows.append(
                            {
                                "Unit": current_unit,
                                "Electrode": electrode,
                                "Total Count": total,
                                "Date": date,
                            }
                        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Total Count"] = (
            pd.to_numeric(df["Total Count"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# ---------- UI ----------
uploaded_file = st.sidebar.file_uploader(
    "Upload Detailed Test Counter PDF", type=["pdf"]
)

if uploaded_file:
    pdf_bytes = uploaded_file.read()

    with st.spinner("Parsing Test Counter..."):
        test_df = parse_test_counter(pdf_bytes)
    with st.spinner("Parsing Sample Counter..."):
        sample_df = parse_sample_counter(pdf_bytes)
    with st.spinner("Parsing Measuring Cells Counter..."):
        mc_df = parse_mc_counter(pdf_bytes)
    with st.spinner("Parsing Electrodes Counter..."):
        electrode_df = parse_electrode_counter(pdf_bytes)

    tabs = st.tabs(
        [
            "Test Counter",
            "Sample Counter",
            "Measuring Cells Counter",
            "Electrodes Counter",
        ]
    )

    # --- Tab 1: Test Counter ---
    with tabs[0]:
        st.subheader("Test Counter Data (raw)")
        st.write(test_df)

        if not test_df.empty:
            st.subheader("Total Count by Test")
            chart_test = (
                alt.Chart(test_df)
                .mark_bar()
                .encode(
                    x=alt.X("Test:N", sort="-y"),
                    y=alt.Y("Total Count:Q"),
                    tooltip=["Test", "Total Count"],
                )
                .properties(height=400)
            )
            st.altair_chart(chart_test, use_container_width=True)

    # --- Tab 2: Sample Counter ---
    with tabs[1]:
        st.subheader("Sample Counter Data (raw)")
        st.write(sample_df)

        if not sample_df.empty:
            st.subheader("Sample Total Count by Unit")

            base_sample = (
                alt.Chart(sample_df)
                .mark_bar()
                .encode(
                    x=alt.X("Unit:N", title="Unit"),
                    y=alt.Y("Total Count:Q", title="Total Count"),
                    color=alt.Color("Unit:N", legend=None),
                    tooltip=["Unit", "Total Count"],
                )
            )

            labels_sample = base_sample.mark_text(dy=-5, color="black").encode(
                text="Total Count:Q"
            )

            st.altair_chart(
                (base_sample + labels_sample).properties(height=400),
                use_container_width=True,
            )

    # --- Tab 3: Measuring Cells Counter ---
    with tabs[2]:
        st.subheader("Measuring Cells Counter Data (raw)")
        st.write(mc_df)

        if not mc_df.empty:
            st.subheader("MC Total Count by Unit")

            base_mc = (
                alt.Chart(mc_df)
                .mark_bar()
                .encode(
                    x=alt.X("Unit:N", title="Unit"),
                    y=alt.Y("Total Count:Q", title="Total Count"),
                    color=alt.Color("Unit:N", legend=None),
                    tooltip=["Unit", "Total Count", "Last Reset"],
                )
            )

            labels_mc = base_mc.mark_text(dy=-5, color="black").encode(
                text="Total Count:Q"
            )

            st.altair_chart(
                (base_mc + labels_mc).properties(height=400),
                use_container_width=True,
            )

    # --- Tab 4: Electrodes (table only for now) ---
    with tabs[3]:
        st.subheader("Electrodes Counter Data (raw)")
        st.write(electrode_df)

else:
    st.info("Upload the Detailed Test Counter PDF to see parsed tables.")
