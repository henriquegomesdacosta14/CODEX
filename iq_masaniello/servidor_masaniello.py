"""
servidor_masaniello.py
======================
Servidor web do painel Masaniello.
Acesse pelo navegador: http://IP:3000

Dependências:
    pip install flask flask-cors anthropic
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE        = Path("/opt/masaniello/iq_masaniello")
STATE_FILE  = BASE / "masaniello_state.json"
COFRE_FILE  = BASE / "cofre_confluencia.json"
HIST_FILE   = BASE / "historico_confluencia.json"
LOG_FILE    = BASE / "bot_confluencia.log"
DASHBOARD   = BASE / "dashboard_masaniello.html"
CONFIG_FILE = BASE / "masaniello_config.json"

_CONFIG_DEFAULTS = {
    "email":              "",
    "password":           "",
    "account_type":       "PRACTICE",
    "asset":              "EURUSD-OTC",
    "duration":           1,
    "banca_trabalho":     1000.0,
    "meta_ciclo":         80.0,
    "total_ops":          10,
    "min_wins":           5,
    "payout":             0.85,
    "min_score":          5,
    "adx_minimo":         20,
    "scan_interval":      15,
    "banca_minima":       200.0,
    "ao_quebrar":         "continuar",
    "ciclos_para_saque":  10,
    "claude_key":         "",
    "claude_model":       "claude-haiku-4-5-20251001",
    "claude_enabled":     False,
}


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


def _ler_config() -> dict:
    saved = ler_json(CONFIG_FILE)
    cfg = {**_CONFIG_DEFAULTS, **saved}
    return cfg


def _salvar_config(data: dict):
    current = _ler_config()
    # Merge incoming fields; skip claude_key if sent as masked placeholder
    for k, v in data.items():
        if k == "claude_key" and v in ("", "••••••••"):
            continue
        current[k] = v
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False))


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
    try:
        from masaniello_core import calcular_entrada
        target    = banca_ini + state.get("cfg", {}).get("meta", state.get("cfg", {}).get("metaLucro", 0))
        rem_ops   = max(0, total_ops - op_atual + 1)
        rem_wins  = max(0, state.get("cfg", {}).get("min_wins", state.get("cfg", {}).get("minWins", 0)) - wins)
        proxima   = calcular_entrada(target, saldo, rem_ops, rem_wins, payout) if rem_ops > 0 else 0
    except Exception:
        proxima = 0

    cfg_saved = ler_json(CONFIG_FILE)
    ativo = state.get("ativo_atual", cfg_saved.get("assets_reais", ["EURUSD"])[0]
                      if cfg_saved.get("assets_reais") else "EURUSD")

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
        "ts":            datetime.now().strftime("%H:%M:%S")
    })


@app.route("/api/logs")
def api_logs():
    try:
        linhas = LOG_FILE.read_text(errors="ignore").splitlines()
        return jsonify({"logs": linhas[-50:]})
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


@app.route("/api/config", methods=["GET"])
def api_config_get():
    cfg = _ler_config()
    # Mask the Claude key before sending to browser
    if cfg.get("claude_key"):
        cfg["claude_key"] = "••••••••"
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    try:
        data = request.get_json(force=True) or {}
        _salvar_config(data)
        # Reload bot config if pm2 process is running
        try:
            subprocess.run(["pm2", "reload", "masaniello"], timeout=10, capture_output=True)
        except Exception:
            pass
        return jsonify({"ok": True, "msg": "Configuração salva com sucesso!"})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@app.route("/api/testar_claude", methods=["POST"])
def api_testar_claude():
    cfg = _ler_config()
    key   = cfg.get("claude_key", "")
    model = cfg.get("claude_model", "claude-haiku-4-5-20251001")

    # Allow override key in the request body (when user just typed it)
    body = request.get_json(force=True) or {}
    if body.get("claude_key") and body["claude_key"] not in ("", "••••••••"):
        key = body["claude_key"]

    if not key:
        return jsonify({"ok": False, "msg": "Chave API não configurada. Salve a chave primeiro."})

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=model,
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": (
                    "Você é um assistente de trading. Responda APENAS com: "
                    "CONEXÃO OK — Claude disponível para análise de sinais."
                )
            }]
        )
        resposta = msg.content[0].text.strip()
        return jsonify({"ok": True, "msg": resposta, "model": model})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro: {str(e)}"})


@app.route("/")
def index():
    return send_file(str(DASHBOARD))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
