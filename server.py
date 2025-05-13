from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from kafka import KafkaProducer, KafkaConsumer
import asyncio, json

app = FastAPI()

@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

@app.post("/publish")
async def publish(msg: dict):
    producer.send("chat", msg)
    producer.flush()
    return {"status": "ok"}

@app.get("/stream")
async def stream():
    consumer = KafkaConsumer(
        "chat",
        bootstrap_servers=["localhost:9092"],
        auto_offset_reset="latest",
        group_id=None,
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    async def event_generator():
        try:
            while True:
                for msgs in consumer.poll(timeout_ms=1000).values():
                    for m in msgs:
                        yield f"data: {json.dumps(m.value)}\n\n"
                await asyncio.sleep(0.1)
        finally:
            consumer.close()
    return StreamingResponse(event_generator(), media_type="text/event-stream")
