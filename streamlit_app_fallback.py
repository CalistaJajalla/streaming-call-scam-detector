import streamlit as st
import pandas as pd
import time

st.set_page_config(page_title="Live Scam Call Detector", layout="wide")

# Page header, instructions, UI setup
st.markdown("""
<h1 style="text-align:center; margin-bottom:5px; color:#58a6ff;">📞 Live Scam Call Detector</h1>
<p style="text-align:center; font-size:16px; color:#aaa; margin-top:-10px;">
Built with Kafka • Machine Learning • Real-time Streaming <br>
<b>by Calista Jajalla</b>
</p>
<hr style="border-color:#444;">

<div style="
    background-color:#2c2c2c; 
    padding:20px; 
    border-radius:10px; 
    margin-bottom:20px;
    color:#ccc;
    font-size: 15px;
    line-height: 1.5;
">
    <h3 style="color:#58a6ff; margin-bottom:10px;">ℹ Instructions & Disclaimer</h3>
    <ul style="padding-left:20px; margin-top:0;">
        <li>Hello! This dashboard shows sample predictions of scam calls inspired by streaming data.</li>
        <li>The full real-time streaming setup is currently running locally and being migrated to the cloud.</li>
        <li>Data refreshes every few seconds. Use the sidebar slider to adjust the refresh interval.</li>
        <li>Displayed data reflects how live predictions typically appear, with updates occurring regularly.</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# Load sample CSV 
df = pd.read_csv("sample_calls_scored.csv")

# Process dataframe as in original prepare_df()
def prepare_df_from_csv(df):
    df = df.rename(columns={
        "call.caller": "Caller Number",
        "call.call_duration": "Duration (secs)",
        "call.hour_of_day": "Call Hour",
        "predicted_label": "Scam Detected",
        "processed_ts": "Processed Time"
    })

    df = df[["Caller Number", "Duration (secs)", "Call Hour", "Scam Detected", "Processed Time"]]

    df["Processed Time"] = pd.to_datetime(df["Processed Time"], unit='s')

    df["Scam Detected"] = df["Scam Detected"].map({0: "No", 1: "Yes"})

    return df

df = prepare_df_from_csv(df)

# Sidebar controls for refresh interval and max rows to show
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 1, 10, 3)
max_events = st.sidebar.slider("Show last N events", 10, 200, 50)

# Use Streamlit's autorefresh with the selected interval
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=refresh_interval * 1000, key="autorefresh")

# Simulate "streaming" by showing a sliding window over data that grows with refresh count
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0
st.session_state.refresh_count += 1

# Number of rows to show grows with refresh count until max_events
rows_to_show = min(st.session_state.refresh_count * 5, max_events)

st.subheader("Latest Predictions")

st.write(f"**Last updated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

df_slice = df.sort_values("Processed Time", ascending=False).head(rows_to_show).reset_index(drop=True)
st.dataframe(df_slice)

counts = df_slice["Scam Detected"].value_counts().to_dict()

col1, col2 = st.columns(2)
with col1:
    st.metric("Scam Calls Detected", counts.get("Yes", 0))
with col2:
    st.metric("Non-Scam Calls", counts.get("No", 0))

st.markdown("---")

st.header("Frequently Asked Questions (FAQ)")

with st.expander("How does the system flag a call as scam or non-scam?"):
    st.write("""
    I use a machine learning model (K-Nearest Neighbors) trained to analyze call features like duration, call frequency, and time of day.  
    Basically, the model predicts whether a call is likely to be a scam based on patterns learned from historical call data.  
    The result is a real-time prediction displayed here as “Yes” (scam) or “No” (non-scam).
    """)

with st.expander("Where does the call data come from?"):
    st.write("""
    The call data is generated in real-time by a simulated producer sending call records to Kafka topics.  
    Each record contains anonymized call details such as caller number, call duration, and timestamp.  
    This setup copies how telecom systems might stream live call data for analysis.
    """)

with st.expander("How was the model trained?"):
    st.write("""
    The model was trained on labeled historical call data where calls were marked as scam or legitimate.  
    Features extracted from each call helped the model learn to distinguish patterns indicative of scams.  
    Training involved using scikit-learn’s K-Nearest Neighbors algorithm to build a predictive classifier.
    """)

with st.expander("How often is the data updated?"):
    st.write("""
    Data updates every few seconds as new calls are processed and scored.  
    You can adjust the refresh interval using the slider in the sidebar to control how frequently new data appears.
    Let the data load fully and don't just hastily drag the slider! :>         
    """)
