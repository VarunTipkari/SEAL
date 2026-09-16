#!/usr/bin/env python
"""Launch SEAL AI v2 with FastAPI + Uvicorn."""
import uvicorn

if __name__ == "__main__":
    print("=" * 70, flush=True)
    print("SEAL AI v2 - starting server", flush=True)
    print("URL: http://127.0.0.1:8000", flush=True)
    print("=" * 70, flush=True)
    uvicorn.run(
        "backend.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
