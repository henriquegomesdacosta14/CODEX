"""
servidor_masaniello.py
======================
Servidor web do painel Masaniello.
Acesse pelo navegador: http://IP:3000

Dependências:
    pip install flask flask-cors
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

STATE_FILE  = Path("/opt/masaniello/iq_masaniello/masaniello_state.json")
COFRE_FILE  = Path("/opt/masaniello/iq_masaniello/cofre_confluencia.json")
HIST_FILE   = Path("/opt/masaniello/iq_masaniello/historico_confluencia.json")
LOG_FILE    = Path("/opt/masaniello/iq_masaniello/bot_confluencia.log")
DASHBOARD   = Path("/opt/masaniello/iq_masaniello/dashboard_masaniello.html")

def ler_json(path):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}

def pm2_status():
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        procs = json.loads(r.stdout)
        for p in procs:
            if p.get("name") == "masaniello":
                return p.get("pm2_env", {}).get("status", "stopped")
    except Exception:
        pass
    return "unknown"

# ── API ─────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    state  = ler_json(STATE_FILE)
    cofre  = ler_json(COFRE_FILE)
    hist   = ler_json(HIST_FILE) if HIST_FILE.exists() else []
    status = pm2_status()

    saldo      = state.get("saldo", 0)
    banca_ini  = state.get("cfg", {}).get("bancaInicial", state.get("cfg", {}).get("banca", 0))
    wins       = state.get("wins", 0)
    losses     = state.get("losses", 0)
    total      = wins + losses
    taxa       = round(wins / total * 100, 1) if total else 0
    lucro      = round(saldo - banca_ini, 2) if banca_ini else 0
    op_atual   = state.get("op_atual", state.get("opAtual", 1))
    total_ops  = state.get("cfg", {}).get("total_ops", state.get("cfg", {}).get("totalOps", 0))
    payout     = state.get("cfg", {}).get("payout", 0.85)

    # Próxima entrada
    from masaniello_core import calcular_entrada
    target    = banca_ini + state.get("cfg", {}).get("meta", state.get("cfg", {}).get("metaLucro", 0))
    rem_ops   = max(0, total_ops - op_atual + 1)
    rem_wins  = max(0, state.get("cfg", {}).get("min_wins", state.get("cfg", {}).get("minWins", 0)) - wins)
    proxima   = calcular_entrada(target, saldo, rem_ops, rem_wins, payout) if rem_ops > 0 else 0

    return jsonify({
        "bot_status":   status,
        "saldo":        saldo,
        "banca_ini":    banca_ini,
        "lucro":        lucro,
        "wins":         wins,
        "losses":       losses,
        "taxa":         taxa,
        "op_atual":     op_atual,
        "total_ops":    total_ops,
        "proxima":      round(proxima, 2),
        "cofre":        cofre.get("total", 0),
        "ciclos_ganhos":cofre.get("ciclos_ganhos", 0),
        "total_ciclos": len(hist) if isinstance(hist, list) else 0,
        "cycle_status": state.get("status", "–"),
        "ts":           datetime.now().strftime("%H:%M:%S")
    })

@app.route("/api/logs")
def api_logs():
    try:
        linhas = LOG_FILE.read_text(errors="ignore").splitlines()
        return jsonify({"logs": linhas[-50:]})  # últimas 50 linhas
    except Exception:
        return jsonify({"logs": []})

@app.route("/api/ligar", methods=["POST"])
def api_ligar():
    try:
        subprocess.run(["pm2", "start", "masaniello"], timeout=10)
        return jsonify({"ok": True, "msg": "Bot ligado"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route("/api/desligar", methods=["POST"])
def api_desligar():
    try:
        subprocess.run(["pm2", "stop", "masaniello"], timeout=10)
        return jsonify({"ok": True, "msg": "Bot desligado"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route("/api/historico")
def api_historico():
    hist = ler_json(HIST_FILE) if HIST_FILE.exists() else []
    return jsonify(hist[-20:] if isinstance(hist, list) else [])

@app.route("/")
def index():
    return send_file(str(DASHBOARD))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
