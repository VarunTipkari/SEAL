from __future__ import annotations
import json,uuid
from datetime import datetime,timezone
from .config import CHAT_DIR,MAX_CHAT_MESSAGES

def new_chat_id(): return uuid.uuid4().hex[:12]
def _path(cid): return CHAT_DIR/(''.join(c for c in str(cid) if c.isalnum())+'.json')
def make_title(text):
    x=' '.join(str(text or '').split()); return (x[:42]+'…') if len(x)>42 else (x or 'New chat')
def save_chat(cid,title,messages):
    p=_path(cid); now=datetime.now(timezone.utc).isoformat(); created=now
    if p.exists():
        try: created=json.loads(p.read_text(encoding='utf-8')).get('created_at',now)
        except Exception: pass
    p.write_text(json.dumps({'id':cid,'title':title or 'New chat','created_at':created,'updated_at':now,'messages':messages[-MAX_CHAT_MESSAGES:]},ensure_ascii=False,indent=2),encoding='utf-8')
def load_chat(cid):
    p=_path(cid)
    if not p.exists(): return None
    try:return json.loads(p.read_text(encoding='utf-8'))
    except Exception:return None
def list_chats():
    out=[]
    for p in CHAT_DIR.glob('*.json'):
        try:
            d=json.loads(p.read_text(encoding='utf-8')); out.append({'id':d.get('id',p.stem),'title':d.get('title') or 'New chat','updated_at':d.get('updated_at','')})
        except Exception:pass
    return sorted(out,key=lambda x:x['updated_at'],reverse=True)
def delete_chat(cid):
    p=_path(cid)
    if p.exists():p.unlink()
