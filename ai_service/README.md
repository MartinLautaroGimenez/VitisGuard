# VitisGuard — Microservicio de IA

Servicio **FastAPI** independiente que clasifica/cuenta polillas (*Lobesia botrana*)
en las imágenes de trampa. El core Flask lo consume por HTTP (`POST /detect`) y
degrada con elegancia si el servicio no está disponible.

## Por qué es un servicio aparte
- Aísla la dependencia pesada (PyTorch/Ultralytics) del servidor Flask, que corre
  en Python 3.14 sin problemas.
- Coincide con la arquitectura del documento original ("FastAPI + YOLO").
- Se puede escalar/entrenar por separado y hasta correr en otra máquina con GPU.

## Backends
El detector elige automáticamente:

| Backend | Cuándo | Qué hace |
|---------|--------|----------|
| **CV** (por defecto) | Sin pesos entrenados | Detector clásico OpenCV que cuenta blobs oscuros sobre el engomado. **Funciona desde el minuto cero.** |
| **YOLO11** | Hay `models/*.pt` (o `AI_MODEL_PATH`) y `ultralytics` instalado | Detección por deep learning entrenada para la plaga. |

## Puesta en marcha (backend CV — inmediato)
```bash
cd ai_service
python -m venv .venv && source .venv/bin/activate     # 3.11/3.12 recomendado
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```
Probar: `curl -F image=@trampa.jpg http://127.0.0.1:8001/detect`

## Pasar al backend YOLO11 (modelo real entrenado)
1. Instalar extras: `pip install -r requirements-yolo.txt`
2. Conseguir un dataset etiquetado en formato YOLO (p. ej. buscar *"grape moth"* /
   *"Lobesia botrana"* en Roboflow y exportar a YOLOv8). Debe traer un `data.yaml`.
3. Entrenar:
   ```bash
   python train.py --data /ruta/dataset/data.yaml --epochs 100 --imgsz 640
   ```
   El mejor modelo queda en `models/lobesia.pt`.
4. Reiniciar `uvicorn`: el servicio detecta los pesos y usa **YOLO** automáticamente.

## Variables de entorno
- `AI_MODEL_PATH` — ruta a pesos `.pt` (si no, se busca en `models/`).
- `AI_USE_YOLO` — `off` fuerza el backend CV aunque haya pesos.
- `AI_CONF` — umbral de confianza YOLO (default 0.25).

## Respuesta de `POST /detect`
```json
{
  "count": 3,
  "species": "Lobesia botrana",
  "confidence": 0.81,
  "detections": [{"x":0.1,"y":0.2,"w":0.05,"h":0.04,"class_name":"Lobesia botrana","confidence":0.83}],
  "annotated_png_b64": "iVBORw0KGgo...",
  "backend": "cv"
}
```
