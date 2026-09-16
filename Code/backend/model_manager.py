from __future__ import annotations
from dataclasses import dataclass,field
import time
from typing import Callable,Optional
import base64
from .config import MODELS
@dataclass
class RuntimeEvent:
    kind:str; message:str; role:str=''; model:str=''; timestamp:float=field(default_factory=time.time)
class ModelManager:
    def __init__(self,callback:Optional[Callable[[RuntimeEvent],None]]=None): self.callback=callback
    def _display_role(self, role):
        # File management is intentionally powered by Llama, but it is part of
        # the General lane in the UI. Coding gets its own visible lane.
        return 'general' if role == 'file_manager' else role

    def emit(self, kind, message, role='', model=''):
        display_role = self._display_role(role)
        print(f"[SEAL] [{kind}] {message}", flush=True)

        if self.callback:
            self.callback(
                RuntimeEvent(kind, message, display_role, model)
            )
    def model_name(self,role):
        # File operations intentionally use the General/Llama model.
        if role == 'file_manager':
            return MODELS['general'].name
        return MODELS[role].name
    def chat(self,role,messages,images=None,json_mode=False):
        spec=MODELS[role]; self.emit('model_start',f'{role.title()} · {spec.name}',role,spec.name)
        payload=[dict(m) for m in messages]
        if images:
            if not payload:
                raise ValueError('Cannot attach images without a message payload.')
            normalized_images = []
            for image in images:
                if isinstance(image, (bytes, bytearray)):
                    # Base64 is accepted reliably across Ollama Python versions
                    # and avoids transport/serialization ambiguity with raw PNG/JPEG bytes.
                    normalized_images.append(base64.b64encode(bytes(image)).decode('ascii'))
                elif isinstance(image, str):
                    # Ollama also accepts base64 image strings. Keep those unchanged.
                    normalized_images.append(image)
                else:
                    raise TypeError(f'Unsupported image type: {type(image).__name__}')
            payload[-1]=dict(payload[-1]); payload[-1]['images']=normalized_images
        kwargs={'model':spec.name,'messages':payload,'options':{'temperature':spec.temperature},'keep_alive':0}
        if json_mode: kwargs['format']='json'
        try:
            self.emit('thinking',f'{role.title()} is processing · {spec.name}',role,spec.name)
            if images:
                total = sum(len(x) for x in images if isinstance(x, (bytes, bytearray)))
                self.emit('vision_payload', f'Attached {len(images)} image(s)' + (f' · {total:,} bytes' if total else ''), role, spec.name)
            import ollama
            response=ollama.chat(**kwargs); content=(response.get('message') or {}).get('content','') or ''
            self.emit('model_done',f'{role.title()} completed · {spec.name}',role,spec.name); return content.strip()
        except Exception as exc:
            self.emit('error',f'{role.title()} failed · {exc}',role,spec.name); raise
