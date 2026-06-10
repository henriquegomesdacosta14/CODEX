"""
servidor_masaniello.py
======================
Servidor web do painel Masaniello.
Acesse pelo navegador: http://localhost:3000

Dependências:
    pip install flask flask-cors anthropic
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE        = (
    Path("/opt/masaniello/iq_masaniello")
    if Path("/opt/masaniello/iq_masaniello").exists()
    else Path(__file__).parent
)
STATE_FILE  = BASE / "masaniello_state.json"
COFRE_FILE  = BASE / "cofre_confluencia.json"
HIST_FILE   = BASE / "historico_confluencia.json"
LOG_FILE    = BASE / "bot_confluencia.log"
DASHBOARD   = BASE / "dashboard_masaniello.html"
CONFIG_FILE = BASE / "masaniello_config.json"
PID_FILE    = BASE / "bot.pid"

IS_WINDOWS = sys.platform == "win32"

_CONFIG_DEFAULTS = {
    "email":              "",
    "password":           "",
    "account_type":       "PRACTICE",
    "assets_reais":       ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD"],
    "assets_otc":         ["EURUSD-OTC","GBPUSD-OTC","AUDUSD-OTC"],
    "duration":           1,
    "banca_trabalho":     480.0,
    "meta_ciclo":         70.0,
    "total_ops":          7,
    "min_wins":           4,
    "payout":             0.85,
    "min_score":          5,
    "adx_minimo":         20,
    "scan_interval":      15,
    "banca_minima":       100.0,
    "ao_quebrar":         "continuar",
    "ciclos_para_saque":  10,
    "claude_key":         "",
    "claude_model":       "claude-haiku-4-5-20251001",
    "claude_enabled":     False,
}


def ler_json(path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


# ── Status do bot ────────────────────────────────────────────

def _processo_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def _status_local() -> str:
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            return "online" if _processo_vivo(pid) else "stopped"
    except Exception:
        pass
    return "stopped"


def _status_pm2() -> str:
    try:
        r = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True, text=True, timeout=5
        )
        procs = json.loads(r.stdout)
        for p in procs:
            if p.get("name") == "masaniello":
                return p.get("pm2_env", {}).get("status", "stopped")
    except Exception:
        pass
    return None


def bot_status() -> str:
    if not IS_WINDOWS:
        s = _status_pm2()
        if s is not None:
            return s
    return _status_local()


# ── Config ───────────────────────────────────────────────────

def _ler_config() -> dict:
    saved = ler_json(CONFIG_FILE)
    return {**_CONFIG_DEFAULTS, **saved}


def _salvar_config(data: dict):
    current = _ler_config()
    for k, v in data.items():
        if k == "claude_key" and v in ("", "••••••••"):
            continue
        current[k] = v
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(current, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


# ── API ──────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    state  = ler_json(STATE_FILE)
    cofre  = ler_json(COFRE_FILE)
    hist   = ler_json(HIST_FILE) if HIST_FILE.exists() else []
    status = bot_status()

    saldo     = state.get("saldo", 0)
    banca_ini = state.get("cfg", {}).get("bancaInicial", state.get("cfg", {}).get("banca", 0))
    wins      = state.get("wins", 0)
    losses    = state.get("losses", 0)
    total     = wins + losses
    taxa      = round(wins / total * 100, 1) if total else 0
    lucro     = round(saldo - banca_ini, 2) if banca_ini else 0
    op_atual  = state.get("op_atual", state.get("opAtual", 1))
    total_ops = state.get("cfg", {}).get("total_ops", state.get("cfg", {}).get("totalOps", 0))
    payout    = state.get("cfg", {}).get("payout", 0.85)

    proxima = 0
    try:
        from masaniello_core import calcular_entrada
        target   = banca_ini + state.get("cfg", {}).get("meta", state.get("cfg", {}).get("metaLucro", 0))
        rem_ops  = max(0, total_ops - op_atual + 1)
        rem_wins = max(0, state.get("cfg", {}).get("min_wins", state.get("cfg", {}).get("minWins", 0)) - wins)
        proxima  = calcular_entrada(target, saldo, rem_ops, rem_wins, payout) if rem_ops > 0 else 0
    except Exception:
        pass

    cfg_saved = ler_json(CONFIG_FILE)
    reais = cfg_saved.get("assets_reais", ["EURUSD"])
    ativo = state.get("ativo_atual", reais[0] if reais else "EURUSD")

    return jsonify({
        "bot_status":    status,
        "saldo":         saldo,
        "banca_ini":     banca_ini,
        "lucro":         lucro,
        "wins":          wins,
        "losses":        losses,
        "taxa":          taxa,
        "op_atual":      op_atual,
        "total_ops":     total_ops,
        "proxima":       round(proxima, 2),
        "cofre":         cofre.get("total", 0),
        "ciclos_ganhos": cofre.get("ciclos_ganhos", 0),
        "total_ciclos":  len(hist) if isinstance(hist, list) else 0,
        "cycle_status":  state.get("status", "–"),
        "ativo_atual":   ativo,
        "ts":            datetime.now().strftime("%H:%M:%S"),
        "modo":          "local" if IS_WINDOWS else "vps",
    })


@app.route("/api/logs")
def api_logs():
    try:
        linhas = LOG_FILE.read_text(errors="ignore", encoding="utf-8").splitlines()
        return jsonify({"logs": linhas[-50:]})
    except Exception:
        return jsonify({"logs": []})


@app.route("/api/ligar", methods=["POST"])
def api_ligar():
    # VPS com PM2
    if not IS_WINDOWS:
        try:
            subprocess.run(["pm2", "start", "masaniello"], timeout=10)
            return jsonify({"ok": True, "msg": "Bot ligado via PM2"})
        except FileNotFoundError:
            pass

    # Windows / local: inicia como subprocesso
    try:
        bot_py = str(BASE / "bot_confluencia.py")
        proc = subprocess.Popen(
            [sys.executable, bot_py],
            cwd=str(BASE),
            creationflags=subprocess.CREATE_NEW_CONSOLE if IS_WINDOWS else 0,
        )
        PID_FILE.write_text(str(proc.pid))
        return jsonify({"ok": True, "msg": f"Bot ligado (PID {proc.pid})"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/api/desligar", methods=["POST"])
def api_desligar():
    # VPS com PM2
    if not IS_WINDOWS:
        try:
            subprocess.run(["pm2", "stop", "masaniello"], timeout=10)
            return jsonify({"ok": True, "msg": "Bot desligado via PM2"})
        except FileNotFoundError:
            pass

    # Windows / local: mata pelo PID
    try:
        if not PID_FILE.exists():
            return jsonify({"ok": False, "msg": "PID não encontrado — feche a janela do bot manualmente"})
        pid = int(PID_FILE.read_text().strip())
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 15)  # SIGTERM
        PID_FILE.unlink(missing_ok=True)
        return jsonify({"ok": True, "msg": "Bot desligado"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/api/historico")
def api_historico():
    hist = ler_json(HIST_FILE) if HIST_FILE.exists() else []
    return jsonify(hist[-20:] if isinstance(hist, list) else [])


@app.route("/api/config", methods=["GET"])
def api_config_get():
    cfg = _ler_config()
    if cfg.get("claude_key"):
        cfg["claude_key"] = "••••••••"
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    try:
        data = request.get_json(force=True) or {}
        _salvar_config(data)
        # Tenta recarregar via PM2 (VPS)
        try:
            subprocess.run(["pm2", "reload", "masaniello"], timeout=10, capture_output=True)
        except Exception:
            pass
        return jsonify({"ok": True, "msg": "Configuração salva! Reinicie o bot para aplicar."})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/api/testar_claude", methods=["POST"])
def api_testar_claude():
    cfg  = _ler_config()
    key  = cfg.get("claude_key", "")
    model = cfg.get("claude_model", "claude-haiku-4-5-20251001")

    body = request.get_json(force=True) or {}
    if body.get("claude_key") and body["claude_key"] not in ("", "••••••••"):
        key = body["claude_key"]

    if not key:
        return jsonify({"ok": False, "msg": "Chave API não configurada."})

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=model,
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": "Responda APENAS: CONEXÃO OK — Claude disponível para análise de sinais."
            }]
        )
        return jsonify({"ok": True, "msg": msg.content[0].text.strip(), "model": model})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro: {str(e)}"})


@app.route("/")
def index():
    return send_file(str(DASHBOARD))


if __name__ == "__main__":
    print(f"\n  Painel rodando em: http://localhost:3000\n")
    app.run(host="0.0.0.0", port=3000, debug=False)
