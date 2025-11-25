docker compose up -d

version: '3.8'
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
trainer.py
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

producer.py
import asyncio
import json
import random
import time
from aiokafka import AIOKafkaProducer
import numpy as np

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "calls_raw"

def random_call_event():
    return {
        "call_duration": float(np.random.exponential(scale=60)),
        "num_digits": int(np.random.choice([7,10,11,12], p=[0.2,0.5,0.2,0.1])),
        "hour_of_day": int(np.random.randint(0,24)),
        "freq_calls": int(np.random.poisson(lam=2)),
        "caller": f"+63{np.random.randint(1000000,9999999)}",
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

processor.py
import asyncio
import json
import time
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import joblib
import numpy as np

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
INPUT_TOPIC = "calls_raw"
OUTPUT_TOPIC = "calls_scored"
MODEL_PATH = "knn_model.joblib"

class ScamDetector:
    def __init__(self, model_path):
        self.model = joblib.load(model_path)

    def featurize(self, event):
        return np.array([[event['call_duration'], event['num_digits'], event['hour_of_day'], event['freq_calls']]])

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
            event = json.loads(msg.value.decode("utf-8"))
            pred_label, pred_proba = detector.predict(event)
            output = {
                "call": event,
                "predicted_label": pred_label,
                "predicted_proba": pred_proba,
                "processed_ts": time.time(),
            }
            await producer.send_and_wait(OUTPUT_TOPIC, json.dumps(output).encode("utf-8"))
    finally:
        await consumer.stop()
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(consume_and_process())

streamlit_app.py
import streamlit as st
from kafka import KafkaConsumer
import json
import pandas as pd
import threading
import time

st.set_page_config(page_title="Live Scam Call Detector", layout="wide")
st.title("Live Scam Call Detector")

BUFFER_SIZE = 200
events = []
lock = threading.Lock()

def kafka_consumer_thread():
    consumer = KafkaConsumer(
        "calls_scored",
        bootstrap_servers="localhost:9092",
        auto_offset_reset="latest",
        group_id="streamlit_group",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    for msg in consumer:
        with lock:
            events.append(msg.value)
            if len(events) > BUFFER_SIZE:
                events[:] = events[-BUFFER_SIZE:]

if "consumer_thread" not in st.session_state:
    thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    thread.start()
    st.session_state.consumer_thread = thread

st.sidebar.header("Settings")
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 0.5, 5.0, 1.0, 0.1)
max_events = st.sidebar.slider("Show last N events", 10, BUFFER_SIZE, 50)

placeholder = st.empty()

def prepare_df():
    with lock:
        recent = events[-max_events:]
    if not recent:
        return pd.DataFrame()
    df = pd.json_normalize(recent)
    df = df.rename(columns={
        "call.caller": "Caller",
        "call.call_duration": "Duration (s)",
        "call.hour_of_day": "Hour",
        "call.freq_calls": "Freq Calls",
        "predicted_label": "Scam (1) / Not (0)",
        "processed_ts": "Processed Timestamp"
    })
    df["Processed Timestamp"] = pd.to_datetime(df["Processed Timestamp"], unit='s')
    return df

while True:
    df = prepare_df()
    with placeholder.container():
        st.subheader("Latest Predictions")
        if df.empty:
            st.info("Waiting for data... Start producer and processor.")
        else:
            st.dataframe(df.sort_values("Processed Timestamp", ascending=False).reset_index(drop=True))
            counts = df["Scam (1) / Not (0)"].value_counts().to_dict()
            st.metric("Scam calls detected", counts.get(1, 0))
            st.metric("Non-scam calls", counts.get(0, 0))
    time.sleep(refresh_interval)




# 1) Create and activate a Python virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate

# 2) Install all Python dependencies
pip install aiokafka kafka-python scikit-learn pandas numpy joblib streamlit

# 3) Start Kafka stack (using the updated docker-compose.yml with Confluent images)
docker compose up -d

# 4) Train your ML model once
python trainer.py

# 5) Open 3 separate terminals and run these commands:

# Terminal 1: Start the processor (consumer + predictor)
python processor.py

# Terminal 2: Start the producer (produces random call events)
python producer.py

# Terminal 3: Run the Streamlit dashboard UI
streamlit run streamlit_app.py

