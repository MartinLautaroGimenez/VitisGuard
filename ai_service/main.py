"""Microservicio de IA de VitisGuard (FastAPI).

Expone ``POST /detect`` que recibe una imagen JPEG de la trampa y devuelve el
conteo de polillas, las cajas detectadas, la especie y una imagen anotada (PNG b64).

Arranque:
    cd ai_service
    python -m venv .venv && source .venv/bin/activate     # Python 3.11/3.12 recomendado
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from detector import get_detector

app = FastAPI(title="VitisGuard AI", version="1.0")


@app.get("/health")
def health():
    det = get_detector()
    return {"status": "ok", "backend": det.backend}


@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    data = await image.read()
    result = get_detector().detect(data)
    return JSONResponse(result)
