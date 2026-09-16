"""FastAPI routes for SEAL AI v2 dashboard"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from functools import partial
from pathlib import Path
from urllib.parse import quote
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, events
from .agents import general_agent, vision_agent, route_task, file_operation_plan
from .file_manager import (
    list_files, read_file, search_files, write_file, create_file,
    delete_path, move_path, copy_path, make_directory, execute_terminal,
    save_upload
)
from .graph import run as run_agent
from .chat_store import new_chat_id, make_title, save_chat, load_chat, list_chats, delete_chat
from .model_manager import ModelManager

# Global state
_runs: dict[str, dict] = {}
_current_task: Optional[asyncio.Task] = None
_current_sid: Optional[str] = None
_event_bus = events.EventBus()


def create_app() -> FastAPI:
    app = FastAPI(title="SEAL AI - Sovereign Enterprise AI Layer")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup():
        """Initialize the system on startup"""
        print("SEAL AI v2 starting...", flush=True)
        print(f"Workspace: {config.WORKSPACE_DIR}", flush=True)
        print(f"Models: {[f'{k}: {v.name}' for k, v in config.MODELS.items()]}", flush=True)

    # ---------- Health & Status ----------
    @app.get("/api/health")
    async def health():
        return {"ok": True, "name": "SEAL AI", "status": "ready"}

    @app.get("/api/status")
    async def status():
        return {
            "running": _current_sid,
            "busy": _current_task is not None and not _current_task.done(),
            "models": [
                {"role": "general", "name": config.MODELS["general"].name},
                {"role": "vision", "name": config.MODELS["vision"].name},
                {"role": "coding", "name": config.MODELS["coding"].name},
            ],
        }

    # ---------- Persistent chat history ----------
    @app.post("/api/chats")
    async def create_chat(body: dict | None = None):
        cid = new_chat_id()
        title = make_title((body or {}).get("title") or "New chat")
        save_chat(cid, title, [])
        return {"id": cid, "title": title, "messages": []}

    @app.get("/api/chats")
    async def chats():
        return {"chats": list_chats()}

    @app.get("/api/chats/{cid}")
    async def get_chat(cid: str):
        data = load_chat(cid)
        if not data:
            raise HTTPException(404, "Chat not found")
        return data

    @app.put("/api/chats/{cid}")
    async def put_chat(cid: str, body: dict):
        title = body.get("title") or make_title((body.get("messages") or [{}])[0].get("text", "New chat"))
        messages = body.get("messages") or []
        save_chat(cid, title, messages)
        return {"ok": True, "id": cid, "title": title, "messages": messages[-config.MAX_CHAT_MESSAGES:]}

    @app.delete("/api/chats/{cid}")
    async def remove_chat(cid: str):
        delete_chat(cid)
        return {"ok": True}

    # ---------- Agent Runs ----------
    @app.post("/api/run")
    async def start_run(body: dict):
        task = (body.get("task") or "").strip()
        print("\n" + "=" * 70, flush=True)
        print(f"[SEAL] USER TASK: {task}", flush=True)
        print("=" * 70, flush=True)
        
        files = body.get("files") or []
        chat_id = str(body.get("chat_id") or "").strip()

        if not task:
            raise HTTPException(400, "Task text required")
        if not chat_id:
            raise HTTPException(400, "chat_id required. Create/select a conversation first.")

        # ChatGPT-style architecture: the server is the source of truth for the
        # current conversation. Do not trust a browser-supplied history array.
        chat = load_chat(chat_id)
        if not chat:
            raise HTTPException(404, "Chat not found")
        history = list(chat.get("messages") or [])

        global _current_task, _current_sid
        if _current_task is not None and not _current_task.done():
            raise HTTPException(409, "SEAL is already running a task")

        # Persist the new user turn BEFORE invoking the model. This makes the
        # current conversation durable even while the model is working and means
        # every subsequent request sees exactly the same server-side history.
        user_attachments = []
        for f in files:
            fp = str(f)
            name = Path(fp).name or "file"
            is_image = Path(fp).suffix.lower() in config.IMAGE_EXTENSIONS
            user_attachments.append({
                "name": name,
                "path": fp,
                "isImage": is_image,
                "previewUrl": "/api/upload/preview?path=" + quote(fp),
            })
        user_record = {"role": "user", "text": task, "attachments": user_attachments}
        history_for_model = history[-config.MAX_CHAT_MESSAGES:]
        persisted_messages = history + [user_record]
        title = chat.get("title") or make_title(task)
        if title == "New chat":
            title = make_title(task)
        save_chat(chat_id, title, persisted_messages)

        sid = "run-" + uuid.uuid4().hex[:8]
        _current_sid = sid

        async def background_run():
            try:
                # IMPORTANT: run_agent() performs blocking Ollama/model/file work.
                # Running it directly inside the asyncio event loop blocks SSE delivery,
                # so model_start/thinking/model_done events only appeared in the terminal.
                # Execute the graph in a worker thread and marshal events back to the
                # main event loop so the browser receives model switches in realtime.
                loop = asyncio.get_running_loop()

                def publish_runtime_event(event):
                    payload = dict(event.__dict__)
                    loop.call_soon_threadsafe(
                        partial(_event_bus.publish, event.kind, sid=sid, **payload)
                    )

                # Convert files to their full paths
                file_paths = []
                for f in files:
                    p = Path(config.WORKSPACE_DIR) / f
                    if p.exists():
                        file_paths.append(str(p))
                
                # Vision models need the actual image bytes, not only the uploaded path.
                image_paths = [
                    p for p in file_paths
                    if Path(p).suffix.lower() in config.IMAGE_EXTENSIONS
                ]
                image_bytes = None
                if image_paths:
                    image_path = Path(image_paths[0])
                    try:
                        image_bytes = image_path.read_bytes()
                        print(
                            f"[SEAL] [vision_input] {image_path.name} · {len(image_bytes):,} bytes",
                            flush=True,
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            f"Could not read uploaded image '{image_path.name}': {exc}"
                        ) from exc

                state = {
                    "user_prompt": task,
                    "has_image": bool(image_paths),
                    "image_bytes": image_bytes,
                    "image_paths": image_paths,
                    "files": file_paths,
                    "history": history_for_model,
                "chat_id": chat_id,
                    "event_callback": publish_runtime_event,
                }
                
                result = await asyncio.to_thread(run_agent, state)
                # Never expose raw image bytes through FastAPI JSON responses.
                # FastAPI's jsonable_encoder tries to UTF-8 decode bytes, which
                # crashes for PNG/JPEG data (e.g. 0x89 PNG header).
                result.pop("image_bytes", None)
                result["sid"] = sid
                result["status"] = "ok"
                
                print(f"DEBUG: Result keys: {result.keys()}")
                print(f"DEBUG: answer: {result.get('answer', 'MISSING')}")
                print(f"DEBUG: final_answer: {result.get('final_answer', 'MISSING')}")
                
                # Ensure the result has 'final_answer' for the UI
                if "answer" in result and "final_answer" not in result:
                    result["final_answer"] = result["answer"]
                elif "final_answer" not in result:
                    result["final_answer"] = "Task completed successfully."
                
                if "artifacts" not in result:
                    result["artifacts"] = []
                
                print(f"DEBUG: Result keys: {list(result.keys())}")
                print(f"DEBUG: final_answer: {result.get('final_answer', 'MISSING')[:100]}...")

                # Persist the assistant turn on the server. The browser is only a
                # view of this state, not the memory store.
                assistant_record = {
                    "role": "assistant",
                    "text": result.get("final_answer") or result.get("answer") or "",
                    "model": result.get("model"),
                    "attachments": [],
                }
                latest_chat = load_chat(chat_id) or {"title": title, "messages": []}
                latest_messages = list(latest_chat.get("messages") or [])
                # Avoid duplicate assistant records if a retry races with storage.
                latest_messages.append(assistant_record)
                save_chat(chat_id, latest_chat.get("title") or title, latest_messages)

                _runs[sid] = result
                
                _event_bus.publish("run.done", sid=sid, status="ok")
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_text = f"Error: {str(e)}"
                _runs[sid] = {
                    "status": "error",
                    "error": str(e),
                    "sid": sid,
                    "final_answer": error_text,
                    "answer": error_text
                }
                try:
                    latest_chat = load_chat(chat_id) or {"title": title, "messages": []}
                    latest_messages = list(latest_chat.get("messages") or [])
                    latest_messages.append({"role": "assistant", "text": error_text, "model": None, "attachments": []})
                    save_chat(chat_id, latest_chat.get("title") or title, latest_messages)
                except Exception:
                    pass
                _event_bus.publish("run.error", sid=sid, error=str(e))
            finally:
                global _current_task, _current_sid
                _current_task = None
                _current_sid = None
                

        _current_task = asyncio.create_task(background_run())
        _event_bus.publish("run.started", sid=sid, task=task[:200])
        
        return {"sid": sid, "queued": True}

    @app.get("/api/run/{sid}")
    async def get_run(sid: str):
        if sid in _runs:
            result = _runs[sid]
            # Ensure final_answer exists
            if "final_answer" not in result:
                if "answer" in result:
                    result["final_answer"] = result["answer"]
                else:
                    result["final_answer"] = "Task completed."
            return result
        return {"status": "running" if _current_sid == sid else "unknown"}

    @app.post("/api/cancel")
    async def cancel_run():
        global _current_task
        if _current_task and not _current_task.done():
            _current_task.cancel()
            _event_bus.publish("run.cancelled", sid=_current_sid)
        return {"cancelled": True}

    # ---------- SSE Event Stream ----------
    @app.get("/api/stream")
    async def stream_events():
        async def event_generator():
            q = _event_bus.subscribe()
            try:
                # Replay recent events
                for evt in _event_bus.history()[-50:]:
                    yield f"data: {json.dumps(evt)}\n\n"
                
                while True:
                    try:
                        item = await asyncio.wait_for(q.get(), timeout=15)
                        yield f"data: {item}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                _event_bus.unsubscribe(q)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"}
        )

    @app.get("/api/events/history")
    async def event_history(limit: int = 100):
        return _event_bus.history()[-limit:]

    # ---------- File Operations ----------
    @app.get("/api/files/list")
    async def api_list_files(path: str = ""):
        try:
            if path:
                result = list_files(path)
            else:
                result = list_files()
            return {"files": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/read")
    async def api_read_file(body: dict):
        try:
            content = read_file(body.get("path", ""))
            return {"content": content}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/write")
    async def api_write_file(body: dict):
        try:
            result = write_file(
                body.get("path", ""),
                body.get("content", ""),
                overwrite=body.get("overwrite", True)
            )
            return {"result": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/create")
    async def api_create_file(body: dict):
        try:
            result = create_file(body.get("path", ""))
            return {"result": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/delete")
    async def api_delete_file(body: dict):
        try:
            result = delete_path(body.get("path", ""))
            return {"result": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/move")
    async def api_move_file(body: dict):
        try:
            result = move_path(body.get("old_path", ""), body.get("new_path", ""))
            return {"result": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/copy")
    async def api_copy_file(body: dict):
        try:
            result = copy_path(body.get("old_path", ""), body.get("new_path", ""))
            return {"result": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/mkdir")
    async def api_mkdir(body: dict):
        try:
            result = make_directory(body.get("path", ""))
            return {"result": result}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/search")
    async def api_search_files(body: dict):
        try:
            results = search_files(
                body.get("query", ""),
                body.get("root", None)
            )
            return {"results": results}
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/files/terminal")
    async def api_terminal(body: dict):
        try:
            result = execute_terminal(
                body.get("command", ""),
                body.get("cwd", None)
            )
            return result
        except Exception as e:
            raise HTTPException(400, str(e))

    # ---------- Knowledge Base ----------
    @app.get("/api/kb/docs")
    async def kb_docs():
        docs = []
        for ext in config.KB_EXTENSIONS:
            for p in config.KNOWLEDGE_DIR.rglob(f"*{ext}"):
                rel = p.relative_to(config.KNOWLEDGE_DIR)
                docs.append(str(rel))
        return {"docs": docs}

    @app.post("/api/kb/add")
    async def kb_add(files: list[UploadFile] = File(...)):
        added = []
        for f in files:
            name = Path(f.filename or "").name
            if not name:
                continue
            ext = Path(name).suffix.lower()
            if ext not in config.KB_EXTENSIONS:
                continue
            dest = config.KNOWLEDGE_DIR / "uploads" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            content = await f.read()
            try:
                dest.write_bytes(content)
                added.append(str(dest.relative_to(config.KNOWLEDGE_DIR)))
            except Exception:
                pass
        return {"added": added}

    @app.get("/api/kb/search")
    async def kb_search(q: str, k: int = 4):
        results = []
        try:
            for ext in config.KB_EXTENSIONS:
                for p in config.KNOWLEDGE_DIR.rglob(f"*{ext}"):
                    try:
                        content = p.read_text(encoding='utf-8', errors='replace')
                        if q.lower() in content.lower():
                            results.append({
                                "doc": str(p.relative_to(config.KNOWLEDGE_DIR)),
                                "score": 1.0,
                                "text": content[:500]
                            })
                    except Exception:
                        continue
            return {"hits": results[:k]}
        except Exception:
            return {"hits": []}

    # ---------- Upload ----------
    @app.post("/api/upload")
    async def upload_file(file: UploadFile = File(...)):
        try:
            data = await file.read()
            result = save_upload(file.filename or "upload.bin", data)
            rel = str(Path(result).relative_to(config.WORKSPACE_DIR)).replace('\\', '/')
            return {"path": rel, "preview_url": f"/api/upload/preview?path={quote(rel)}", "is_image": Path(result).suffix.lower() in config.IMAGE_EXTENSIONS}
        except Exception as e:
            raise HTTPException(400, str(e))

    # ---------- Uploaded image preview ----------
    @app.get("/api/upload/preview")
    async def upload_preview(path: str):
        """Serve an uploaded image back to the chat UI from the safe workspace."""
        try:
            p = config.WORKSPACE_DIR / Path(path)
            p = p.resolve()
            upload_root = config.UPLOAD_DIR.resolve()
            try:
                p.relative_to(upload_root)
            except ValueError:
                raise HTTPException(404, "Image not found")
            if not p.is_file():
                raise HTTPException(404, "Image not found")
            if p.suffix.lower() not in config.IMAGE_EXTENSIONS:
                raise HTTPException(400, "Preview is only available for image files")
            return FileResponse(p)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(404, str(e))

    # ---------- Static Dashboard ----------
    @app.get("/")
    async def serve_index():
        index_path = config.STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return JSONResponse({"error": "Dashboard not found"}, status_code=404)

    app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")

    return app


app = create_app()