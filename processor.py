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
