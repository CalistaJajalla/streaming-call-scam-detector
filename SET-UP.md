# Live Scam Call Detector by Calista Jajalla

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

Then, run this in your terminal.

```bash
python processor.py
```

- Terminal 2 — Producer
  - Generates random call events and sends to Kafka.

```bash
python producer.py
```

- Terminal 3 — Streamlit Dashboard
  - Visualizes live predictions with an interactive dashboard.

```bash
streamlit run streamlit_app.py
```

## 7. Stopping the System

When finished, stop Kafka containers and deactivate environment:

```bash
docker compose down
deactivate
```




