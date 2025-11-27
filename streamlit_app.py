import streamlit as st
from kafka import KafkaConsumer
import json
import pandas as pd
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Live Scam Call Detector", layout="wide")

BUFFER_SIZE = 200
MAX_POLL_RECORDS = 10

# Page header and disclaimer/instructions
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
        <li>Hello! This dashboard displays real-time predictions of scam calls based on streaming data.</li>
        <li>Data updates every few seconds. Refresh interval adjustable in the sidebar.</li>
        <li>There may be a short delay (a few seconds) from when calls are made to when predictions appear here.</li>
        <li>Ensure the <code style="background:#444; padding:2px 5px; border-radius:3px;">Producer</code> and <code style="background:#444; padding:2px 5px; border-radius:3px;">Processor</code> components are running to feed data.</li>
        <li>Displayed data is limited to the most recent events to keep the interface responsive :)).</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# Cache KafkaConsumer as resource, fallback for older Streamlit versions
try:
    cache_decorator = st.cache_resource
except AttributeError:
    cache_decorator = st.cache(allow_output_mutation=True)

@cache_decorator
def get_consumer():
    return KafkaConsumer(
        "calls_scored",
        bootstrap_servers="localhost:9092",
        auto_offset_reset="latest",
        group_id="streamlit_group",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=1000,
    )

consumer = get_consumer()

if "events" not in st.session_state:
    st.session_state.events = []

# Sidebar controls
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 1, 10, 3)
max_events = st.sidebar.slider("Show last N events", 10, BUFFER_SIZE, 50)

st_autorefresh(interval=refresh_interval * 1000, key="autorefresh")

def poll_kafka():
    new_events = []
    try:
        polled = consumer.poll(timeout_ms=500, max_records=MAX_POLL_RECORDS)
        for msg_batch in polled.values():
            for record in msg_batch:
                new_events.append(record.value)
    except Exception as e:
        st.error(f"Error polling Kafka: {e}")
    return new_events

new_msgs = poll_kafka()
if new_msgs:
    st.session_state.events.extend(new_msgs)
    st.session_state.events = st.session_state.events[-BUFFER_SIZE:]

def prepare_df(events):
    if not events:
        return pd.DataFrame()

    df = pd.json_normalize(events)

    # Only keep important columns and rename for clarity
    df = df.rename(columns={
        "call.caller": "Caller Number",
        "call.call_duration": "Duration (secs)",
        "call.hour_of_day": "Call Hour",
        "predicted_label": "Scam Detected",
        "processed_ts": "Processed Time"
    })

    # Keep only essential columns
    df = df[["Caller Number", "Duration (secs)", "Call Hour", "Scam Detected", "Processed Time"]]

    df["Processed Time"] = pd.to_datetime(df["Processed Time"], unit='s')

    # Make Scam Detected column more human-friendly
    df["Scam Detected"] = df["Scam Detected"].map({0: "No", 1: "Yes"})

    return df

st.subheader("Latest Predictions")

df = prepare_df(st.session_state.events[-max_events:])

if df.empty:
    st.info("Waiting for data... Please ensure the Producer & Processor are running.")
else:
    st.write(f"**Last updated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.dataframe(df.sort_values("Processed Time", ascending=False).reset_index(drop=True))

    counts = df["Scam Detected"].value_counts().to_dict()

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
