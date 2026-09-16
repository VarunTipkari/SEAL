from __future__ import annotations
import os,re,shutil,subprocess,shlex
from pathlib import Path
from .config import ALLOWED_ROOTS,WORKSPACE_DIR,UPLOAD_DIR,MAX_FILE_CHARS,TEXT_EXTENSIONS,TERMINAL_TIMEOUT_SECONDS
DANGEROUS=re.compile(r'\b(format|diskpart|shutdown|reboot|reg\s+delete|cipher\s+/w|del\s+/s\s+/q|rm\s+-rf\s+/|sudo|powershell\s+-enc)\b',re.I)
FILE_COMMANDS={'dir','ls','pwd','cd','tree','mkdir','md','touch','type','cat','copy','cp','move','mv','ren','rename','del','rm','rmdir'}
def _within(p,r):
    try:p.resolve().relative_to(r.resolve());return True
    except ValueError:return False
def _allowed(p):return any(_within(p,r) for r in ALLOWED_ROOTS)
def safe_path(path,base=None):
    raw=str(path or '').strip().strip('"').strip("'")
    if not raw:raise ValueError('Path is empty.')
    p=Path(os.path.expandvars(os.path.expanduser(raw)))
    if not p.is_absolute():p=(base or WORKSPACE_DIR)/p
    p=p.resolve()
    if not _allowed(p):raise ValueError("Path is outside SEAL's allowed local folders.")
    return p
def list_files(path=None):
    root=safe_path(path,WORKSPACE_DIR) if path else WORKSPACE_DIR
    return sorted(str(p.relative_to(root)).replace('\\','/') for p in root.rglob('*') if p.is_file()) if root.exists() else []
def read_file(path):
    p=safe_path(path)
    if not p.is_file():raise FileNotFoundError(path)
    x=p.read_text(encoding='utf-8',errors='replace');return x[:MAX_FILE_CHARS]+('\n…[truncated]' if len(x)>MAX_FILE_CHARS else '')
def write_file(path,content,overwrite=True):
    p=safe_path(path)
    if p.exists() and not overwrite:raise FileExistsError(path)
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(content),encoding='utf-8');return str(p)
def create_file(path):
    p=safe_path(path)
    if p.exists():raise FileExistsError(path)
    p.parent.mkdir(parents=True,exist_ok=True);p.touch();return str(p)
def make_directory(path):p=safe_path(path);p.mkdir(parents=True,exist_ok=True);return str(p)
def delete_path(path):
    p=safe_path(path)
    if p==WORKSPACE_DIR:raise ValueError('Refusing to delete workspace root.')
    if p.is_dir():shutil.rmtree(p)
    elif p.is_file():p.unlink()
    else:raise FileNotFoundError(path)
    return str(p)
def move_path(old,new):
    a,b=safe_path(old),safe_path(new)
    if not a.exists():raise FileNotFoundError(old)
    if b.exists():raise FileExistsError(new)
    b.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(a),str(b));return str(b)
def copy_path(old,new):
    a,b=safe_path(old),safe_path(new)
    if not a.exists():raise FileNotFoundError(old)
    if b.exists():raise FileExistsError(new)
    b.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(a,b) if a.is_dir() else shutil.copy2(a,b);return str(b)
def search_files(query,root=None):
    q=str(query or '').lower().strip()
    if not q:raise ValueError('Search query cannot be empty.')
    base=safe_path(root) if root else WORKSPACE_DIR;hits=[]
    for p in base.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXTENSIONS:continue
        try:x=p.read_text(encoding='utf-8',errors='replace')
        except OSError:continue
        low=x.lower();pos=low.find(q)
        if q in str(p).lower() or pos>=0:hits.append({'path':str(p),'snippet':x[max(0,pos-160):max(0,pos-160)+700]});
        if len(hits)>=30:break
    return hits
def execute_terminal(command,cwd=None):
    """Execute only file/folder terminal semantics without shell=True."""
    cmd=str(command or '').strip()
    if not cmd: raise ValueError('Terminal command is empty.')
    if DANGEROUS.search(cmd): raise PermissionError('This terminal command is blocked by SEAL safety rules.')
    parts=shlex.split(cmd,posix=False)
    if not parts: raise ValueError('Terminal command is empty.')
    exe=Path(parts[0]).name.lower()
    if exe not in FILE_COMMANDS: raise PermissionError('Only file/folder terminal commands are allowed.')
    args=[x.strip('"') for x in parts[1:]]
    work=safe_path(cwd) if cwd else WORKSPACE_DIR
    if exe in {'pwd'}: return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':str(work)+'\n','stderr':''}
    if exe in {'cd'}:
        target=safe_path(args[0],work) if args else work
        if not target.is_dir(): raise NotADirectoryError(args[0] if args else str(work))
        return {'command':cmd,'cwd':str(target),'returncode':0,'stdout':str(target)+'\n','stderr':''}
    if exe in {'dir','ls'}:
        target=safe_path(args[0],work) if args else work
        if not target.is_dir(): raise NotADirectoryError(str(target))
        rows=[]
        for x in sorted(target.iterdir(),key=lambda z:(not z.is_dir(),z.name.lower())):
            rows.append(('📁 ' if x.is_dir() else '📄 ')+x.name)
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':'\n'.join(rows)+'\n','stderr':''}
    if exe=='tree':
        target=safe_path(args[0],work) if args else work
        rows=[str(target)]
        for x in sorted(target.rglob('*'),key=lambda z:str(z).lower()):
            rows.append(('  ' if x.parent==target else '    ')+('📁 ' if x.is_dir() else '📄 ')+str(x.relative_to(target)))
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':'\n'.join(rows)+'\n','stderr':''}
    if exe in {'mkdir','md'}:
        if not args: raise ValueError('mkdir needs a path')
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':make_directory(args[0])+'\n','stderr':''}
    if exe=='touch':
        if not args: raise ValueError('touch needs a path')
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':create_file(args[0])+'\n','stderr':''}
    if exe in {'type','cat'}:
        if not args: raise ValueError('type/cat needs a file')
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':read_file(args[0])+'\n','stderr':''}
    if exe in {'del','rm','rmdir'}:
        if not args: raise ValueError('delete needs a path')
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':delete_path(args[0])+'\n','stderr':''}
    if exe in {'copy','cp'} and len(args)>=2:
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':copy_path(args[0],args[1])+'\n','stderr':''}
    if exe in {'move','mv','ren','rename'} and len(args)>=2:
        return {'command':cmd,'cwd':str(work),'returncode':0,'stdout':move_path(args[0],args[1])+'\n','stderr':''}
    raise ValueError(f'Invalid arguments for {exe}.')

def save_upload(filename,data):
    name=Path(filename).name
    if not name:raise ValueError('Invalid upload filename.')
    p=UPLOAD_DIR/name;p.write_bytes(data);return str(p)
