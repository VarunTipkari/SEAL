from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class ModelSpec:
    role: str
    name: str
    temperature: float = 0.0

# Model configuration - using your 3 models
MODELS = {
    'vision': ModelSpec('vision', os.getenv('SEAL_VISION_MODEL', 'qwen2.5vl:3b'), 0.1),
    'general': ModelSpec('general', os.getenv('SEAL_GENERAL_MODEL', 'llama3.2:3b'), 0.2),
    'file_manager': ModelSpec('file_manager', os.getenv('SEAL_FILE_MODEL', 'llama3.2:3b'), 0.2),
    'coding': ModelSpec('coding', os.getenv('SEAL_CODING_MODEL', 'qwen2.5-coder:1.5b'), 0.0),
}

APP_NAME = 'SEAL AI'
WORKSPACE_DIR = Path(os.getenv('SEAL_WORKSPACE', 'workspace')).expanduser().resolve()
UPLOAD_DIR = WORKSPACE_DIR / '_inbox'
CHAT_DIR = WORKSPACE_DIR / '_chats'
KNOWLEDGE_DIR = Path('knowledge').resolve()
STATIC_DIR = Path('dashboard/static').resolve()

MAX_FILE_CHARS = 20000
MAX_CONTEXT_CHARS = 30000
MAX_CHAT_MESSAGES = 40
TERMINAL_TIMEOUT_SECONDS = 15

def _roots():
    raw = os.getenv('SEAL_ALLOWED_ROOTS', '')
    if raw.strip():
        return [Path(x).expanduser().resolve() for x in raw.split(';') if x.strip()]
    home = Path.home().resolve()
    roots = [WORKSPACE_DIR]
    # On Windows, allow the user's system drive for explicit local file requests
    # such as C:/8086/sample.txt. Additional roots can still be supplied with
    # SEAL_ALLOWED_ROOTS (semicolon-separated).
    if os.name == 'nt':
        system_drive = os.environ.get('SystemDrive', 'C:')
        roots.append(Path(system_drive + os.sep))
    for name in ('Desktop', 'Documents', 'Downloads'):
        p = home / name
        if p.exists():
            roots.append(p)
    return roots

ALLOWED_ROOTS = _roots()

# Create necessary directories
for d in (WORKSPACE_DIR, UPLOAD_DIR, CHAT_DIR, KNOWLEDGE_DIR, STATIC_DIR):
    d.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml', '.csv', '.html', '.css', '.sql', '.xml', '.ini', '.toml', '.bat', '.sh', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.java', '.go', '.rs', '.ps1'}
UPLOAD_EXTENSIONS = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | {'.pdf', '.docx'}

# Knowledge base extensions
KB_EXTENSIONS = {'.md', '.txt', '.csv'}