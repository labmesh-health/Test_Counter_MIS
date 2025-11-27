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

def line_contains_words_in_order(line, words):
    tokens = re.split(r"\s+", line.strip())
    idx = 0
    for w in words:
        while idx < len(tokens) and tokens[idx] != w:
            idx += 1
        if idx == len(tokens):
            return False
        idx += 1
    return True

# ---------- Test Counter ----------
def parse_test_counter(pdf_bytes):
    headers = ["Test", "ACN", "Routine", "Calib.", "QC", "Rerun", "STAT", "Total Count"]
    header_words = headers
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            date = extract_date_from_text(text)

            for i, line in enumerate(lines):
                if line_contains_words_in_order(line, header_words):
                    for data_line in lines[i+1:]:
                        dl = data_line.strip()
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
        for col in df.columns:
            if col not in ["Date", "Test"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df

# ---------- Sample Counter ----------
def parse_sample_counter(pdf_bytes):
    header_words = ["Unit:", "Routine", "Rerun", "STAT", "Total", "Count"]
    headers = ["Unit", "Routine", "Rerun", "STAT", "Total Count"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            date = extract_date_from_text(text)

            for i, line in enumerate(lines):
                if line_contains_words_in_order(line, header_words):
                    for data_line in lines[i+1:]:
                        dl = data_line.strip()
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
        for col in df.columns:
            if col not in ["Date", "Unit"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df

# ---------- Measuring Cells Counter ----------
def parse_mc_counter(pdf_bytes):
    header_words = ["Unit:", "Count", "after", "Reset", "Total", "Count",
                    "MC", "Serial", "No.", "Last", "Reset"]
    headers = ["Unit", "Count after Reset", "Total Count", "MC Serial No.", "Last Reset"]
    rows = []

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")
            date = extract_date_from_text(text)

            for i, line in enumerate(lines):
                if line_contains_words_in_order(line, header_words):
                    for data_line in lines[i+1:]:
                        dl = data_line.strip()
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
                        row = dict(zip(headers, [unit] + nums + [mc_serial, last_reset]))
                        row["Date"] = date
                        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        for col in df.columns:
            if col not in ["Date", "Unit", "MC Serial No.", "Last Reset"]:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df

# ---------- Streamlit UI ----------
st.title("LAB MIS Instrument Counters")

uploaded_file = st.sidebar.file_uploader("Upload your PDF report", type=["pdf"])
test_df = sample_df = mc_df = pd.DataFrame()

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    with st.spinner("Extracting Test Counter..."):
        test_df = parse_test_counter(pdf_bytes)
    with st.spinner("Extracting Sample Counter..."):
        sample_df = parse_sample_counter(pdf_bytes)
    with st.spinner("Extracting MC Counter..."):
        mc_df = parse_mc_counter(pdf_bytes)

def setup_filters(df, name):
    if df.empty or "Date" not in df.columns or df["Date"].isnull().all():
        st.sidebar.warning(f"No Date data in {name}")
        return None, "All"
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    min_date = df["Date"].min()
    max_date = df["Date"].max()
    date_range = st.sidebar.date_input(f"{name} Date Range",
                                       value=(min_date, max_date),
                                       min_value=min_date, max_value=max_date)
    all_units = sorted(df["Unit"].dropna().unique()) if "Unit" in df.columns else []
    options = ["All"] + all_units if all_units else ["All"]
    selected_unit = st.sidebar.selectbox(f"{name} Unit", options=options, index=0,
                                         key=f"{name.replace(' ', '_')}_unit")
    return date_range, selected_unit

test_date_range, test_unit = setup_filters(test_df, "Test Counter") if not test_df.empty else (None, "All")
sample_date_range, sample_unit = setup_filters(sample_df, "Sample Counter") if not sample_df.empty else (None, "All")
mc_date_range, mc_unit = setup_filters(mc_df, "Measuring Cells") if not mc_df.empty else (None, "All")

def apply_filters(df, date_range, unit):
    if df.empty:
        return df
    start, end = date_range if date_range else (None, None)
    filtered = df
    if start and end:
        filtered = filtered[(filtered["Date"] >= start) & (filtered["Date"] <= end)]
    if "Unit" in df.columns and unit and unit != "All":
        filtered = filtered[filtered["Unit"] == unit]
    return filtered

filtered_test = apply_filters(test_df, test_date_range, test_unit)
filtered_sample = apply_filters(sample_df, sample_date_range, sample_unit)
filtered_mc = apply_filters(mc_df, mc_date_range, mc_unit)

tabs = st.tabs(["Test Counter", "Sample Counter", "Measuring Cells Counter", "Download"])

with tabs[0]:
    st.header("Test Counter Data")
    cols_test = ["Test", "Routine", "Calib.", "QC", "Rerun", "STAT", "Total Count"]
    final_test_df = filtered_test[cols_test] if not filtered_test.empty else pd.DataFrame()
    if not final_test_df.empty:
        with st.container():
            st.markdown('<div class="rounded-box">', unsafe_allow_html=True)
            st.dataframe(final_test_df)
            base = alt.Chart(final_test_df).mark_line(point=True).encode(
                x="Test:N",
                y="Total Count:Q",
                color=alt.value("#1f77b4"),
                tooltip=["Test", "Total Count"]
            )
            text = base.mark_text(align='center', baseline='bottom', dy=-5).encode(text='Total Count:Q')
            st.altair_chart(base + text, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No Test Counter data to display.")

with tabs[1]:
    st.header("Sample Counter Data")
    cols_sample = ["Unit", "Routine", "Rerun", "STAT", "Total Count"]
    final_sample_df = filtered_sample[cols_sample] if not filtered_sample.empty else pd.DataFrame()
    if not final_sample_df.empty:
        with st.container():
            st.markdown('<div class="rounded-box">', unsafe_allow_html=True)
            st.dataframe(final_sample_df)
            base = alt.Chart(final_sample_df).mark_bar().encode(
                x="Unit:N",
                y="Routine:Q",
                color="Unit:N",
                tooltip=["Unit", "Routine"]
            )
            text = base.mark_text(dy=-5, color='black').encode(text='Routine:Q')
            st.altair_chart(base + text, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No Sample Counter data to display.")

with tabs[2]:
    st.header("Measuring Cells Counter Data")
    cols_mc = ["Unit", "MC Serial No.", "Last Reset", "Count after Reset", "Total Count"]
    final_mc_df = filtered_mc[cols_mc] if not filtered_mc.empty else pd.DataFrame()
    if not final_mc_df.empty:
        with st.container():
            st.markdown('<div class="rounded-box">', unsafe_allow_html=True)
            st.dataframe(final_mc_df)
            base = alt.Chart(final_mc_df).mark_line(point=True).encode(
                x="MC Serial No.:N",
                y="Total Count:Q",
                color="Unit:N",
                tooltip=["Unit", "MC Serial No.", "Total Count"]
            )
            text = base.mark_text(align='center', baseline='bottom', dy=-5).encode(text='Total Count:Q')
            st.altair_chart(base + text, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No Measuring Cells counter data to display.")

with tabs[3]:
    st.header("Download Data")
    if not final_test_df.empty:
        st.download_button("Download Test CSV", final_test_df.to_csv(index=False), "test_counter.csv")
    if not final_sample_df.empty:
        st.download_button("Download Sample CSV", final_sample_df.to_csv(index=False), "sample_counter.csv")
    if not final_mc_df.empty:
        st.download_button("Download MC CSV", final_mc_df.to_csv(index=False), "mc_counter.csv")
