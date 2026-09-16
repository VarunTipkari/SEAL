# SEAL AI v2 — Vision Fixed

This build fixes the image/vision pipeline and keeps the previous terminal/runtime fixes.

## Main vision fixes

- Uploaded image paths are converted to actual image bytes before the agent runs.
- Vision input is validated before calling the vision model.
- Ollama receives image bytes in the `images` field.
- If JSON-format mode is rejected by the installed vision model, SEAL retries without JSON format and still parses a structured response when possible.
- Vision failures are printed clearly in the server terminal.
- The Vision → General handoff remains enabled.
- Frontend polling recognizes completed results even when status is absent, and successful backend runs now explicitly return `status: ok`.

## Folder structure

```text
SEAL_AI_v2_FIXED_VISION/
├── backend/
├── dashboard/
│   └── static/
├── knowledge/
├── workspace/
├── requirements.txt
├── run.py
└── README.md
```

## Install

```bat
python -m pip install -r requirements.txt
```

Make sure Ollama is running and that the configured models exist. The default vision model is `qwen2.5vl:3b`.

```bat
ollama list
```

If it is not installed, install the configured model using your Ollama setup, for example:

```bat
ollama pull qwen2.5vl:3b
```

## Start

Run from the project root:

```bat
python run.py
```

Open:

```text
http://127.0.0.1:8000
```

If port 8000 is occupied, stop the existing process or change the port in `run.py`.

## Test vision

1. Open the dashboard.
2. Attach a PNG/JPG/JPEG/WEBP image.
3. Ask: `What is shown in this image?`
4. Watch the server terminal. You should see events similar to:

```text
[SEAL] [route] Route → vision
[SEAL] [vision_input] screenshot.png · 123,456 bytes
[SEAL] [model_start] Vision · qwen2.5vl:3b
[SEAL] [thinking] Vision is processing · qwen2.5vl:3b
[SEAL] [vision_payload] Attached 1 image(s) · 123,456 bytes
[SEAL] [model_done] Vision completed · qwen2.5vl:3b
[SEAL] [handoff] Vision → General: visual evidence transferred
```

If Ollama rejects the JSON format, you will see a `vision_retry` event and SEAL will retry the same image without JSON format.

## Vision fix

This version fixes a FastAPI serialization crash caused by returning raw PNG/JPEG bytes in the `/api/run/{sid}` JSON result. Image bytes are now used internally by the vision model and removed before results are stored/returned.

If port 8000 is busy on Windows:
```bat
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

Ensure Ollama has the configured vision model:
```bat
ollama list
```
Default vision model: `qwen2.5vl:3b`.

