from __future__ import annotations
from .agents import route_task, vision_agent, coding_agent, general_agent, file_operation_plan, generate_file_content, _infer_generated_path, _clean_generated_file
from .file_manager import (
    list_files, read_file, search_files, write_file, create_file, delete_path,
    move_path, copy_path, make_directory, execute_terminal,
)
from .model_manager import ModelManager


def _operation(manager, item):
    action = item.get('action', '')
    if action in {'read','write','create_file','generate_file','modify','delete','rename','move','copy','mkdir'} and not str(item.get('path') or '').strip():
        raise ValueError('Path is empty.')
    if action == 'list':
        return list_files(item.get('path') or None)
    if action == 'read':
        return read_file(item['path'])
    if action == 'search':
        return search_files(item['query'], item.get('path') or None)
    if action == 'write':
        return write_file(item['path'], item.get('content', ''), overwrite=bool(item.get('overwrite', True)))
    if action == 'create_file':
        return create_file(item['path'])
    if action == 'generate_file':
        content = generate_file_content(manager, item['path'], item.get('instruction') or item.get('path', ''))
        if not content:
            raise ValueError('The file-generation model returned empty content.')
        return write_file(item['path'], content, overwrite=bool(item.get('overwrite', True)))
    if action == 'modify':
        old = read_file(item['path'])
        content = generate_file_content(manager, item['path'], item.get('instruction') or 'Modify the file as requested.', existing_content=old)
        if not content:
            raise ValueError('The file-modification model returned empty content.')
        return write_file(item['path'], content, overwrite=True)
    if action == 'delete':
        return delete_path(item['path'])
    if action in ('rename', 'move'):
        return move_path(item['path'], item['new_path'])
    if action == 'copy':
        return copy_path(item['path'], item['new_path'])
    if action == 'mkdir':
        return make_directory(item['path'])
    if action == 'terminal':
        return execute_terminal(item['command'], item.get('cwd') or None)
    raise ValueError(f'Unsupported file action: {action}')


def run(state):
    manager = state.get('runtime_manager') or ModelManager(state.get('event_callback'))
    prompt = state['user_prompt']
    handoffs = []
    history = state.get('history') or []
    route = route_task(prompt, bool(state.get('has_image')), history)
    state['route'] = route
    route_role = 'vision' if route == 'vision_coding' else route
    manager.emit('route', f'Route → {route}', route_role, manager.model_name(route_role))

    if route in {'vision', 'vision_coding'}:
        image = state.get('image_bytes')
        if not image:
            raise ValueError('Vision route selected, but the image could not be loaded. Please upload the image again.')
        handoff = vision_agent(manager, image, prompt)
        handoffs.append(handoff)

        if route == 'vision_coding':
            manager.emit('handoff', 'Vision → Coding: structured problem transferred', 'coding', manager.model_name('coding'))
            import re
            wants_file = bool(re.search(r'\b(create|make|write|save|generate)\b.*\bfile\b|\bfile\b.*\b(create|make|write|save|generate)\b', prompt.lower()))
            if wants_file:
                path = _infer_generated_path(prompt)
                manager.emit('handoff', f'Vision → Coding → File: generating {path}', 'coding', manager.model_name('coding'))
                content = _clean_generated_file(coding_agent(manager, prompt, handoffs, file_only=True, history=history))
                if not content or len(content) < 10:
                    raise ValueError('Coding model returned empty/incomplete file content. File was not written.')
                low = content.lower()[:220]
                if any(x in low for x in ('here is the code', "here's the code", 'sure,', 'as an ai', 'i cannot')):
                    raise ValueError('Coding model returned conversational text instead of source code. File was not written.')
                written = write_file(path, content, overwrite=True)
                manager.emit('operation', f'✓ generated {path}', 'file_manager', manager.model_name('file_manager'))
                answer = f'Created `{path}` with the solution extracted from the image.'
                state.update(answer=answer, final_answer=answer, model=manager.model_name('coding'), handoffs=handoffs, artifacts=[{'action':'generate_file','path':path,'success':True,'result':written}])
            else:
                result_text = coding_agent(manager, prompt, handoffs, file_only=False, history=history)
                state.update(answer=result_text, final_answer=result_text, model=manager.model_name('coding'), handoffs=handoffs, artifacts=[])
            state.pop('image_bytes', None)
            return state

        manager.emit('handoff', 'Vision → General: visual evidence transferred', 'vision', manager.model_name('vision'))
        result = general_agent(manager, prompt, handoffs, history=history)
        state.update(answer=result['answer'], final_answer=result['answer'], model=result['model'], handoffs=handoffs, artifacts=[])
        state.pop('image_bytes', None)
        return state

    if route == 'coding':
        manager.emit('handoff', 'Coding task → Coding model', 'coding', manager.model_name('coding'))
        result_text = coding_agent(manager, prompt, handoffs, file_only=False, history=history)
        state.update(
            answer=result_text,
            final_answer=result_text,
            model=manager.model_name('coding'),
            handoffs=handoffs,
            artifacts=[]
        )
        return state

    if route == 'file_manager':
        ops = file_operation_plan(manager, prompt, list_files(), history=history)
        results = []
        for item in ops:
            try:
                value = _operation(manager, item)
                # Never claim a filesystem mutation succeeded unless the target exists.
                if item['action'] in {'create_file','generate_file','write','modify','mkdir'}:
                    from .file_manager import safe_path
                    target = safe_path(item.get('path',''))
                    if not target.exists():
                        raise IOError(f"Operation reported success but target was not created: {target}")
                elif item['action'] in {'move','copy','rename'}:
                    from .file_manager import safe_path
                    target = safe_path(item.get('new_path',''))
                    if not target.exists():
                        raise IOError(f"Operation reported success but destination was not created: {target}")
                results.append({'action': item['action'], 'path': item.get('path', ''), 'success': True, 'result': value})
                manager.emit('operation', f"✓ {item['action']} completed", 'general', manager.model_name('general'))
            except Exception as exc:
                results.append({'action': item.get('action'), 'path': item.get('path', ''), 'success': False, 'error': str(exc)})
                manager.emit('operation_error', f"✕ {item.get('action')} · {exc}", 'general', manager.model_name('general'))

        state['operations'] = ops
        state['operation_results'] = results
        state['model'] = manager.model_name('general')
        state['artifacts'] = results
        
        succeeded = sum(1 for result in results if result['success'])
        failed = len(results) - succeeded
        
        if not results:
            answer = (
                "I couldn't identify a safe file/folder operation from that request. "
                "Try a request such as 'create project/hello.py', 'modify project/app.py', "
                "'rename a.txt to b.txt', or 'move folder A to folder B'."
            )
        elif failed:
            failed_items = [
                f"{r.get('action', 'operation').replace('_', ' ')} on {r.get('path', '')}: {r.get('error', 'Unknown error')}"
                for r in results if not r.get('success')
            ]
            answer = f"I completed {succeeded} of {len(results)} file operation(s). {failed} failed."
            if failed_items:
                answer += " " + " | ".join(failed_items)
        else:
            completed_items = [
                f"{r.get('action', 'operation').replace('_', ' ')} on {r.get('path', '')} ({r.get('result')})"
                for r in results if r.get('success')
            ]
            answer = f"Done — {succeeded} file operation(s) completed successfully."
            if completed_items:
                answer += " " + " | ".join(completed_items)
        
        state['answer'] = answer
        state['final_answer'] = answer  # Add this
        return state

    # General chat
    result = general_agent(manager, prompt, [], history=history)
    state.update(
        answer=result['answer'],
        final_answer=result['answer'],  # Add this
        model=result['model'],
        artifacts=[]
    )
    return state