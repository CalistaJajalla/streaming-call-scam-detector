import streamlit as st
import pandas as pd

st.set_page_config(page_title="Live Scam Call Detector (Fallback)", layout="wide")

# Page header, instructions, UI setup: keep the same as original
st.markdown("""
<h1 style="text-align:center; margin-bottom:5px; color:#58a6ff;">📞 Live Scam Call Detector (Fallback Mode)</h1>
<p style="text-align:center; font-size:16px; color:#aaa; margin-top:-10px;">
Using static sample data instead of live Kafka stream.<br>
<b>by Calista Jajalla</b>
</p>
<hr style="border-color:#444;">
""", unsafe_allow_html=True)

# Load sample CSV (make sure you add this file to your repo)
df = pd.read_csv("sample_calls_scored.csv")

# Process dataframe as in original prepare_df()
def prepare_df_from_csv(df):
    # Rename columns (adjust if CSV columns differ)
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

st.subheader("Sample Predictions (Static Data)")

st.write(f"**Data snapshot:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

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

st.markdown("---")

st.header("Note")

st.write("""
This is a **fallback mode** showing pre-recorded data from a CSV file.  
Real-time streaming and live updates require Kafka and the full pipeline running.  
This version is only for demos since my Kafka is in local set-up at the moment.
Peace ✌︎︎♡⃛
""")
