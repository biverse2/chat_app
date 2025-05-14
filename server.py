import ssl
import json
import asyncio
from kafka import KafkaProducer, KafkaConsumer
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# FastAPI app setup
app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

# === Kafka Configuration ===
KAFKA_BOOTSTRAP_SERVERS = "kafka-chatapp-chatapp-2.c.aivencloud.com:20658"
TOPIC_NAME = "chat"
CA_FILE = "ca.pem"
SSL_CERTFILE = "service.cert"
SSL_KEYFILE = "service.key"

# Initialize Kafka Producer
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        security_protocol="SSL",
        ssl_cafile=CA_FILE,
        ssl_certfile=SSL_CERTFILE,
        ssl_keyfile=SSL_KEYFILE,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    print("Kafka producer initialized successfully")
except Exception as e:
    raise RuntimeError(f"Failed to initialize Kafka producer: {e}")

# === Publish Endpoint ===
@app.post("/publish")
async def publish(msg: dict):
    if 'user' not in msg or 'text' not in msg:
        raise HTTPException(status_code=400, detail="Message must contain 'user' and 'text' fields")
    
    try:
        producer.send(TOPIC_NAME, value=msg)
        producer.flush()
        return {"status": "ok", "mode": "kafka"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kafka error: {e}")

# === Stream Endpoint ===
@app.get("/stream")
async def stream():
    try:
        consumer = KafkaConsumer(
            TOPIC_NAME,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            security_protocol="SSL",
            ssl_cafile=CA_FILE,
            ssl_certfile=SSL_CERTFILE,
            ssl_keyfile=SSL_KEYFILE,
            auto_offset_reset="earliest",
            group_id=None,
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8"))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Kafka consumer: {e}")
    
    async def kafka_event_generator():
        try:
            yield f"data: {json.dumps({'user': 'System', 'text': 'Connected to Kafka chat stream'})}\n\n"
            while True:
                messages = consumer.poll(timeout_ms=1000, max_records=10)
                for tp, msgs in messages.items():
                    for message in msgs:
                        yield f"data: {json.dumps(message.value)}\n\n"
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Kafka streaming error: {e}")
            yield f"data: {json.dumps({'user': 'System', 'text': 'Kafka error. Stream ended.'})}\n\n"
        finally:
            consumer.close()

    return StreamingResponse(kafka_event_generator(), media_type="text/event-stream")

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "kafka": "connected"}

# Clear endpoint removed since no in-memory store
