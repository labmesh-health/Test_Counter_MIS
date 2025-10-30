# LAB MIS Instrument Test Counter Difference Calculator

This Streamlit app, **Test Counter MIS.py**, allows users to upload two PDF reports containing instrument test counters for different dates. The app extracts the test counter data, determines which report is newer, and calculates the difference in test counters between the two dates. The differences are displayed in both tabular and graphical forms.

## Features

- Upload two PDF reports simultaneously through the sidebar.
- Extract test counter data including Routine, Rerun, STAT, Calibrator, QC, and Total Count.
- Automatically identify the newer and older reports based on embedded datetime.
- Calculate the difference between newer and older test counters.
- View results in interactive tables and Altair bar charts.
