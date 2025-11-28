# 📞 Live Scam Call Detector by Calista Jajalla ᓚᘏᗢ

This guide helps set up the full streaming pipeline.

**Kafka → Producer → Processor (ML) → Streamlit Dashboard**

---

## 1. Project Folder Structure

Make sure your project directory looks like this:

```bash
streaming-call-scam-detector/
│
├── docker-compose.yml
├── trainer.py
├── producer.py
├── processor.py
├── requirements.txt
├── streamlit_app.py
└── SETUP.md
```

---

## 2. Create Python Virtual Environment

Create an isolated Python environment to avoid package conflicts.

```bash
python -m venv kafka-env
source kafka-env/bin/activate   # For Windows use: kafka-env\Scripts\activate
```

## 3. Install Required Python Packages

Install all necessary dependencies for Kafka, ML, and Streamlit.

```bash
pip install aiokafka kafka-python scikit-learn pandas numpy joblib streamlit
```

## 4. Setup Kafka Using Docker Compose

Create docker-compose.yml file with the following content.
This will start Kafka and Zookeeper in Docker containers.

```bash
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

Then, start Kafka and Zookeeper containers.

```
docker compose up -d
```

## 5. Train the Machine Learning Model

Write the training script. Feel free to customize and optimize this.

```python
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
import joblib

def generate_synthetic_data(n_samples=5000, random_seed=42):
    np.random.seed(random_seed)
    call_duration = np.random.exponential(scale=60, size=n_samples)
    num_digits = np.random.choice([7,10,11,12], size=n_samples, p=[0.2, 0.5, 0.2, 0.1])
    hour_of_day = np.random.randint(0, 24, size=n_samples)
    freq_calls = np.random.poisson(2, size=n_samples)

    # Labeling logic (probabilistic)
    prob_scam = (
        (call_duration < 40).astype(float) * 0.4 +
        ((hour_of_day < 6) | (hour_of_day > 22)).astype(float) * 0.3 +
        (freq_calls > 3).astype(float) * 0.3 +
        (num_digits == 11).astype(float) * 0.1
    )
    prob_scam = np.clip(prob_scam, 0, 0.95)
    labels = (np.random.rand(n_samples) < prob_scam).astype(int)

    return pd.DataFrame({
        "call_duration": call_duration,
        "num_digits": num_digits,
        "hour_of_day": hour_of_day,
        "freq_calls": freq_calls,
        "label": labels,
    })

def train_and_save_model(df, filename="knn_model.joblib"):
    X = df[["call_duration", "num_digits", "hour_of_day", "freq_calls"]]
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5))
    pipeline.fit(X_train, y_train)
    accuracy = pipeline.score(X_test, y_test)
    print(f"Test accuracy: {accuracy:.4f}")
    joblib.dump(pipeline, filename)
    print(f"Model saved to {filename}")

if __name__ == "__main__":
    data = generate_synthetic_data()
    train_and_save_model(data)
```
Run the training script to generate synthetic call data, train the KNN model, and save it.

```bash
python trainer.py
```

This will create the knn_model.joblib file required by the processor.

## 6. Run the Streaming Pipeline

Open 3 separate terminal windows (make sure you activate the virtual environment in each):

- Terminal 1 - Processor
  - Consumes call events, predicts scam likelihood, and produces results.

```python
import asyncio
import json
import time
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import joblib
import pandas as pd

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
INPUT_TOPIC = "calls_raw"
OUTPUT_TOPIC = "calls_scored"
MODEL_PATH = "knn_model.joblib"

class ScamDetector:
    FEATURE_COLUMNS = ['call_duration', 'num_digits', 'hour_of_day', 'freq_calls']

    def __init__(self, model_path):
        self.model = joblib.load(model_path)

    def featurize(self, event):
        # Use event directly, since producer sends flat dict without 'call' key
        df = pd.DataFrame([{
            'call_duration': event.get('call_duration', 0),
            'num_digits': event.get('num_digits', 0),
            'hour_of_day': event.get('hour_of_day', 0),
            'freq_calls': event.get('freq_calls', 0),
        }])
        return df[self.FEATURE_COLUMNS]

    def predict(self, event):
        x = self.featurize(event)
        pred = self.model.predict(x)[0]
        proba = self.model.predict_proba(x)[0].tolist() if hasattr(self.model, "predict_proba") else None
        return int(pred), proba

async def consume_and_process():
    detector = ScamDetector(MODEL_PATH)
    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="processor_group",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

    await consumer.start()
    await producer.start()
    print("Processor started: consuming raw calls and producing predictions.")
    try:
        async for msg in consumer:
            try:
                event = json.loads(msg.value.decode("utf-8"))
                print(f"Processing event: {event}")  # Debug
                pred_label, pred_proba = detector.predict(event)
                output = {
                    "call": event,  # Pass original flat event here
                    "predicted_label": pred_label,
                    "predicted_proba": pred_proba,
                    "processed_ts": time.time(),
                }
                await producer.send_and_wait(OUTPUT_TOPIC, json.dumps(output).encode("utf-8"))
                print(f"Produced prediction: {output}")
            except Exception as e:
                print(f"Error processing message: {e} | Message value: {msg.value}")
    finally:
        await consumer.stop()
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(consume_and_process())
```

Then, run this in your terminal:

```bash
python processor.py
```

-----

- Terminal 2 — Producer
  - Generates random call events and sends to Kafka.

```python
import asyncio
import json
import random
import time
from aiokafka import AIOKafkaProducer
import numpy as np

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "calls_raw"

def generate_ph_mobile():
    # PH mobile numbers: 09 + 9 digits (11 digits total)
    return "09" + "".join([str(random.randint(0, 9)) for _ in range(9)])

def random_call_event():
    return {
        "call_duration": float(np.random.exponential(scale=60)),
        "num_digits": 11,  
        "hour_of_day": int(np.random.randint(0, 24)),
        "freq_calls": int(np.random.poisson(lam=2)),
        "caller": generate_ph_mobile(),
        "ts": time.time(),
    }

async def produce():
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    try:
        print("Producer started, streaming calls to Kafka...")
        while True:
            event = random_call_event()
            await producer.send_and_wait(TOPIC, json.dumps(event).encode('utf-8'))
            await asyncio.sleep(random.uniform(0.1, 0.7))  # adjustable rate
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(produce())
```
Then, run this in your terminal:

```bash
python producer.py
```

----

- Terminal 3 — Streamlit Dashboard
  - Visualizes live predictions with an interactive dashboard.

```python
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
```

Then, run this in your terminal:

```bash
streamlit run streamlit_app.py
```

## 7. Stopping the System

When finished, stop Kafka containers and deactivate environment:

```bash
docker compose down
deactivate
```

----

## Optional: Run Streamlit Dashboard with Sample CSV (Fallback Mode)

Here's a fallback Streamlit app that reads from a sample CSV file containing historical or simulated data (If my Kafka and docker is not running. I'm still migrating this to cloud ://)

1. Use the CSV file (sample_calls_scored.csv) in my project folder. It's generated from one of real-time my runs.

2. Create a fallback Streamlit script: streamlit_app_fallback.py

Add a new Python file streamlit_app_fallback.py with the following minimal changes:

```python
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
Use this version for easy demos or when you don't have access to Kafka.
""")
```

3. Run fallback app in your terminal.

```bash
streamlit run streamlit_app_fallback.py
```



