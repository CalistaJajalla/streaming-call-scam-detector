# Live Scam Call Detector

This guide helps set up the full streaming pipeline.

**Kafka → Producer → Processor (ML) → Streamlit Dashboard**

---

## 1. Project Folder Structure

Make sure your project directory looks like this:

streaming-call-scam-detector/
│
├── docker-compose.yml
├── trainer.py
├── producer.py
├── processor.py
├── streamlit_app.py
├── knn_model.joblib
└── SETUP.md


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

Run the training script to generate synthetic call data, train the KNN model, and save it.

```bash
python trainer.py
```

This will create the knn_model.joblib file required by the processor.

## 6. Run the Streaming Pipeline

Open 3 separate terminal windows (make sure you activate the virtual environment in each):

- Terminal 1 - Processor
  - Consumes call events, predicts scam likelihood, and produces results.

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




