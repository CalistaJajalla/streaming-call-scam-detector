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
