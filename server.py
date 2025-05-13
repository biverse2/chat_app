import ssl
import json
import asyncio
import time
from kafka import KafkaProducer, KafkaConsumer
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request, HTTPException

# FastAPI app setup
app = FastAPI()

@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

# === AIVEN KAFKA CONFIG ===
KAFKA_BOOTSTRAP_SERVERS = "kafka-chatapp-chatapp-2.c.aivencloud.com:20658"
KAFKA_USERNAME = "avnadmin"  # Replace with your Aiven Kafka username

CA_FILE = "ca.pem"  # CA file location
SSL_CERTFILE = "service.cert"  # Service certificate location
SSL_KEYFILE = "service.key"  # Service key file location

# SSL context setup for secure communication
ssl_context = ssl.create_default_context(cafile=CA_FILE)
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

# Kafka topic
TOPIC_NAME = "chat"

# === Producer Setup ===
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_plain_username=KAFKA_USERNAME,

    ssl_cafile=CA_FILE,
    ssl_certfile=SSL_CERTFILE,
    ssl_keyfile=SSL_KEYFILE,
    value_serializer=lambda v: v.encode('utf-8'),
    key_serializer=lambda v: v.encode('utf-8') if v is not None else None
)



# === FastAPI Endpoint to Publish Messages ===
@app.post("/publish")
async def publish(msg: dict):
    print("Publishing message:", msg)
    text = msg.get("text", "hello")  # Default if no text provided
    producer.send(TOPIC_NAME, value=text)
    producer.flush()
    return {"status": "ok"}






# === FastAPI Endpoint for Kafka Stream ===
@app.get("/stream")
async def stream():
    consumer = KafkaConsumer(
        TOPIC_NAME,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        security_protocol="SASL_SSL",  # Use SASL_SSL for secure connection
        sasl_mechanism="PLAIN",  # SASL PLAIN authentication mechanism
        sasl_plain_username=KAFKA_USERNAME,  # Aiven Kafka username
  
        ssl_cafile=CA_FILE,  # CA certificate
        ssl_certfile=SSL_CERTFILE,  # Service certificate
        ssl_keyfile=SSL_KEYFILE,  # Service key
        auto_offset_reset="latest",  # Start reading from the latest message
        group_id="something",  # No consumer group
        enable_auto_commit=False,  # Manual commit
        consumer_timeout_ms=1000,  # Timeout if no messages
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),  # Deserialize message
        api_version=(2, 0, 0)
    )

    async def event_generator():
        try:
            for message in consumer:
                yield f"data: {json.dumps(message.value)}\n\n"
                await asyncio.sleep(0.1)
        finally:
            consumer.close()


    return StreamingResponse(event_generator(), media_type="text/event-stream")

