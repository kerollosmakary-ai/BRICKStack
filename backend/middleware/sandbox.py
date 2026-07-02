"""Hardened sandbox execution for BRICKStack."""
import os, subprocess, tempfile, resource, signal, sys, time, re
from typing import Dict, Any

class SecureSandbox:
    """Execute code in a restricted subprocess."""
    
    # Blacklisted modules and builtins
    BLACKLISTED_IMPORTS = [
        'os', 'subprocess', 'sys', 'pty', 'socket', 'urllib', 'http', 'ftplib',
        'pickle', 'marshal', 'ctypes', 'multiprocessing', 'threading',
    ]
    
    # Resource limits
    MAX_MEMORY_MB = 128
    MAX_CPU_SECONDS = 5
    MAX_OUTPUT_BYTES = 100000
    
    @classmethod
    def execute(cls, code: str, language: str = "python") -> Dict[str, Any]:
        if language != "python":
            return {"success": False, "output": "", "error": "Only Python supported in secure mode"}
        
        # Pre-validate code
        if not code or len(code) > 50000:
            return {"success": False, "output": "", "error": "Code too large or empty"}
        
        # Wrap code with restrictions
        restricted_code = cls._wrap_code(code)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w") as f:
                f.write(restricted_code)
            
            try:
                proc = subprocess.run(
                    [sys.executable, "-u", script_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    preexec_fn=cls._set_limits,
                    env={"PATH": "/usr/bin:/bin", "HOME": tmpdir, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                output = proc.stdout[:cls.MAX_OUTPUT_BYTES]
                error = proc.stderr[:cls.MAX_OUTPUT_BYTES] if proc.returncode != 0 else ""
                return {
                    "success": proc.returncode == 0,
                    "output": output,
                    "error": error,
                    "returncode": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "output": "", "error": "Execution timed out (30s limit)"}
            except Exception as e:
                return {"success": False, "output": "", "error": f"Sandbox error: {e}"}
    
    @classmethod
    def _set_limits(cls):
        """Set resource limits in the child process."""
        try:
            # Memory limit
            resource.setrlimit(resource.RLIMIT_AS, (cls.MAX_MEMORY_MB * 1024 * 1024, cls.MAX_MEMORY_MB * 1024 * 1024))
            # CPU limit
            resource.setrlimit(resource.RLIMIT_CPU, (cls.MAX_CPU_SECONDS, cls.MAX_CPU_SECONDS + 1))
            # No core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # Limit file size
            resource.setrlimit(resource.RLIMIT_FSIZE, (1 * 1024 * 1024, 1 * 1024 * 1024))
            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
        except Exception:
            pass
    
    @classmethod
    def _wrap_code(cls, user_code: str) -> str:
        """Wrap user code with security restrictions."""
        wrapper = f'''
import sys, builtins

# Restrict builtins
restricted_builtins = dict(builtins.__dict__)
for name in ['eval', 'exec', 'compile', '__import__', 'open', 'input']:
    restricted_builtins.pop(name, None)

# Restrict imports
original_import = __builtins__.get('__import__', __import__)

def restricted_import(name, *args, **kwargs):
    base = name.split('.')[0]
    blacklist = {repr(cls.BLACKLISTED_IMPORTS)}
    if base in blacklist:
        raise ImportError(f"Import of '{{base}}' is not allowed")
    return original_import(name, *args, **kwargs)

restricted_builtins['__import__'] = restricted_import

# Run user code in restricted namespace
exec({repr(user_code)}, {{
    "__builtins__": restricted_builtins,
    "print": print,
}})
'''
        return wrapper
