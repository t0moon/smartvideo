import subprocess, sys, time, os

log = open(r"C:\Users\gyue\Desktop\smartvideo-main\backend\server_debug.log", "w", encoding="utf-8")

env = {**os.environ, "PYTHONUNBUFFERED": "1"}

p = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8765", "--log-level", "info"],
    cwd=r"C:\Users\gyue\Desktop\smartvideo-main\backend",
    stdout=log, stderr=subprocess.STDOUT, env=env
)
log.write(f"[startup] Server PID: {p.pid}\n")
log.flush()

while True:
    time.sleep(5)
    if p.poll() is not None:
        log.write(f"[startup] Server exited with code {p.returncode}\n")
        log.flush()
        break
    else:
        log.write(f"[startup] Server alive (PID {p.pid})\n")
        log.flush()
