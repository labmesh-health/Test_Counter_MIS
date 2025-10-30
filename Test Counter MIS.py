import streamlit as st
import pandas as pd
import pdfplumber
import re
from datetime import datetime
from io import BytesIO
import altair as alt

# Styling and page setup
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

def extract_date_from_text(text):
    # Attempts to extract the first date/time in the first few lines of the PDF text
    for line in text.split('\n')[:6]:
        match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})', line)
        if match:
            date_str, time_str = match.groups()
            try:
                return datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            except:
                continue
    return None

def parse_test_counter(pdf_bytes):
    headers = ["Test", "ACN", "Routine", "Rerun", "STAT", "Calibrator", "QC", "Total Count"]
    pattern = r"Test\s+ACN\s+Routine\s+Rerun\s+STAT\s+Calibrator\s+QC\s+Total\s+Count"
    rows = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            date = extract_date_from_text(text)
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if re.search(pattern, line, re.IGNORECASE):
                    for data_line in lines[i+1:]:
                        data_line = data_line.strip()
                        if not data_line or data_line.lower().startswith(("total", "unit:", "system:")):
                            break
                        match = re.match(r'^(.*?)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$', data_line)
                        if match:
                            row_vals = list(match.groups())
                            row_dict = dict(zip(headers, row_vals))
                            row_dict["Date"] = date
                            rows.append(row_dict)
    df = pd.DataFrame(rows)
    if not df.empty:
        for col in headers[2:]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["Date"] = pd.to_datetime(df["Date"])
    return df

st.title("LAB MIS Instrument Test Counter Difference Calculator")

uploaded_file_1 = st.sidebar.file_uploader("Upload yesterdays PDF report", type=["pdf"], key="file1")
uploaded_file_2 = st.sidebar.file_uploader("Upload todays PDF report", type=["pdf"], key="file2")

if uploaded_file_1 and uploaded_file_2:
    pdf_bytes1 = uploaded_file_1.read()
    pdf_bytes2 = uploaded_file_2.read()
    with st.spinner("Extracting Test Counter from first PDF..."):
        df1 = parse_test_counter(pdf_bytes1)
    with st.spinner("Extracting Test Counter from second PDF..."):
        df2 = parse_test_counter(pdf_bytes2)

    if df1.empty or df2.empty:
        st.error("Test Counter data could not be found in one or both PDFs.")
    else:
        date1 = df1["Date"].min()
        date2 = df2["Date"].min()
        if date1 is None or date2 is None:
            st.error("Unable to extract dates from the PDFs for comparison.")
        else:
            if date1 > date2:
                df_newer, df_older = df1, df2
                new_date, old_date = date1, date2
            else:
                df_newer, df_older = df2, df1
                new_date, old_date = date2, date1

            merged_df = pd.merge(df_newer, df_older, on="Test", suffixes=('_newer', '_older'))

            diff_cols = ["Routine", "Rerun", "STAT", "Calibrator", "QC", "Total Count"]
            for col in diff_cols:
                merged_df[f"{col}_diff"] = merged_df[f"{col}_newer"] - merged_df[f"{col}_older"]

            st.header(f"Test Counter Differences: {new_date.date()} minus {old_date.date()}")
            diff_display_cols = ["Test"] + [f"{col}_diff" for col in diff_cols]
            st.dataframe(merged_df[diff_display_cols])

            # Visualization of Total Count differences
            base = alt.Chart(merged_df).mark_bar().encode(
                x="Test:N",
                y="Total Count_diff:Q",
                color=alt.condition(
                    alt.datum["Total Count_diff"] > 0,
                    alt.value("green"),
                    alt.value("red")
                ),
                tooltip=["Test", "Total Count_diff"]
            )
            st.altair_chart(base, use_container_width=True)

else:
    st.info("Please upload two PDF files in the sidebar to compare their test counters.")

