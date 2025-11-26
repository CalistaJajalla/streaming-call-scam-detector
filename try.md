# Live Scam Call Detector - Setup & Run Guide

## 1. Setup Python Environment

```bash
python -m venv kafka-env
source kafka-env/bin/activate  # Windows: kafka-env\Scripts\activate
pip install aiokafka kafka-python scikit-learn pandas numpy joblib streamlit
```

2. Start Kafka Environment with Docker Compose

Inside docker-compose.yml, write the following:
```bash
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
```

Then, run Kafka stack:
```bash
docker compose up -d
```

3. Train the ML Model

Run trainer.py to generate synthetic call data and train the KNN model. Output is saved as knn_model.joblib.

```bash
python trainer.py
```

4. Run Application Components

Open 3 separate terminal windows and run the following files

- Terminal 1: Processor (Kafka consumer + scam call prediction)
processor.py: Consumes raw call events from Kafka topic calls_raw, runs ML model to predict scam likelihood, then produces results to calls_scored.

```bash
python processor.py
```


- Terminal 2: Producer (Simulated call event generator)
producer.py: Produces randomized call event data to Kafka topic calls_raw.
  
```bash
python producer.py
```

- Terminal 3: Streamlit Dashboard UI
streamlit_app.py: Displays live streaming results from Kafka topic calls_scored in a dashboard with interactive refresh.

```bash
streamlit run streamlit_app.py
```




