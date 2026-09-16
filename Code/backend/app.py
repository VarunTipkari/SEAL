"""SEAL AI v2 - FastAPI entry point"""
from .routes import app

# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)