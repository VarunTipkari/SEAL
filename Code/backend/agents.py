from __future__ import annotations
import json
import re
from pathlib import Path
from .config import MODELS, MAX_CONTEXT_CHARS
from .file_manager import FILE_COMMANDS

ALLOWED_ACTIONS = {
    'list', 'read', 'search', 'write', 'create_file', 'generate_file',
    'modify', 'delete', 'rename', 'move', 'copy', 'mkdir', 'terminal'
}


def strip_private(x):
    """Remove thinking tags and extract the actual answer."""
    text = str(x or '')
    # Remove <think>...</think> blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.I | re.S)
    # Also remove thinking tags if present (Chinese variant)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.I | re.S)
    # Remove common thinking prefixes
    text = re.sub(r'^(?:Let me think|I\'ll think|Thinking|思考中).*?\n', '', text, flags=re.I)
    # Remove empty lines at start/end
    text = text.strip()
    return text


def extract_json(text):
    x = strip_private(text)
    candidates = re.findall(r'```json\s*(.*?)\s*```', x, re.I | re.S) + [x]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return None


def conversation_messages(history, current_prompt, max_messages=20):
    """Build ChatGPT-style current-conversation context for the local model.

    The server owns the conversation history. Every model call receives the
    recent user/assistant turns, followed by the new user message.
    """
    messages = []
    for item in (history or [])[-max_messages:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        text = str(item.get('text') or item.get('content') or '').strip()
        if role not in {'user', 'assistant'} or not text:
            continue
        # Keep attachment information lightweight; actual current images are
        # supplied separately to the vision model.
        attachments = item.get('attachments') or []
        image_names = [str(a.get('name') or 'image') for a in attachments
                       if isinstance(a, dict) and a.get('isImage')]
        if image_names:
            text += '\n[Previous image attachment: ' + ', '.join(image_names) + ']'
        messages.append({'role': role, 'content': text})
    messages.append({'role': 'user', 'content': current_prompt})
    return messages


def history_text(history, max_messages=12):
    return '\n'.join(
        f"{m.get('role','').upper()}: {m.get('text','')}"
        for m in (history or [])[-max_messages:]
        if isinstance(m, dict) and m.get('text')
    )


def route_task(prompt, has_image=False, history=None):
    # The latest user turn determines the task type. History is used only to
    # resolve follow-ups, not to accidentally turn a new coding question into a file task.
    cur = (prompt or '').lower()
    recent = history_text(history, 8).lower()
    file_words = r'\b(file|folder|directory|desktop|download|document|workspace|terminal|path)\b'
    action_words = r'\b(create|make|write|generate|read|open|view|delete|remove|rename|move|copy|list|show|find|search|edit|modify|update|append|prepend|mkdir|touch|terminal)\b'
    coding_words = r'\b(code|coding|program|programming|algorithm|solve|solution|debug|bug|error|leetcode|hackerrank|function|class|python|javascript|typescript|java|c\+\+|cpp|sql|html|css|react|node|api|django|flask)\b'
    code_file = r'\b[\w.-]+\.(py|js|ts|tsx|jsx|json|sql|cpp|cc|cxx|h|hpp|java|go|rs|html|css|bat|sh|ps1)\b'

    if has_image and (re.search(coding_words, cur) or re.search(code_file, cur)):
        return 'vision_coding'
    if has_image and not re.search(action_words, cur):
        return 'vision'

    # Explicit file/folder operations are General/Llama.
    if re.search(action_words, cur) and re.search(file_words, cur):
        return 'file_manager'
    # A filename alone with a file-creation verb is also a file operation.
    if re.search(r'\b(?:create|make|generate|write|save)\b', cur) and re.search(code_file, cur) and not re.search(coding_words, cur):
        return 'file_manager'

    # Real programming requests use the Coding model.
    if re.search(coding_words, cur) or re.search(code_file, cur):
        return 'coding'

    # Contextual follow-ups can refer to a previously created file/folder.
    if re.search(r'\b(?:above|previous|that|same)\s+(?:file|folder|directory|path)\b', cur) and recent:
        if re.search(action_words, cur):
            return 'file_manager'

    return 'general'


def vision_agent(manager, image, instruction):
    """Analyze an uploaded image and create a structured handoff for the general model."""
    if not image:
        raise ValueError(
            "Vision was selected, but no image data was loaded. "
            "Please re-upload the image and try again."
        )
    if isinstance(image, str):
        # Accept a path as a defensive fallback for callers outside the HTTP route.
        from pathlib import Path
        image = Path(image).read_bytes()
    if not isinstance(image, (bytes, bytearray)):
        raise TypeError(f"Unsupported vision image type: {type(image).__name__}")
    image = bytes(image)
    if len(image) < 16:
        raise ValueError("The uploaded image is empty or too small to analyze.")

    messages = [
        {
            'role': 'system',
            'content': (
                'Analyze only the visible contents of the image. Do not identify people. '
                'Return JSON with these keys: summary, visible_text, ui_elements, layout, '
                'requirements_for_responder.'
            ),
        },
        {'role': 'user', 'content': instruction or 'Describe and analyze this image.'},
    ]

    # Some Ollama/model combinations reject JSON format together with vision input.
    # Try structured JSON first, then fall back to normal vision output and parse it.
    try:
        raw = manager.chat(
            'vision', messages, images=[image], json_mode=True
        )
    except Exception as first_error:
        manager.emit(
            'vision_retry',
            f'Vision JSON mode failed; retrying without JSON format · {first_error}',
            'vision',
            MODELS['vision'].name,
        )
        raw = manager.chat(
            'vision', messages, images=[image], json_mode=False
        )

    data = extract_json(raw) or {
        'summary': strip_private(raw),
        'visible_text': [],
        'ui_elements': [],
        'layout': '',
        'requirements_for_responder': [],
    }
    return {
        'type': 'vision_handoff',
        'producer': 'vision',
        'model': MODELS['vision'].name,
        'data': data,
    }


def coding_agent(manager, instruction, handoffs, file_only=False, history=None):
    """Coding specialist with the current conversation included in its context."""
    context = json.dumps(handoffs, ensure_ascii=False, indent=2)[-MAX_CONTEXT_CHARS:]
    system = (
        "You are SEAL AI's coding specialist. Follow the current conversation context and the user's latest request. "
        "When a Vision handoff exists, treat it as the source of truth for the visible problem. "
        "Solve the actual programming problem; do not invent requirements. "
        + ("Return ONLY complete source code. No markdown fences, explanation, placeholders, TODO, pass, pseudo-code, or ellipses."
           if file_only else
           "Give a concise solution, algorithm, complexity, and complete code. Never expose internal reasoning or <think> tags.")
    )
    messages = conversation_messages(history, instruction, max_messages=20)
    if context:
        messages[-1]['content'] += f'\n\nVISION HANDOFF:\n{context}'
    raw = manager.chat('coding', [{'role':'system','content':system}] + messages, json_mode=False)
    return strip_private(raw).strip()


def general_agent(manager, instruction, handoffs, history=None):
    """General Llama agent using the full recent current-chat context."""
    context = json.dumps(handoffs, ensure_ascii=False, indent=2)[-MAX_CONTEXT_CHARS:] if handoffs else ''
    system_prompt = (
        'You are SEAL AI, a helpful assistant running locally. ' 
        'Use the conversation history as memory for this current chat. ' 
        'Answer the latest user message in context, and do not ask the user to repeat information already present. ' 
        'Answer directly and clearly. Do not use <think> tags or expose hidden reasoning. ' 
        'File operations are handled by the General/Llama lane.'
    )
    messages = conversation_messages(history, instruction, max_messages=20)
    if context:
        messages[-1]['content'] += f'\n\nAGENT CONTEXT:\n{context}'
    raw = manager.chat('general', [{'role':'system','content':system_prompt}] + messages, json_mode=False)
    cleaned = strip_private(raw)
    if not cleaned or len(cleaned) < 3:
        cleaned = "I couldn't generate a response. Please try again."
    return {'answer': cleaned, 'model': MODELS['general'].name}


def _paths(prompt):
    # Prefer quoted paths, then common Windows/POSIX paths and filenames.
    values = re.findall(r'["\'`]([^"\'`]+)["\'`]', prompt)
    values += re.findall(r'(?:[A-Za-z]:[\\/][^\s,;]+|~[\\/][^\s,;]+|(?:\.\.?[\\/])[^\s,;]+|[\w.@%+~-]+(?:[\\/][\w.@%+~-]+)*\.[A-Za-z0-9]{1,8})', prompt)
    out = []
    for value in values:
        value = value.strip().strip('.,:;()[]{}')
        if value and value not in out:
            out.append(value)
    return out


def _infer_generated_path(prompt):
    """Infer a safe default filename when the user asks for a file but gives no name."""
    low = prompt.lower()
    paths = _paths(prompt)
    if paths:
        return paths[0]
    if re.search(r'\breadme\b', low): return 'README.md'
    if re.search(r'\bjson\b', low): return 'generated.json'
    if re.search(r'\bcsv\b', low): return 'generated.csv'
    if re.search(r'\bhtml\b', low): return 'index.html'
    if re.search(r'\bcss\b', low): return 'styles.css'
    if re.search(r'\bjavascript\b|\bjs\b', low): return 'generated.js'
    if re.search(r'\btypescript\b|\bts\b', low): return 'generated.ts'
    if re.search(r'c\+\+|\bcpp\b', low):
        return 'palindrome.cpp' if 'palindrom' in low else 'generated.cpp'
    if re.search(r'\bpython\b|\bpy\b', low):
        return 'palindrome.py' if 'palindrom' in low else 'generated.py'
    if re.search(r'\bjava\b', low): return 'Generated.java'
    if re.search(r'\bgo\b', low): return 'generated.go'
    if re.search(r'\brust\b|\brs\b', low): return 'generated.rs'
    if re.search(r'\bsql\b', low): return 'generated.sql'
    return 'generated.txt'


def _op(action, path='', new='', query='', content='', instruction='', command='', cwd='', overwrite=True):
    return {
        'action': action,
        'path': path,
        'new_path': new,
        'query': query,
        'content': content,
        'instruction': instruction,
        'command': command,
        'cwd': cwd,
        'overwrite': bool(overwrite),
    }


def _contextual_path(path, prompt, history=None):
    """Resolve follow-up phrases such as 'inside the above folder' from the current chat.

    Relative paths stay inside SEAL's workspace. If the latest conversation established a
    folder and the user says 'inside above folder', place the new file there.
    """
    raw = str(path or '').strip().strip('"').strip("'")
    if not raw or Path(raw).is_absolute():
        return raw
    low = str(prompt or '').lower()
    if not re.search(r'\b(?:inside|within|in)\s+(?:the\s+)?(?:above|previous|that|same)\s+(?:folder|directory)\b', low):
        return raw
    hist = history_text(history, 12)
    candidates = re.findall(
        r'(?i)\b(?:the\s+)?([A-Za-z0-9_.-]+)\s+(?:folder|directory)\s+(?:was\s+)?(?:created|made|exists|is)',
        hist,
    )
    if not candidates:
        candidates = re.findall(
            r'(?i)\b(?:create|make|new)\s+(?:a\s+)?(?:folder|directory)\s+(?:called|named)?\s*[`\"\']?([A-Za-z0-9_.-]+)',
            hist,
        )
    if not candidates:
        candidates = re.findall(r'(?i)\b(?:folder|directory)\s+[`\"\']?([A-Za-z0-9_.-]+)', hist)
    if candidates:
        folder = candidates[-1].strip()
        if folder and folder.lower() not in {'folder', 'directory'}:
            return str(Path(folder) / raw).replace('\\', '/')
    return raw


def _deterministic_file_ops(prompt, history=None):
    """High-confidence parser for common local file/folder requests.

    This is deliberately conservative. The model planner is used for requests that
    cannot be identified reliably from the wording alone.
    """
    low = prompt.lower()
    paths = _paths(prompt)
    ops = []

    if re.search(r'\b(list|show)\b', low) and re.search(r'\b(files?|folders?|directories?)\b', low):
        return [_op('list')]

    if re.search(r'\b(search|find|look for)\b', low) and re.search(r'\b(files?|folders?|directories?|text|content|inside)\b', low):
        query = paths[0] if paths and '.' not in paths[0] else re.sub(
            r'(?i)^.*?\b(?:search|find|look for)\b\s*', '', prompt
        ).strip(' .,:;')
        return [_op('search', query=query)] if query else []

    if re.search(r'\b(rename|ren)\b', low) and len(paths) >= 2:
        return [_op('rename', paths[0], new=paths[1])]

    if re.search(r'\b(move|mv)\b', low) and len(paths) >= 2:
        return [_op('move', paths[0], new=paths[1])]

    if re.search(r'\b(copy|cp)\b', low) and len(paths) >= 2:
        return [_op('copy', paths[0], new=paths[1])]

    if re.search(r'\b(delete|remove|erase|trash)\b', low) and paths:
        return [_op('delete', paths[0])]

    if (re.search(r'\b(create|make|new)\b', low) and
        re.search(r'\b(?:folder|directory)\b', low) and
        not re.search(r'\b(?:above|previous|that|same)\s+(?:folder|directory)\b', low)):
        # Match only a real folder-creation request, not a follow-up such as
        # 'inside the above folder create sample.py'.
        match = re.search(r'(?i)\b(?:create|make|new)\s+(?:a\s+)?(?:folder|directory)\s+(?:called|named)?\s*["\'`]?([A-Za-z0-9_. -]+?)["\'`]?(?:\s+in\s+.+)?$', prompt)
        if not match:
            match = re.search(r'(?i)\b(?:folder|directory)\b\s+(?:called|named)?\s*["\'`]?([A-Za-z0-9_.-]+)', prompt)
        name = match.group(1).strip() if match else ''
        return [_op('mkdir', name)] if name else []

    # Read/open a file before generation checks.
    if re.search(r'\b(read|open|view|display|show)\b', low) and paths:
        return [_op('read', paths[0])]

    # Explicit content supplied by the user: write it exactly as given.
    content_match = re.search(
        r'(?is)\b(?:containing|content is|with content|contents? is)\s*[:=]?\s*["\'`](.*?)["\'`]\s*$',
        prompt,
    )
    if paths and content_match and re.search(r'\b(create|make|write|save|generate)\b', low):
        return [_op('write', paths[0], content=content_match.group(1), overwrite=True)]

    # Creating/generating a file without a filename gets a sensible default name.
    if re.search(r'\b(create|make|write|save|generate)\b', low) and re.search(r'\bfile\b', low):
        path = paths[0] if paths else _infer_generated_path(prompt)
        path = _contextual_path(path, prompt, history)
        return [_op('generate_file', path, instruction=prompt, overwrite=True)]

    # Natural-language modification: "modify app.py to ...", "edit README.md ...".
    if paths and re.search(r'\b(edit|modify|update|change|rewrite|append|prepend)\b', low):
        instruction = prompt
        return [_op('modify', paths[0], instruction=instruction, overwrite=True)]

    # A direct terminal command is allowed only through the safe terminal adapter.
    if re.search(r'\b(?:run|execute)\s+(?:the\s+)?(?:terminal|command)\b', low):
        match = re.search(r'(?is)\b(?:terminal|command)\b\s*[:=]?\s*["\'`](.*?)["\'`]\s*$', prompt)
        if match:
            return [_op('terminal', command=match.group(1))]

    return ops


def file_operation_plan(manager, prompt, listing, history=None):
    deterministic = _deterministic_file_ops(prompt, history)
    if deterministic:
        return deterministic

    # Use the general Llama model as the file-operation intent/planning model.
    system = (
        'Return JSON only. Schema: {"operations":[...]} . '
        f'Allowed actions: {sorted(ALLOWED_ACTIONS)}. '
        'Each operation may contain action,path,new_path,query,content,instruction,command,cwd,overwrite. '
        'For a request to create/generate a file without explicit content, use action generate_file and put '
        'the requested specification in instruction. For modifying an existing file, use modify with path '
        'and the exact requested change in instruction. Do not invent paths. '
        f'Terminal command must be one simple file/folder command from {sorted(FILE_COMMANDS)}. '
        'No network, package installation, code execution, registry changes, process control, or arbitrary shell.'
    )
    try:
        raw = manager.chat(
            'file_manager',
            [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': (
                    'CURRENT CONVERSATION:\n' + history_text(history, 12) +
                    '\n\nLATEST REQUEST:\n' + prompt +
                    '\n\nCURRENT WORKSPACE FILES:\n' + json.dumps(listing[:300], ensure_ascii=False)
                )},
            ],
            json_mode=True,
        )
        data = extract_json(raw) or {}
        model_ops = data.get('operations', []) if isinstance(data.get('operations', []), list) else []
        clean = []
        for item in model_ops:
            if not isinstance(item, dict) or item.get('action') not in ALLOWED_ACTIONS:
                continue
            action = item.get('action', '')
            path = str(item.get('path') or '')
            if action in {'generate_file', 'create_file', 'write'} and not path:
                path = _infer_generated_path(prompt)
            clean.append(_op(
                action,
                path,
                str(item.get('new_path') or ''),
                str(item.get('query') or ''),
                str(item.get('content') or ''),
                str(item.get('instruction') or prompt),
                str(item.get('command') or ''),
                str(item.get('cwd') or ''),
                item.get('overwrite', True),
            ))
        if clean:
            return clean
        if re.search(r'\b(generate|create|make|write|save)\b', prompt.lower()) and re.search(r'\bfile\b', prompt.lower()):
            return [_op('generate_file', _contextual_path(_infer_generated_path(prompt), prompt, history), instruction=prompt, overwrite=True)]
        return []
    except Exception:
        return []


def _clean_generated_file(text):
    value = strip_private(text).strip()
    fenced = re.search(r'```(?:[A-Za-z0-9_+.-]+)?\s*(.*?)\s*```', value, re.S)
    if fenced:
        value = fenced.group(1).strip()
    return value


def generate_file_content(manager, path, instruction, existing_content=None):
    ext = re.search(r'\.([A-Za-z0-9]{1,8})$', path or '')
    extension = (ext.group(1).lower() if ext else 'txt')
    context = ''
    if existing_content is not None:
        context = f'\n\nEXISTING FILE CONTENT:\n{existing_content}'
    raw = manager.chat(
        'file_manager',
        [
            {
                'role': 'system',
                'content': (
                    'Generate complete file content for SEAL. Return ONLY the file content, with no markdown fences, '
                    'explanation, or hidden reasoning. Do not use placeholders such as TODO, pass, "add code here", '
                    'or ellipses unless the user explicitly asks for them. Preserve existing behavior when modifying '
                    'a file and implement the requested change completely. Target file extension: .' + extension
                ),
            },
            {'role': 'user', 'content': f'FILE PATH: {path}\nREQUEST: {instruction}{context}'},
        ],
    )
    return _clean_generated_file(raw)