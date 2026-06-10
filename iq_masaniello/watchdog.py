"""
IQBOT Watchdog v1.0
Monitora o bot e reinicia automaticamente se travar.
"""
import subprocess, time, sys, os, socket
from datetime import datetime

BOT_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
CHECK_PORT  = 8765
MAX_TRAVADO = 60
RESTART_WAIT= 5

processo    = None
ultimo_ok   = time.time()

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Watchdog: {msg}", flush=True)

def iniciar_bot():
    global processo, ultimo_ok
    log("Iniciando bot...")
    processo = subprocess.Popen([sys.executable, BOT_FILE], stdout=sys.stdout, stderr=sys.stderr)
    ultimo_ok = time.time()
    log(f"Bot PID {processo.pid}")

def bot_vivo():
    global ultimo_ok
    if processo is None or processo.poll() is not None:
        return False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        ok = s.connect_ex(('localhost', CHECK_PORT)) == 0
        s.close()
        if ok:
            ultimo_ok = time.time()
            return True
    except Exception:
        pass
    return time.time() - ultimo_ok <= MAX_TRAVADO

def matar_bot():
    global processo
    if processo and processo.poll() is None:
        try:
            processo.terminate()
            time.sleep(3)
            if processo.poll() is None:
                processo.kill()
        except Exception:
            pass
    processo = None

log("Watchdog iniciado!")
iniciar_bot()

while True:
    time.sleep(10)
    if not bot_vivo():
        log("Bot travado - reiniciando...")
        matar_bot()
        time.sleep(RESTART_WAIT)
        iniciar_bot()
        log("Bot reiniciado!")
