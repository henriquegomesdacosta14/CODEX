"""
IQBOT EMA M1 + Claude Vision

Base: iqbot-ema-m1.py (estrutura original preservada)
Adicionado:
- Claude Vision analisa cada vela com chart EMA3/EMA10/SMA21 + Williams Fractal
- Contra-tendência bloqueado: se preço abaixo SMA21 e Claude vê compra → SKIP
- Pausa automática após N losses consecutivos (retoma com conf≥80%)
- Sinal FORTE → boost 1.5x no stake inicial
- EMA original (EMA20/50) como fallback se Claude falhar
"""

import asyncio
import base64
import io
import json
import os
import ssl
import time
import urllib.request
from collections import deque
from datetime import datetime


def carregar_env_local(caminho=".env"):
    if not os.path.exists(caminho):
        return
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#") or "=" not in linha:
                    continue
                chave, valor = linha.split("=", 1)
                chave = chave.strip()
                valor = valor.strip().strip('"').strip("'")
                os.environ.setdefault(chave, valor)
    except Exception:
        pass


carregar_env_local()

IQ_EMAIL    = os.getenv("IQ_EMAIL", "SEU_EMAIL@exemplo.com")
IQ_PASSWORD = os.getenv("IQ_PASSWORD", "SUA_SENHA")
CLAUDE_KEY  = os.getenv("CLAUDE_KEY", "sk-ant-api03-SEU_CLAUDE_API_KEY")

ATIVO_FIXO           = os.getenv("IQ_ATIVO", "EURUSD-OTC")

# Lista de ativos alternativos — usados quando o principal está fechado ou payout baixo
ATIVOS_LISTA = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC",
    "EURJPY-OTC", "EURGBP-OTC", "NZDUSD-OTC", "USDCAD-OTC",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
]

TIMEFRAME            = 60
EXPIRACAO_MIN        = 1

STAKE_MINIMA         = 2.0
STAKE_INICIAL        = 2.0
MG_FATOR             = 2.25
MG_NIVEIS            = 7
STOP_LOSS            = 250.0
STOP_GAIN            = 48.0
CONTA_DEMO           = True
DASHBOARD_PORT       = 8775
CONFIG_FILE          = "iqbot-claude-config.json"
STATE_FILE           = "iqbot-claude-state.json"
PAYOUT_MINIMO        = 0.80
MODO_EXECUCAO        = os.getenv("MODO_EXECUCAO", "precheck")

# Claude / análise
MAX_LOSS_SEQ         = 3     # pausa após N losses seguidos
CONFIANCA_MIN_CLAUDE = 72    # confiança mínima para entrar
FORTE_BOOST          = 1.5   # multiplicador de stake quando sinal FORTE

# EMA original (fallback sem Claude)
EMA_RAPIDA           = 20
EMA_LENTA            = 50
CANDLES_ANALISE      = 90
CONFIRMAR_CRUZAMENTO = 2

ENTRADA_APOS_SEGUNDOS       = 0
JANELA_ENTRADA_SEGUNDOS     = 4
TIMEOUT_COMPRA_SEGUNDOS     = 15
TIMEOUT_BANCA_SEGUNDOS      = 12
TIMEOUT_RESULTADO_ID_SEGUNDOS = 6
TENTATIVAS_BANCA            = 3
FOLGA_RESULTADO_SEGUNDOS    = 0.15
PRECHECK_RESULTADO          = True
PRECHECK_SEGUNDOS_ANTES     = 5
PRECHECK_WIN_PONTOS         = 150
PRECHECK_LOSS_PONTOS        = 19
PONTOS_MULTIPLICADOR        = 100000

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        _cfg = json.load(f)
    ATIVO_FIXO           = str(_cfg.get("ativo", ATIVO_FIXO))
    STAKE_INICIAL        = max(STAKE_MINIMA, float(_cfg.get("stake", STAKE_INICIAL)))
    MG_FATOR             = float(_cfg.get("mg_fator", MG_FATOR))
    MG_NIVEIS            = int(_cfg.get("mg_niveis", MG_NIVEIS))
    STOP_LOSS            = float(_cfg.get("stop_loss", STOP_LOSS))
    STOP_GAIN            = float(_cfg.get("stop_gain", STOP_GAIN))
    CONTA_DEMO           = bool(_cfg.get("demo", CONTA_DEMO))
    PAYOUT_MINIMO        = float(_cfg.get("payout_minimo", PAYOUT_MINIMO))
    MODO_EXECUCAO        = str(_cfg.get("modo_execucao", MODO_EXECUCAO))
    CLAUDE_KEY           = str(_cfg.get("claude_key", CLAUDE_KEY))
    MAX_LOSS_SEQ         = int(_cfg.get("max_loss_seq", MAX_LOSS_SEQ))
    CONFIANCA_MIN_CLAUDE = int(_cfg.get("confianca_min", CONFIANCA_MIN_CLAUDE))
except Exception:
    pass

# ─── Aprendizado adaptativo ──────────────────────────────────────
APRENDIZADO_JANELA     = 15    # últimas N operações para análise
APRENDIZADO_THRESH_INV = 0.35  # auto-inverte se win rate < 35%
APRENDIZADO_THRESH_OK  = 0.55  # remove inversão se win rate > 55%

estado = {
    "rodando": False,
    "banca_inicial": 0.0,
    "banca_atual": 0.0,
    "lucro": 0.0,
    "ganhos": 0,
    "perdas": 0,
    "mg_nivel": 0,
    "soros_nivel": 0,
    "soros_stake": 0.0,
    "stake_atual": STAKE_INICIAL,
    "modo_banca": "claude_m1",
    "mg_soros_fase": "ema",
    "mg_rec_perdas": 0.0,
    "mg_rec_nivel": 0,
    "payout_atual": 0.80,
    "api_credito": 0.0,
    "api_gasto": 0.0,
    "api_chamadas": 0,
    "api_alerta": False,
    "ultima_operacao": None,
    "ultima_analise": None,
    "ativo_atual": ATIVO_FIXO,
    "tf_atual": "M1",
    "varrendo": False,
    "varredura_log": [],
    "historico": [],
    "status": "Aguardando...",
    "log": deque(maxlen=120),
    "crono_entrada": 0,
    "crono_sessao": 0,
    "trade_ativo": False,
    "inverter_tudo": False,
    "so_tendencia": False,
    "sessao_inicio": 0,
    # Claude / pausa
    "gale_pausado": False,
    "loss_seq": 0,
    "max_loss_seq": MAX_LOSS_SEQ,
    "confianca_min": CONFIANCA_MIN_CLAUDE,
    # Indicadores
    "ema3": 0.0,
    "ema10": 0.0,
    "ema21": 0.0,
    "direcao_ema": "—",
    # Multi-timeframe
    "mtf_dir15s": "—",
    "mtf_dir30s": "—",
    "mtf_conf":   "—",
    # Aprendizado adaptativo
    "aprendizado": {
        "call_wins":    0,
        "call_total":   0,
        "put_wins":     0,
        "put_total":    0,
        "auto_inverter": False,
        "taxa_recente": 0.0,
    },
}

clientes_ws          = set()
bot_task             = None
ultima_direcao_valida = None

# ── Cache de análise pré-buscada em background ──────────────────
# { "vela_id": int, "analise": dict, "em_busca": bool }
_analise_cache: dict = {"vela_id": -1, "analise": None, "em_busca": False}

# Timeframes auxiliares para MTF
TF_15S = 15
TF_30S = 30
CANDLES_MTF = 12   # últimas 12 velas de 15s/30s para análise


# ─────────────────────────────────────────────
#  LOG / BROADCAST
# ─────────────────────────────────────────────

def log(msg):
    linha = f"{datetime.now().strftime('%H:%M:%S')} | {msg}"
    print(linha, flush=True)
    estado["log"].appendleft(linha)


async def broadcast():
    if not clientes_ws:
        return
    payload = dict(estado)
    payload["log"]      = list(estado["log"])
    payload["banca"]    = estado["banca_atual"]
    payload["stake"]    = estado["stake_atual"]
    payload["ultima_op"]    = estado.get("ultima_operacao")
    payload["analise"]      = estado.get("ultima_analise")
    payload["aprendizado"]  = estado.get("aprendizado", {})
    padroes_stats, horas_stats = stats_padroes()
    payload["padroes_stats"] = [
        {"nome": k, "wins": v["wins"], "total": v["total"]}
        for k, v in sorted(padroes_stats.items(), key=lambda x: -x[1]["total"])
    ]
    payload["horas_stats"] = [
        {"hora": k, "wins": v["wins"], "total": v["total"]}
        for k, v in sorted(horas_stats.items())
    ]
    payload["config"]   = {
        "ativo":              ATIVO_FIXO,
        "stake":              STAKE_INICIAL,
        "mg_fator":           MG_FATOR,
        "mg_niveis":          MG_NIVEIS,
        "stop_loss":          STOP_LOSS,
        "stop_gain":          STOP_GAIN,
        "demo":               CONTA_DEMO,
        "payout_minimo":      PAYOUT_MINIMO,
        "modo_execucao":      MODO_EXECUCAO,
        "precheck_segundos":  PRECHECK_SEGUNDOS_ANTES,
        "precheck_win_pontos":PRECHECK_WIN_PONTOS,
        "precheck_loss_pontos":PRECHECK_LOSS_PONTOS,
        "max_loss_seq":       MAX_LOSS_SEQ,
        "confianca_min":      CONFIANCA_MIN_CLAUDE,
        "claude_key_ok":      bool(CLAUDE_KEY and not CLAUDE_KEY.startswith("sk-ant-api03-SEU")),
    }
    texto = json.dumps(payload, ensure_ascii=False, default=str)
    mortos = []
    for ws in clientes_ws:
        try:
            await ws.send(texto)
        except Exception:
            mortos.append(ws)
    for ws in mortos:
        clientes_ws.discard(ws)


async def loop_cronometro():
    while True:
        await asyncio.sleep(1)
        if estado["trade_ativo"]:
            estado["crono_entrada"] += 1
        if estado["rodando"] and estado["sessao_inicio"] > 0:
            estado["crono_sessao"] = int(time.time() - estado["sessao_inicio"])
        await broadcast()


# ─────────────────────────────────────────────
#  CANDLES / INDICADORES
# ─────────────────────────────────────────────

def normalizar_candles(candles_raw):
    candles = []
    for c in candles_raw or []:
        try:
            candles.append({
                "open":  float(c["open"]),
                "high":  float(c.get("max", c.get("high"))),
                "low":   float(c.get("min", c.get("low"))),
                "close": float(c["close"]),
                "from":  int(c.get("from", c.get("at", 0))),
            })
        except Exception:
            pass
    return candles


def ema(valores, periodo):
    """EMA simples — mantida para compatibilidade com analisar_ema()."""
    if len(valores) < periodo:
        return None
    k = 2 / (periodo + 1)
    atual = sum(valores[:periodo]) / periodo
    for preco in valores[periodo:]:
        atual = (preco * k) + (atual * (1 - k))
    return atual


def _ema(prices, n):
    if len(prices) < n:
        return None
    k = 2 / (n + 1)
    val = sum(prices[:n]) / n
    for p in prices[n:]:
        val = p * k + val * (1 - k)
    return val


def _sma(prices, n):
    if len(prices) < n:
        return None
    return sum(prices[-n:]) / n


def detectar_fractais(candles):
    """Williams Fractal de 5 velas."""
    ups, downs = [], []
    for i in range(2, len(candles) - 2):
        c = candles[i]
        if all(c["high"] > candles[i + j]["high"] and c["high"] > candles[i - j]["high"] for j in range(1, 3)):
            ups.append(i)
        if all(c["low"] < candles[i + j]["low"] and c["low"] < candles[i - j]["low"] for j in range(1, 3)):
            downs.append(i)
    return ups, downs


def cor(candle):
    if candle["close"] > candle["open"]:
        return "VERDE"
    if candle["close"] < candle["open"]:
        return "VERMELHA"
    return "DOJI"


def analisar_mtf(c15: list, c30: list) -> dict:
    """Analisa velas de 15s e 30s para confirmar o comportamento da vela M1.

    Retorna:
        dir_15s, dir_30s   — "CALL" | "PUT" | "NEUTRO"
        confluencia        — direção quando ambos concordam
        forca              — pontuação 0..8 (mais = mais claro)
        motivo_mtf         — texto curto para o dashboard
    """
    def tendencia(candles):
        if len(candles) < 4:
            return "NEUTRO", 0
        recentes = candles[-6:]
        closes = [c["close"] for c in recentes]
        e3 = _ema(closes, 3)
        e5 = _ema(closes, min(5, len(closes)))
        if e3 is None or e5 is None:
            return "NEUTRO", 0
        bulls = sum(1 for c in recentes[-4:] if c["close"] > c["open"])
        bears = sum(1 for c in recentes[-4:] if c["close"] < c["open"])
        if e3 > e5 and bulls >= 3:
            return "CALL", bulls
        if e3 < e5 and bears >= 3:
            return "PUT", bears
        # Empate fraco — usa só EMA
        if e3 > e5:
            return "CALL", 1
        if e3 < e5:
            return "PUT", 1
        return "NEUTRO", 0

    dir15, f15 = tendencia(c15) if c15 else ("NEUTRO", 0)
    dir30, f30 = tendencia(c30) if c30 else ("NEUTRO", 0)

    if dir15 == dir30 and dir15 != "NEUTRO":
        conf = dir15
        forca = f15 + f30
        motivo = f"MTF ✓ 15s:{dir15} 30s:{dir30} forca={forca}"
    elif dir30 != "NEUTRO":
        conf = dir30
        forca = f30
        motivo = f"MTF 30s:{dir30} (15s neutro)"
    elif dir15 != "NEUTRO":
        conf = dir15
        forca = f15
        motivo = f"MTF 15s:{dir15} (30s neutro)"
    else:
        conf = "NEUTRO"
        forca = 0
        motivo = "MTF neutro"

    return {
        "dir_15s":    dir15,
        "dir_30s":    dir30,
        "confluencia": conf,
        "forca":      forca,
        "motivo_mtf": motivo,
    }


# ─────────────────────────────────────────────
#  ANÁLISE EMA20/50 — FALLBACK original
# ─────────────────────────────────────────────

def analisar_ema(candles):
    global ultima_direcao_valida

    fechadas = candles[:-1]
    if len(fechadas) < EMA_LENTA + 2:
        return None

    closes = [c["close"] for c in fechadas]
    ultima = fechadas[-1]
    ema20 = ema(closes, EMA_RAPIDA)
    ema50 = ema(closes, EMA_LENTA)
    if ema20 is None or ema50 is None:
        return None

    ultimas_confirmacao = fechadas[-CONFIRMAR_CRUZAMENTO:]
    acima = all(c["close"] > ema(closes[:len(closes) - (len(ultimas_confirmacao) - 1 - i)], EMA_RAPIDA)
                for i, c in enumerate(ultimas_confirmacao))
    abaixo = all(c["close"] < ema(closes[:len(closes) - (len(ultimas_confirmacao) - 1 - i)], EMA_RAPIDA)
                 for i, c in enumerate(ultimas_confirmacao))

    inclinacao_20 = ema20 - ema(closes[:-3], EMA_RAPIDA)
    direcao = ultima_direcao_valida
    motivo  = "mantendo direcao anterior perto/cruzando EMA20"

    if acima:
        direcao = "CALL"
        motivo  = "2 fechamentos acima da EMA20"
    elif abaixo:
        direcao = "PUT"
        motivo  = "2 fechamentos abaixo da EMA20"
    elif direcao is None:
        direcao = "CALL" if ultima["close"] >= ema20 else "PUT"
        motivo  = "primeira direcao por EMA20"

    if estado["inverter_tudo"]:
        direcao = "PUT" if direcao == "CALL" else "CALL"
        motivo  = f"invertido | {motivo}"

    ultima_direcao_valida = direcao

    distancia = abs(ultima["close"] - ema20)
    score = 70
    if direcao == "CALL" and ema20 > ema50:
        score += 15
    if direcao == "PUT" and ema20 < ema50:
        score += 15
    if (direcao == "CALL" and inclinacao_20 > 0) or (direcao == "PUT" and inclinacao_20 < 0):
        score += 10
    score = min(score, 95)

    return {
        "sinal":     direcao,
        "padrao":    "EMA20/EMA50 M1 (fallback)",
        "confianca": score,
        "motivo":    f"{motivo} | close={ultima['close']:.5f} ema20={ema20:.5f} ema50={ema50:.5f} dist={distancia:.5f} vela={cor(ultima)}",
        "ativo":     ATIVO_FIXO,
        "timeframe": TIMEFRAME,
        "ema20":     ema20,
        "ema50":     ema50,
    }


# ─────────────────────────────────────────────
#  ANÁLISE CLAUDE VISION — principal
# ─────────────────────────────────────────────

def _gerar_grafico(candles):
    """Gera candlestick com EMA3/EMA10/SMA21 + fractais. Retorna base64 PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n   = min(30, len(candles) - 1)
    exib = candles[-(n + 1):-1]   # N velas fechadas para exibir
    all_c = [c["close"] for c in candles[:-1]]

    ups, downs = detectar_fractais(candles[:-1])
    offset = len(candles) - 1 - n   # índice da primeira vela exibida

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0a0f1e")
    ax.set_facecolor("#0a0f1e")

    for i, c in enumerate(exib):
        cor_c = "#00d084" if c["close"] >= c["open"] else "#ff4b6a"
        ax.plot([i, i], [c["low"], c["high"]], color=cor_c, linewidth=0.8)
        body = abs(c["close"] - c["open"]) or 0.00001 * c["close"]
        bot  = min(c["open"], c["close"])
        ax.add_patch(plt.Rectangle((i - 0.35, bot), 0.7, body, color=cor_c, zorder=2))

    xs = list(range(n))

    # Calcula EMAs ponto a ponto sobre o histórico completo para suavidade
    def serie_ema(period):
        serie = []
        for j in range(offset, offset + n):
            v = _ema(all_c[:j + 1], period)
            serie.append(v if v is not None else all_c[j])
        return serie

    def serie_sma(period):
        serie = []
        for j in range(offset, offset + n):
            v = _sma(all_c[:j + 1], period)
            serie.append(v if v is not None else all_c[j])
        return serie

    e3  = serie_ema(3)
    e10 = serie_ema(10)
    s21 = serie_sma(21)

    ax.plot(xs, e3,  color="#ffd166", linewidth=1.2, label="EMA3",  zorder=3)
    ax.plot(xs, e10, color="#ff4b6a", linewidth=1.2, label="EMA10", zorder=3)
    ax.plot(xs, s21, color="#4f7cff", linewidth=1.6, label="SMA21", zorder=3)

    for fi in ups:
        idx = fi - offset
        if 0 <= idx < n:
            ax.annotate("▲", xy=(idx, exib[idx]["high"] * 1.0002),
                        color="#00d084", fontsize=8, ha="center", zorder=4)
    for fi in downs:
        idx = fi - offset
        if 0 <= idx < n:
            ax.annotate("▼", xy=(idx, exib[idx]["low"] * 0.9998),
                        color="#ff4b6a", fontsize=8, ha="center", zorder=4)

    ax.legend(fontsize=8, facecolor="#0a0f1e", labelcolor="white", loc="upper left",
              framealpha=0.6)
    ax.tick_params(colors="#8f9bc4", labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor("#273153")
    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=80, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


async def analisar_com_claude(candles):
    """Chama Claude Vision. Retorna dict no mesmo formato de analisar_ema(), ou None."""
    try:
        closes = [c["close"] for c in candles[:-1]]
        e3  = _ema(closes, 3)
        e10 = _ema(closes, 10)
        s21 = _sma(closes, 21)

        if e3 is None or e10 is None:
            return None

        ups, downs = detectar_fractais(candles[:-1])
        ult         = candles[-2]
        preco       = ult["close"]
        price_vs_sma = "ACIMA" if preco > (s21 or preco) else "ABAIXO"
        ema_div      = abs(e3 - e10) / e10 * 100 if e10 else 0
        ema_dir      = "CALL" if e3 > e10 else "PUT"

        # Atualiza estado com indicadores
        estado["ema3"]       = round(e3, 5)
        estado["ema10"]      = round(e10, 5)
        estado["ema21"]      = round(s21, 5) if s21 else 0.0
        estado["direcao_ema"] = ema_dir

        ult_frac_up   = len(candles) - 2 - ups[-1]   if ups   else None
        ult_frac_down = len(candles) - 2 - downs[-1] if downs else None

        ultimas_velas = []
        for c in candles[-7:-1]:
            rng  = c["high"] - c["low"] or 0.00001
            body = abs(c["close"] - c["open"])
            ultimas_velas.append(
                f"{'▲' if c['close'] >= c['open'] else '▼'} body={body / rng * 100:.0f}% "
                f"c={c['close']:.5f}"
            )

        prompt = f"""Voce e um analista de price action M1 altamente especializado para binary options na IQ Option.

INDICADORES:
- EMA3={e3:.5f}  EMA10={e10:.5f}  SMA21={f'{s21:.5f}' if s21 else 'N/A'}
- Preco vs SMA21: {price_vs_sma}
- Divergencia EMA3/EMA10: {ema_div:.3f}%
- Tendencia EMA: {ema_dir}
- Ultimo fractal de ALTA: {f'{ult_frac_up} velas atras' if ult_frac_up is not None else 'N/A'}
- Ultimo fractal de BAIXA: {f'{ult_frac_down} velas atras' if ult_frac_down is not None else 'N/A'}

ULTIMAS 6 VELAS fechadas (da mais antiga para a mais recente):
{chr(10).join(ultimas_velas)}

CONTEXTO MG: nivel {estado['mg_nivel']}/{MG_NIVEIS} | {estado['loss_seq']} losses seguidos
{resumo_aprendizado()}

REGRAS RIGIDAS — siga exatamente:
1. Preco ABAIXO SMA21 + EMA3 < EMA10 => somente aceita PUT (tendencia baixa)
2. Preco ACIMA SMA21 + EMA3 > EMA10 => somente aceita CALL (tendencia alta)
3. Claude ver fluxo de COMPRA mas preco ABAIXO SMA21 => SKIP (risco alto de falha)
4. Claude ver fluxo de VENDA mas preco ACIMA SMA21 => SKIP (risco alto de falha)
5. Divergencia EMA < 0.02% => sem tendencia clara => SKIP
6. MG nivel >= 4 sem setup FORTE muito claro => SKIP
7. Sinal FORTE somente quando: EMA3/EMA10/SMA21 todos alinhados, fractal recente confirma, velas com corpo > 60%

Retorne JSON puro sem markdown:
{{"sinal":"CALL"|"PUT"|"SKIP","confianca":0-100,"padrao":"nome do padrao","motivo":"razao resumida","forca":"FORTE"|"NORMAL"}}"""

        img_b64 = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _gerar_grafico(candles)
        )

        body_req = json.dumps({
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 250,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                    {"type": "text",  "text": prompt},
                ]
            }]
        }).encode()

        headers = {
            "x-api-key":           CLAUDE_KEY,
            "anthropic-version":   "2023-06-01",
            "content-type":        "application/json",
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body_req, headers=headers, method="POST"
        )
        ctx = ssl.create_default_context()

        resp_raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: urllib.request.urlopen(req, context=ctx, timeout=25).read().decode()
        )

        rj     = json.loads(resp_raw)
        texto  = rj["content"][0]["text"].strip()
        if "```" in texto:
            partes = texto.split("```")
            texto = partes[1].lstrip("json").strip() if len(partes) > 1 else partes[0]

        res       = json.loads(texto)
        sinal     = res.get("sinal", "SKIP")
        confianca = int(res.get("confianca", 0))
        padrao    = res.get("padrao", "Claude Vision")
        motivo    = res.get("motivo", "")
        forca     = res.get("forca", "NORMAL")

        uso    = rj.get("usage", {})
        tokens = uso.get("input_tokens", 0) + uso.get("output_tokens", 0)
        custo  = tokens * 0.000003
        estado["api_gasto"]   = round(estado["api_gasto"] + custo, 5)
        estado["api_chamadas"] += 1

        log(f"🤖 Claude: {sinal} {confianca}% [{forca}] | {motivo[:70]}")

        if sinal == "SKIP":
            return None

        if confianca < estado["confianca_min"]:
            log(f"⏭ Confianca {confianca}% < {estado['confianca_min']}% — pulando")
            return None

        # Bloqueia contra-tendência (margem: conf < 85 não justifica contra-trend)
        if price_vs_sma == "ABAIXO" and sinal == "CALL" and confianca < 85:
            log(f"⏭ CALL mas preco ABAIXO SMA21, conf={confianca}% — SKIP")
            return None
        if price_vs_sma == "ACIMA" and sinal == "PUT" and confianca < 85:
            log(f"⏭ PUT mas preco ACIMA SMA21, conf={confianca}% — SKIP")
            return None

        # Inversão de sinal manual
        if estado["inverter_tudo"]:
            sinal = "PUT" if sinal == "CALL" else "CALL"
            motivo = f"invertido | {motivo}"

        # Boost FORTE no stake inicial (nivel 0)
        if forca == "FORTE" and estado["mg_nivel"] == 0:
            novo_stake = round(STAKE_INICIAL * FORTE_BOOST, 2)
            estado["stake_atual"] = novo_stake
            log(f"🔥 Sinal FORTE → stake boosted R${novo_stake:.2f}")

        return {
            "sinal":     sinal,
            "padrao":    padrao,
            "confianca": confianca,
            "motivo":    f"{motivo} | ema3={e3:.5f} ema10={e10:.5f} sma21={s21:.5f if s21 else 'N/A'} vs_sma={price_vs_sma}",
            "ativo":     ATIVO_FIXO,
            "timeframe": TIMEFRAME,
            "ema3":      e3,
            "ema10":     e10,
            "sma21":     s21,
            "forca":     forca,
        }

    except Exception as e:
        log(f"⚠ Claude erro: {e}")
        return None


# ─────────────────────────────────────────────
#  BUSCA ANÁLISE — M1 + MTF (15s/30s) em paralelo
# ─────────────────────────────────────────────

async def _fetch_candles_ativo(iq, ativo, tf, n):
    """Busca candles de um ativo específico. Usado na varredura."""
    try:
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: iq.get_candles(ativo, tf, n, time.time())
        )
        return normalizar_candles(raw)
    except Exception:
        return []


async def _fetch_candles_tf(iq, tf, n):
    """Busca candles do ATIVO_FIXO atual; retorna lista normalizada."""
    try:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None, lambda: iq.get_candles(ATIVO_FIXO, tf, n, time.time())
        )
        candles = normalizar_candles(raw)
        if not candles:
            log(f"⚠ Candles vazios tf={tf}s")
        return candles
    except Exception as e:
        log(f"⚠ Erro candles tf={tf}s: {e}")
        return []


def pontuar_ativo(candles):
    """Pontua clareza do gráfico para operar. Retorna (score 0-100, direcao, motivo)."""
    if not candles or len(candles) < 55:
        return 0, "NEUTRO", "poucos candles"
    fechadas = candles[:-1]
    closes   = [c["close"] for c in fechadas]
    e3  = _ema(closes, 3)
    e10 = _ema(closes, 10)
    s21 = _sma(closes, 21)
    e50 = _ema(closes, 50)
    if not all([e3, e10, s21, e50]):
        return 0, "NEUTRO", "EMA falhou"

    score   = 0
    direcao = "NEUTRO"
    motivos = []

    # Alinhamento completo das médias
    if e3 > e10 > s21 > e50:
        score += 40; direcao = "CALL"; motivos.append("EMAs↑ alinhadas")
    elif e3 < e10 < s21 < e50:
        score += 40; direcao = "PUT";  motivos.append("EMAs↓ alinhadas")
    elif e3 > e10 > s21:
        score += 20; direcao = "CALL"; motivos.append("EMA3>10>SMA21")
    elif e3 < e10 < s21:
        score += 20; direcao = "PUT";  motivos.append("EMA3<10<SMA21")
    else:
        return 5, "NEUTRO", "sem tendência"

    # Divergência entre EMA3 e EMA10 (tendência forte)
    div = abs(e3 - e10) / e10 * 100
    if div > 0.05:   score += 20; motivos.append(f"div={div:.3f}%")
    elif div > 0.02: score += 10

    # Consistência das últimas 5 velas
    ult5  = fechadas[-5:]
    bulls = sum(1 for c in ult5 if c["close"] > c["open"])
    bears = 5 - bulls
    if direcao == "CALL" and bulls >= 3:
        score += bulls * 4; motivos.append(f"{bulls}/5 bulls")
    elif direcao == "PUT" and bears >= 3:
        score += bears * 4; motivos.append(f"{bears}/5 bears")

    # Corpo médio (evita mercado lateral/doji)
    corpos = [abs(c["close"]-c["open"]) / max(c["high"]-c["low"], 0.00001) for c in ult5]
    corp_med = sum(corpos) / 5
    if corp_med > 0.5:   score += 20; motivos.append(f"corpo={corp_med*100:.0f}%")
    elif corp_med > 0.3: score += 10

    return min(100, score), direcao, " | ".join(motivos)


async def varrer_melhor_ativo(iq):
    """Varre todos os ativos abertos, pontua cada um e escolhe o melhor gráfico."""
    global ATIVO_FIXO
    estado["varrendo"]     = True
    estado["varredura_log"] = []
    await broadcast()

    # Pega payouts e status de abertura numa chamada
    def buscar_info():
        try:    payouts = iq.get_all_profit() or {}
        except: payouts = {}
        try:    open_times = iq.get_all_open_time() or {}
        except: open_times = {}
        return payouts, open_times

    payouts, open_times = await asyncio.get_event_loop().run_in_executor(None, buscar_info)
    turbo_open  = open_times.get("turbo",  {})
    binary_open = open_times.get("binary", {})

    # Filtra abertos com payout OK
    candidatos = []
    for ativo in ATIVOS_LISTA:
        base   = ativo.replace("-OTC", "")
        aberto = (turbo_open.get(ativo,{}).get("open") or turbo_open.get(base,{}).get("open") or
                  binary_open.get(ativo,{}).get("open") or binary_open.get(base,{}).get("open"))
        dados  = payouts.get(ativo) or payouts.get(base) or {}
        payout = float(dados.get("turbo") or dados.get("binary") or dados.get("digital") or 0)
        if (aberto or not open_times) and payout >= PAYOUT_MINIMO:
            candidatos.append((ativo, payout))

    if not candidatos:
        log("⚠ Varredura: nenhum ativo aberto com payout OK")
        estado["varrendo"] = False
        await broadcast()
        return None

    log(f"🔍 Varrendo {len(candidatos)} ativos...")
    estado["varredura_log"] = [f"Varrendo {len(candidatos)} ativos..."]
    await broadcast()

    # Busca candles de todos em paralelo
    tarefas = [_fetch_candles_ativo(iq, ativo, TIMEFRAME, 60) for ativo, _ in candidatos]
    resultados_candles = await asyncio.gather(*tarefas, return_exceptions=True)

    ranking = []
    for (ativo, payout), candles in zip(candidatos, resultados_candles):
        if isinstance(candles, Exception) or not candles:
            estado["varredura_log"].append(f"  {ativo}: sem candles")
            continue
        score, direcao, motivo = pontuar_ativo(candles)
        ranking.append((score, ativo, payout, direcao, motivo))
        estado["varredura_log"].append(
            f"  {'★' if score>=60 else '·'} {ativo}: {score}pts {direcao} | {motivo}"
        )
        log(f"  {ativo}: {score}pts {direcao} | {motivo}")
        await broadcast()

    estado["varrendo"] = False

    if not ranking:
        log("⚠ Varredura: nenhum ativo com candles disponíveis")
        await broadcast()
        return None

    ranking.sort(reverse=True)
    melhor_score, melhor_ativo, melhor_payout, melhor_dir, melhor_motivo = ranking[0]

    if melhor_score < 20:
        log(f"⚠ Varredura: melhor score {melhor_score}pts ({melhor_ativo}) — mercado lateral")
        await broadcast()
        return None

    log(f"✅ Varredura: escolheu {melhor_ativo} score={melhor_score}pts {melhor_dir} | {melhor_motivo}")
    estado["varredura_log"].append(f"→ Escolhido: {melhor_ativo} ({melhor_score}pts {melhor_dir})")

    if melhor_ativo != ATIVO_FIXO:
        ATIVO_FIXO = melhor_ativo
        estado["ativo_atual"] = melhor_ativo
        estado["payout_atual"] = melhor_payout
        _analise_cache.update({"vela_id": -1, "analise": None, "em_busca": False})

    await broadcast()
    return melhor_ativo


async def buscar_analise(iq):
    """Busca análise M1 + confirma com velas 15s e 30s em paralelo."""
    # Dispara as três buscas de candles ao mesmo tempo
    try:
        resultados = await asyncio.gather(
            _fetch_candles_tf(iq, TIMEFRAME, CANDLES_ANALISE),
            _fetch_candles_tf(iq, TF_30S, CANDLES_MTF),
            _fetch_candles_tf(iq, TF_15S, CANDLES_MTF),
            return_exceptions=True
        )
    except Exception as e:
        log(f"Erro buscando candles MTF: {e}")
        return None

    candles_m1 = resultados[0] if not isinstance(resultados[0], Exception) else []
    candles_30 = resultados[1] if not isinstance(resultados[1], Exception) else []
    candles_15 = resultados[2] if not isinstance(resultados[2], Exception) else []

    log(f"Candles: M1={len(candles_m1)} 30s={len(candles_30)} 15s={len(candles_15)}")

    if not candles_m1:
        log("⚠ Sem candles M1 — análise abortada")
        return None

    # Análise MTF rápida (pura EMA, sem Claude)
    mtf = analisar_mtf(candles_15, candles_30)

    # Análise principal M1
    analise = None
    if CLAUDE_KEY and not CLAUDE_KEY.startswith("sk-ant-api03-SEU"):
        analise = await analisar_com_claude(candles_m1)
        if not analise:
            log("↩ Claude sem resultado — usando EMA20/50 como fallback")

    if not analise:
        analise = analisar_ema(candles_m1)

    if not analise:
        log(f"⚠ EMA retornou None (M1 fechadas={len(candles_m1)-1 if candles_m1 else 0}, min={EMA_LENTA+2})")
        return None

    # Enriquece com dados MTF
    analise["mtf"] = mtf
    sinal = analise.get("sinal")

    if mtf["confluencia"] != "NEUTRO":
        if mtf["confluencia"] == sinal:
            # MTF confirma → sobe confiança e registra no motivo
            boost = min(8, mtf["forca"])
            analise["confianca"] = min(99, analise.get("confianca", 0) + boost)
            analise["motivo"] = f"[{mtf['motivo_mtf']}] " + analise.get("motivo", "")
            log(f"MTF confirma {sinal}: {mtf['dir_15s']}/30s:{mtf['dir_30s']} +{boost}% conf")
        elif sinal not in (None, "SKIP"):
            # MTF contradiz → reduz confiança
            analise["confianca"] = max(0, analise.get("confianca", 0) - 12)
            analise["motivo"] = f"[MTF ✗ contra:{mtf['confluencia']}] " + analise.get("motivo", "")
            log(f"MTF contradiz {sinal} ({mtf['confluencia']}) -12% conf")

    # Atualiza indicadores MTF no estado
    estado["mtf_dir15s"] = mtf["dir_15s"]
    estado["mtf_dir30s"] = mtf["dir_30s"]
    estado["mtf_conf"]   = mtf["confluencia"]

    return analise


# manter nome original para não quebrar referências internas
buscar_analise_ema = buscar_analise


# ─────────────────────────────────────────────
#  LOOP DE ANÁLISE CONTÍNUA (background)
#  Pré-busca a análise nos últimos 20s da vela
#  para que esteja pronta no segundo 0 da próxima
# ─────────────────────────────────────────────

async def loop_analise_continua(iq):
    """Corre em paralelo com loop_bot. Mantém _analise_cache sempre fresco."""
    global _analise_cache
    log("🔄 Loop análise contínua iniciado")
    while estado["rodando"]:
        await asyncio.sleep(2)
        try:
            agora = time.time()
            segundos_da_vela   = int(agora) % TIMEFRAME
            segundos_restantes = TIMEFRAME - segundos_da_vela
            proxima_vela_id    = int(agora // TIMEFRAME) + 1

            # Dispara pré-busca nos últimos 35s da vela atual (Claude precisa de tempo)
            if segundos_restantes <= 35 and not _analise_cache["em_busca"]:
                if _analise_cache["vela_id"] == proxima_vela_id:
                    continue  # já temos análise para a próxima vela

                _analise_cache["em_busca"] = True
                estado["status"] = f"⚙ Pré-analisando ({segundos_restantes}s p/ vela)"
                await broadcast()

                try:
                    resultado = await buscar_analise(iq)
                    if resultado:
                        _analise_cache = {
                            "vela_id":  proxima_vela_id,
                            "analise":  resultado,
                            "em_busca": False,
                        }
                        estado["ultima_analise"] = resultado
                        log(f"✓ Análise pré-carregada: {resultado['sinal']} {resultado.get('confianca',0)}% "
                            f"| MTF 15s:{resultado.get('mtf',{}).get('dir_15s','?')} "
                            f"30s:{resultado.get('mtf',{}).get('dir_30s','?')}")
                        await broadcast()
                    else:
                        _analise_cache["em_busca"] = False
                except Exception as e:
                    log(f"Erro análise bg: {e}")
                    _analise_cache["em_busca"] = False

        except Exception as e:
            log(f"loop_analise_continua erro: {e}")


# ─────────────────────────────────────────────
#  TIMING
# ─────────────────────────────────────────────

def modo_precheck_ativo():
    return MODO_EXECUCAO == "precheck"


def entrada_apos_segundos():
    return 0 if modo_precheck_ativo() else 1


def janela_entrada_segundos():
    return JANELA_ENTRADA_SEGUNDOS if modo_precheck_ativo() else 5


async def aguardar_abertura_proxima_vela():
    agora = int(time.time())
    segundos_da_vela = agora % TIMEFRAME
    entrada_apos  = entrada_apos_segundos()
    janela_entrada = janela_entrada_segundos()
    if segundos_da_vela < entrada_apos:
        espera = entrada_apos - segundos_da_vela
        estado["status"] = f"Aguardando movimento inicial ({espera}s)"
        await broadcast()
        await asyncio.sleep(espera)
        return
    if segundos_da_vela <= janela_entrada:
        estado["status"] = f"Entrando na vela atual ({segundos_da_vela}s)"
        await broadcast()
        return
    restante = TIMEFRAME - (agora % TIMEFRAME)
    if restante < 2:
        restante += TIMEFRAME
    estado["status"] = f"Aguardando nova vela M1 ({restante}s)"
    await broadcast()
    await asyncio.sleep(restante + 0.35)


# ─────────────────────────────────────────────
#  PREÇO / PAYOUT / BANCA / RESULTADO
# ─────────────────────────────────────────────

async def obter_preco_atual(iq, ativo):
    candles_raw = await asyncio.get_event_loop().run_in_executor(
        None, lambda: iq.get_candles(ativo, TIMEFRAME, 1, time.time())
    )
    candles = normalizar_candles(candles_raw)
    if not candles:
        return None
    return float(candles[-1]["close"])


def pontos_a_favor(direcao_sinal, preco_entrada, preco_atual):
    if preco_entrada is None or preco_atual is None:
        return 0
    if direcao_sinal == "CALL":
        return round((preco_atual - preco_entrada) * PONTOS_MULTIPLICADOR)
    return round((preco_entrada - preco_atual) * PONTOS_MULTIPLICADOR)


def classificar_resultado_provavel(pontos):
    if pontos >= PRECHECK_WIN_PONTOS:
        return "WIN_PROVAVEL"
    if pontos <= -PRECHECK_LOSS_PONTOS:
        return "LOSS_PROVAVEL"
    return "INDEFINIDO"


async def obter_banca(iq):
    return await asyncio.get_event_loop().run_in_executor(None, iq.get_balance)


async def obter_banca_com_retry(iq):
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_BANCA + 1):
        try:
            return await obter_banca(iq)
        except Exception as e:
            ultimo_erro = e
            log(f"Timeout/erro lendo banca ({tentativa}/{TENTATIVAS_BANCA}): {e}")
            await asyncio.sleep(2)
    raise RuntimeError(f"Nao consegui confirmar resultado pela banca: {ultimo_erro}")


async def obter_payout(iq, ativo):
    def buscar_payout():
        try:
            payouts = iq.get_all_profit()
            ativo_sem_otc = ativo.replace("-OTC", "")
            dados   = payouts.get(ativo) or payouts.get(ativo_sem_otc) or {}
            payout  = dados.get("turbo") or dados.get("binary") or dados.get("digital")
            return float(payout or 0)
        except Exception:
            return 0
    return await asyncio.get_event_loop().run_in_executor(None, buscar_payout)


async def escolher_ativo(iq, ativo_preferido=None, forcar_troca=False):
    """Busca payouts e status de abertura em UMA chamada, retorna primeiro ativo viável.
    Atualiza ATIVO_FIXO globalmente se trocar de ativo."""
    global ATIVO_FIXO
    preferido = ativo_preferido or ATIVO_FIXO
    # forcar_troca=True: pula o ativo atual e começa pelos alternativos
    if forcar_troca:
        lista = [a for a in ATIVOS_LISTA if a != preferido] + [preferido]
    else:
        lista = [preferido] + [a for a in ATIVOS_LISTA if a != preferido]

    def buscar_info():
        try:
            payouts = iq.get_all_profit() or {}
        except Exception:
            payouts = {}
        try:
            open_times = iq.get_all_open_time() or {}
        except Exception:
            open_times = {}
        return payouts, open_times

    payouts, open_times = await asyncio.get_event_loop().run_in_executor(None, buscar_info)

    turbo_open  = open_times.get("turbo",  {})
    binary_open = open_times.get("binary", {})

    for ativo in lista:
        try:
            base = ativo.replace("-OTC", "")
            # Verifica se mercado está aberto
            aberto = (
                turbo_open.get(ativo,  {}).get("open") or
                turbo_open.get(base,   {}).get("open") or
                binary_open.get(ativo, {}).get("open") or
                binary_open.get(base,  {}).get("open")
            )
            if open_times and not aberto:
                continue   # mercado fechado, tenta próximo

            # Verifica payout
            dados  = payouts.get(ativo) or payouts.get(base) or {}
            payout = float(dados.get("turbo") or dados.get("binary") or dados.get("digital") or 0)
            if payout < PAYOUT_MINIMO:
                continue

            if ativo != ATIVO_FIXO:
                log(f"🔀 Ativo → {ativo} payout={payout*100:.0f}% (era {ATIVO_FIXO}, fechado/baixo)")
                ATIVO_FIXO = ativo
                estado["ativo_atual"] = ativo
                _analise_cache.update({"vela_id": -1, "analise": None, "em_busca": False})
            return ativo, payout
        except Exception:
            pass

    return None, 0.0


async def obter_lucro_por_id(iq, id_op):
    def consultar():
        metodos = ("check_win_v4", "check_win_v3", "check_win_v2", "check_win")
        ultimo_erro = None
        for nome in metodos:
            fn = getattr(iq, nome, None)
            if not callable(fn):
                continue
            try:
                r = fn(id_op)
                if isinstance(r, tuple):
                    for item in reversed(r):
                        try:
                            return round(float(item), 2)
                        except Exception:
                            pass
                return round(float(r), 2)
            except Exception as e:
                ultimo_erro = e
        if ultimo_erro:
            raise ultimo_erro
        raise RuntimeError("Biblioteca sem metodo check_win disponivel")
    return await asyncio.get_event_loop().run_in_executor(None, consultar)


# ─────────────────────────────────────────────
#  MARTINGALE
# ─────────────────────────────────────────────

def calcular_stake_mg():
    return round(STAKE_INICIAL * (MG_FATOR ** estado["mg_nivel"]), 2)


# ─────────────────────────────────────────────
#  APRENDIZADO ADAPTATIVO
# ─────────────────────────────────────────────

def atualizar_aprendizado(sinal_executado, ganhou):
    """Analisa histórico recente e auto-ajusta direção de sinal."""
    ap = estado["aprendizado"]

    # Contadores por direção
    if sinal_executado == "CALL":
        ap["call_total"] += 1
        if ganhou:
            ap["call_wins"] += 1
    elif sinal_executado == "PUT":
        ap["put_total"] += 1
        if ganhou:
            ap["put_wins"] += 1

    # Win rate das últimas N operações
    recent = estado["historico"][-APRENDIZADO_JANELA:]
    if len(recent) < 5:
        return
    wins = sum(1 for t in recent if t["resultado"] == "WIN")
    taxa = wins / len(recent)
    ap["taxa_recente"] = round(taxa, 3)

    c_rate = ap["call_wins"] / ap["call_total"] if ap["call_total"] > 0 else 0.5
    p_rate = ap["put_wins"]  / ap["put_total"]  if ap["put_total"]  > 0 else 0.5

    # Auto-inversão: win rate sistematicamente baixo → sinais estão invertidos
    if taxa < APRENDIZADO_THRESH_INV and not estado["inverter_tudo"]:
        estado["inverter_tudo"] = True
        ap["auto_inverter"]     = True
        log(f"🔄 APRENDIZADO: auto-inversão ATIVADA | win={taxa*100:.0f}% "
            f"CALL={c_rate*100:.0f}% PUT={p_rate*100:.0f}%")

    elif taxa > APRENDIZADO_THRESH_OK and ap.get("auto_inverter"):
        estado["inverter_tudo"] = False
        ap["auto_inverter"]     = False
        log(f"✅ APRENDIZADO: inversão REMOVIDA | win recuperou {taxa*100:.0f}%")

    # Feedback no log a cada 5 trades
    if len(recent) % 5 == 0:
        log(f"📊 Aprendizado: {taxa*100:.0f}% win/{len(recent)} trades | "
            f"CALL {c_rate*100:.0f}% ({ap['call_wins']}/{ap['call_total']}) "
            f"PUT {p_rate*100:.0f}% ({ap['put_wins']}/{ap['put_total']}) "
            f"{'[INVERTIDO]' if estado['inverter_tudo'] else ''}")


def stats_padroes():
    """Agrega win rate por padrão e por faixa de hora nas últimas 30 operações."""
    hist = estado["historico"][-30:]
    if not hist:
        return {}, {}

    # Por padrão de análise
    padroes: dict = {}
    for t in hist:
        p = (t.get("padrao") or "EMA").split(" ")[0][:20]   # pega só o nome curto
        if p not in padroes:
            padroes[p] = {"wins": 0, "total": 0}
        padroes[p]["total"] += 1
        if t.get("resultado") == "WIN":
            padroes[p]["wins"] += 1

    # Por faixa de hora (ex: "08h", "14h")
    horas: dict = {}
    for t in hist:
        hora = t.get("hora", "")
        faixa = hora[:2] + "h" if hora else "?h"
        if faixa not in horas:
            horas[faixa] = {"wins": 0, "total": 0}
        horas[faixa]["total"] += 1
        if t.get("resultado") == "WIN":
            horas[faixa]["wins"] += 1

    return padroes, horas


def resumo_aprendizado():
    """Retorna texto para incluir no prompt Claude com histórico de padrões."""
    ap = estado["aprendizado"]
    recent = estado["historico"][-APRENDIZADO_JANELA:]
    if len(recent) < 3:
        return ""

    wins = sum(1 for t in recent if t["resultado"] == "WIN")
    taxa = wins / len(recent)
    c_rate = ap["call_wins"] / ap["call_total"] if ap["call_total"] > 0 else None
    p_rate = ap["put_wins"]  / ap["put_total"]  if ap["put_total"]  > 0 else None

    linhas = [f"HISTORICO RECENTE ({len(recent)} trades): {taxa*100:.0f}% win rate"]
    if c_rate is not None:
        linhas.append(f"Precisao CALL: {c_rate*100:.0f}% ({ap['call_wins']}/{ap['call_total']})")
    if p_rate is not None:
        linhas.append(f"Precisao PUT:  {p_rate*100:.0f}% ({ap['put_wins']}/{ap['put_total']})")
    if taxa < 0.40:
        linhas.append("ATENCAO: win rate baixo — revise a direcao do sinal com cuidado.")

    # Padrões
    padroes, horas = stats_padroes()
    if padroes:
        linhas.append("PADROES (ultimas 30 ops):")
        for nome, s in sorted(padroes.items(), key=lambda x: -x[1]["total"]):
            r = s["wins"] / s["total"]
            emoji = "✓" if r >= 0.55 else ("✗" if r < 0.35 else "~")
            linhas.append(f"  {emoji} {nome}: {r*100:.0f}% ({s['wins']}/{s['total']})")

    # Melhor/pior horário
    if horas:
        melhores = sorted(horas.items(), key=lambda x: x[1]["wins"]/x[1]["total"] if x[1]["total"]>0 else 0, reverse=True)
        melhor = melhores[0]
        pior   = melhores[-1]
        hora_atual = datetime.now().strftime("%H") + "h"
        linhas.append(f"HORARIOS: melhor={melhor[0]} ({melhor[1]['wins']}/{melhor[1]['total']}) "
                      f"pior={pior[0]} ({pior[1]['wins']}/{pior[1]['total']}) "
                      f"agora={hora_atual}")

    return "\n".join(linhas)


def on_ganho(lucro_op, sinal=""):
    estado["ganhos"]      += 1
    estado["mg_nivel"]     = 0
    estado["stake_atual"]  = STAKE_INICIAL
    estado["loss_seq"]     = 0
    estado["gale_pausado"] = False
    log(f"WIN ${lucro_op:.2f} - MG resetado para ${STAKE_INICIAL:.2f}")
    if sinal:
        atualizar_aprendizado(sinal, ganhou=True)
    salvar_estado_runtime()


def on_perda(sinal=""):
    estado["perdas"]   += 1
    estado["mg_nivel"] += 1
    estado["loss_seq"] += 1
    if sinal:
        atualizar_aprendizado(sinal, ganhou=False)
    if estado["mg_nivel"] >= MG_NIVEIS:
        log(f"LOSS - atingiu MG {MG_NIVEIS}. Stop de sequencia.")
        estado["status"]      = "stop_loss"
        estado["rodando"]     = False
        estado["stake_atual"] = STAKE_INICIAL
        salvar_estado_runtime()
        return
    estado["stake_atual"] = calcular_stake_mg()
    if estado["loss_seq"] >= estado["max_loss_seq"]:
        estado["gale_pausado"] = True
        log(f"⏸ {estado['loss_seq']} losses seguidos → PAUSADO. Aguardando setup limpo (conf≥80%)...")
    else:
        log(f"LOSS - MG nivel {estado['mg_nivel']} proxima ${estado['stake_atual']:.2f}")
    salvar_estado_runtime()


def reset_contadores():
    estado["ganhos"]       = 0
    estado["perdas"]       = 0
    estado["mg_nivel"]     = 0
    estado["soros_nivel"]  = 0
    estado["stake_atual"]  = STAKE_INICIAL
    estado["lucro"]        = 0.0
    estado["historico"]    = []
    estado["ultima_operacao"] = None
    estado["ultima_analise"]  = None
    estado["crono_entrada"]   = 0
    estado["crono_sessao"]    = 0
    estado["loss_seq"]        = 0
    estado["gale_pausado"]    = False
    estado["aprendizado"]     = {
        "call_wins": 0, "call_total": 0,
        "put_wins": 0,  "put_total": 0,
        "auto_inverter": False, "taxa_recente": 0.0,
    }
    log("Contadores resetados.")
    salvar_estado_runtime()


# ─────────────────────────────────────────────
#  PERSISTÊNCIA
# ─────────────────────────────────────────────

def salvar_config_arquivo():
    dados = {
        "ativo":         ATIVO_FIXO,
        "stake":         STAKE_INICIAL,
        "mg_fator":      MG_FATOR,
        "mg_niveis":     MG_NIVEIS,
        "stop_loss":     STOP_LOSS,
        "stop_gain":     STOP_GAIN,
        "demo":          CONTA_DEMO,
        "payout_minimo": PAYOUT_MINIMO,
        "modo_execucao": MODO_EXECUCAO,
        "claude_key":    CLAUDE_KEY,
        "max_loss_seq":  MAX_LOSS_SEQ,
        "confianca_min": CONFIANCA_MIN_CLAUDE,
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def salvar_estado_runtime():
    dados = {
        "banca_inicial":   estado["banca_inicial"],
        "banca_atual":     estado["banca_atual"],
        "lucro":           estado["lucro"],
        "ganhos":          estado["ganhos"],
        "perdas":          estado["perdas"],
        "mg_nivel":        estado["mg_nivel"],
        "stake_atual":     estado["stake_atual"],
        "loss_seq":        estado["loss_seq"],
        "ultima_operacao": estado["ultima_operacao"],
        "ultima_analise":  estado["ultima_analise"],
        "historico":       estado["historico"][-300:],
        "ativo_atual":     estado["ativo_atual"],
        "tf_atual":        estado["tf_atual"],
        "salvo_em":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Erro salvando estado: {e}")


def carregar_estado_runtime():
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        for chave in (
            "banca_inicial", "banca_atual", "lucro", "ganhos", "perdas",
            "mg_nivel", "stake_atual", "loss_seq", "ultima_operacao",
            "ultima_analise", "historico", "ativo_atual", "tf_atual"
        ):
            if chave in dados:
                estado[chave] = dados[chave]
        estado["rodando"]     = False
        estado["trade_ativo"] = False
        estado["status"]      = f"Estado recuperado ({dados.get('salvo_em', 'sem hora')})"
        log(f"Estado recuperado: MG {estado['mg_nivel']} | stake ${estado['stake_atual']:.2f} | loss_seq={estado['loss_seq']}")
    except Exception as e:
        log(f"Erro carregando estado salvo: {e}")


# ─────────────────────────────────────────────
#  WEBSOCKET HANDLER
# ─────────────────────────────────────────────

async def handler_ws(websocket):
    global bot_task
    global STAKE_INICIAL, MG_FATOR, MG_NIVEIS, STOP_LOSS, STOP_GAIN
    global CONTA_DEMO, PAYOUT_MINIMO, MODO_EXECUCAO
    global CLAUDE_KEY, MAX_LOSS_SEQ, CONFIANCA_MIN_CLAUDE
    global ultima_direcao_valida

    clientes_ws.add(websocket)
    try:
        await broadcast()
        async for msg in websocket:
            data = json.loads(msg)
            cmd  = data.get("cmd")

            if cmd == "start" and not estado["rodando"] and not (bot_task and not bot_task.done()):
                estado["sessao_inicio"]   = time.time()
                ultima_direcao_valida     = None
                log(f"Iniciando: MG {estado['mg_nivel']} | stake ${estado['stake_atual']:.2f}")
                bot_task = asyncio.create_task(loop_bot())

            elif cmd == "start":
                log("Start ignorado: bot ja esta rodando.")

            elif cmd in ("stop", "shutdown"):
                estado["rodando"] = False
                estado["status"]  = "Parando apos operacao atual..." if estado["trade_ativo"] else "parado"
                log("Bot parado.")
                await broadcast()

            elif cmd == "reset":
                reset_contadores()
                salvar_estado_runtime()
                await broadcast()

            elif cmd == "retomar":
                estado["gale_pausado"] = False
                estado["loss_seq"]     = 0
                log("▶ Retomado manualmente pelo usuario")
                await broadcast()

            elif cmd == "inverter":
                estado["inverter_tudo"] = bool(data.get("ativo", False))
                log(f"Inverter sinal: {'ON' if estado['inverter_tudo'] else 'OFF'}")
                await broadcast()

            elif cmd == "config":
                STAKE_INICIAL        = max(STAKE_MINIMA, float(data.get("stake", STAKE_INICIAL)))
                MG_FATOR             = float(data.get("mg_fator", MG_FATOR))
                MG_NIVEIS            = int(data.get("mg_niveis", MG_NIVEIS))
                STOP_LOSS            = float(data.get("stop_loss", STOP_LOSS))
                STOP_GAIN            = float(data.get("stop_gain", STOP_GAIN))
                CONTA_DEMO           = bool(data.get("demo", CONTA_DEMO))
                PAYOUT_MINIMO        = float(data.get("payout_minimo", PAYOUT_MINIMO))
                MODO_EXECUCAO        = str(data.get("modo_execucao", MODO_EXECUCAO))
                CLAUDE_KEY           = str(data.get("claude_key", CLAUDE_KEY)) if data.get("claude_key") else CLAUDE_KEY
                MAX_LOSS_SEQ         = int(data.get("max_loss_seq", MAX_LOSS_SEQ))
                CONFIANCA_MIN_CLAUDE = int(data.get("confianca_min", CONFIANCA_MIN_CLAUDE))
                estado["max_loss_seq"]  = MAX_LOSS_SEQ
                estado["confianca_min"] = CONFIANCA_MIN_CLAUDE
                if not estado["rodando"] and not estado["trade_ativo"]:
                    estado["stake_atual"] = STAKE_INICIAL
                    estado["mg_nivel"]    = 0
                salvar_config_arquivo()
                log(f"Config salva: stake=${STAKE_INICIAL:.2f} MG={MG_FATOR}x{MG_NIVEIS} pausa>{MAX_LOSS_SEQ} conf>={CONFIANCA_MIN_CLAUDE}% claude={'OK' if CLAUDE_KEY and not CLAUDE_KEY.startswith('sk-ant-api03-SEU') else 'SEM CHAVE'}")
                await broadcast()

    except Exception:
        pass
    finally:
        clientes_ws.discard(websocket)


# ─────────────────────────────────────────────
#  LOOP PRINCIPAL
# ─────────────────────────────────────────────

async def loop_bot():
    global ATIVO_FIXO
    if estado["rodando"]:
        return

    estado["rodando"] = True
    estado["status"]  = "Conectando na IQ Option..."
    await broadcast()

    analise_bg_task = None  # garante que existe no finally mesmo se conexão falhar
    try:
        from iqoptionapi.stable_api import IQ_Option
        import nest_asyncio
        nest_asyncio.apply()

        log("Conectando na IQ Option...")
        iq = IQ_Option(IQ_EMAIL, IQ_PASSWORD)
        check, reason = await asyncio.get_event_loop().run_in_executor(None, iq.connect)
        if not check:
            estado["status"]  = f"Erro: {reason}"
            estado["rodando"] = False
            log(f"Falha ao conectar: {reason}")
            await broadcast()
            return

        iq.change_balance("PRACTICE" if CONTA_DEMO else "REAL")
        banca = await obter_banca_com_retry(iq)
        if estado["banca_inicial"] <= 0 or not estado["historico"]:
            estado["banca_inicial"] = banca
        estado["banca_atual"] = banca
        estado["lucro"]       = estado["banca_atual"] - estado["banca_inicial"]
        estado["ativo_atual"] = ATIVO_FIXO
        estado["tf_atual"]    = "M1"
        log(f"Conectado. Banca ${banca:.2f} | {'DEMO' if CONTA_DEMO else 'REAL'} | {ATIVO_FIXO}")
        salvar_estado_runtime()

        # Limpa cache e inicia loop de análise em background
        _analise_cache.update({"vela_id": -1, "analise": None, "em_busca": False})
        analise_bg_task = asyncio.create_task(loop_analise_continua(iq))

        # Varredura inicial — escolhe o melhor ativo antes de começar
        log("🔍 Iniciando varredura de ativos...")
        await varrer_melhor_ativo(iq)

        falhas_consecutivas = 0   # conta falhas de análise para re-varrer

        while estado["rodando"]:
            estado["lucro"] = estado["banca_atual"] - estado["banca_inicial"]
            if STOP_LOSS > 0 and estado["lucro"] <= -abs(STOP_LOSS):
                estado["status"] = "stop_loss"
                log(f"Stop Loss atingido: ${estado['lucro']:.2f}")
                break
            if STOP_GAIN > 0 and estado["lucro"] >= abs(STOP_GAIN):
                estado["status"] = "stop_gain"
                log(f"Stop Gain atingido: ${estado['lucro']:.2f}")
                break

            await aguardar_abertura_proxima_vela()
            if not estado["rodando"]:
                break

            # Verifica payout do ativo atual; troca se necessário
            ativo_ok, payout_ok = await escolher_ativo(iq)
            if not ativo_ok:
                log(f"⚠ Nenhum ativo com payout >= {PAYOUT_MINIMO*100:.0f}% — aguardando")
                estado["status"] = "Sem ativo viável — aguardando"
                await broadcast()
                await asyncio.sleep(30)
                continue
            estado["payout_atual"] = payout_ok

            vela_atual_id = int(time.time() // TIMEFRAME)
            if _analise_cache["vela_id"] == vela_atual_id and _analise_cache["analise"]:
                analise = _analise_cache["analise"]
                _analise_cache.update({"vela_id": -1, "analise": None, "em_busca": False})
                log(f"✓ Análise pré-carregada usada: {analise['sinal']} {analise.get('confianca',0)}% "
                    f"| MTF 15s:{analise.get('mtf',{}).get('dir_15s','?')} "
                    f"30s:{analise.get('mtf',{}).get('dir_30s','?')}")
            elif _analise_cache["em_busca"]:
                # Análise Claude ainda rodando — faz EMA imediato para não perder vela
                log("⚠ Análise bg em andamento — EMA M1 imediato para não perder vela")
                try:
                    candles_ema = await _fetch_candles_tf(iq, TIMEFRAME, CANDLES_ANALISE)
                    analise = analisar_ema(candles_ema) if candles_ema else None
                except Exception as e:
                    log(f"Erro EMA fallback: {e}")
                    analise = None
            else:
                # Sem cache — busca agora
                log("⚠ Sem cache — buscando análise agora")
                try:
                    analise = await buscar_analise(iq)
                except Exception as e:
                    log(f"Erro buscando análise: {e}")
                    analise = None

            # ── Se análise falhou → troca ativo ou re-varre ──────
            if not analise:
                falhas_consecutivas += 1
                if falhas_consecutivas >= 3:
                    # 3 falhas seguidas → re-varre todos os ativos
                    log(f"⚠ {falhas_consecutivas} falhas seguidas — re-varrendo ativos")
                    await varrer_melhor_ativo(iq)
                    falhas_consecutivas = 0
                    try:
                        analise = await buscar_analise(iq)
                    except Exception:
                        analise = None
                else:
                    log(f"⚠ Sem análise para {ATIVO_FIXO} — tentando ativo alternativo")
                    novo, _ = await escolher_ativo(iq, forcar_troca=True)
                    if novo:
                        log(f"🔀 Trocou para {ATIVO_FIXO} — buscando análise")
                        estado["status"] = f"Trocou → {ATIVO_FIXO}"
                        await broadcast()
                        try:
                            analise = await buscar_analise(iq)
                        except Exception:
                            analise = None
            else:
                falhas_consecutivas = 0   # análise OK — zera contador

            # ── LÓGICA DE PAUSA ──────────────────────────────
            if estado["gale_pausado"]:
                conf_ok = analise and analise.get("confianca", 0) >= 80 and analise.get("sinal") not in (None, "SKIP")
                if conf_ok:
                    estado["gale_pausado"] = False
                    estado["loss_seq"]     = 0
                    log(f"▶ RETOMANDO: {analise['sinal']} {analise['confianca']}% setup limpo detectado")
                else:
                    conf = analise.get("confianca", 0) if analise else 0
                    sinal_txt = analise.get("sinal", "?") if analise else "sem analise"
                    estado["status"] = f"⏸ PAUSADO ({estado['loss_seq']} losses) — {sinal_txt} {conf}%"
                    log(f"⏸ PAUSADO — {sinal_txt} {conf}% — aguardando proxima vela")
                    await broadcast()
                    agora = int(time.time())
                    await asyncio.sleep(TIMEFRAME - (agora % TIMEFRAME) + 1)
                    continue
            # ─────────────────────────────────────────────────

            if not analise:
                log("⚠ Sem análise em nenhum ativo — aguardando próxima vela")
                estado["status"] = "Sem análise — aguardando vela"
                await broadcast()
                await asyncio.sleep(5)
                continue

            sinal  = analise["sinal"]
            direcao = "call" if sinal == "CALL" else "put"
            stake  = round(float(estado["stake_atual"]), 2)
            estado["ultima_analise"] = analise
            estado["status"]         = f"Executando {sinal} {ATIVO_FIXO} ${stake:.2f}"
            estado["trade_ativo"]    = True
            estado["crono_entrada"]  = 0
            await broadcast()

            log(f"{sinal} | {ATIVO_FIXO} M1 | ${stake:.2f} | {analise.get('motivo','')[:80]}")

            try:
                try:
                    check, id_op = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: iq.buy(stake, ATIVO_FIXO, direcao, EXPIRACAO_MIN)
                    )
                except Exception as _buy_err:
                    if "Timeout" in str(_buy_err) or "timeout" in str(_buy_err):
                        estado["trade_ativo"] = False
                        estado["rodando"]     = False
                        estado["status"]      = "timeout_compra"
                        log(f"Timeout ao abrir trade. Parando.")
                        await broadcast()
                        break
                    raise

                if not check:
                    estado["trade_ativo"] = False
                    log("Falha ao abrir trade. Tentando proxima vela.")
                    await broadcast()
                    continue

                preco_entrada = None
                try:
                    preco_entrada = await obter_preco_atual(iq, ATIVO_FIXO)
                except Exception as e:
                    log(f"Nao consegui capturar preco de entrada: {e}")

                estado["ultima_operacao"] = {
                    "id":     id_op,
                    "dir":    sinal,
                    "stake":  stake,
                    "hora":   datetime.now().strftime("%H:%M:%S"),
                    "padrao": analise.get("padrao", ""),
                    "ativo":  ATIVO_FIXO,
                    "preco_entrada": preco_entrada,
                    "forca":  analise.get("forca", "NORMAL"),
                }
                salvar_estado_runtime()
                await broadcast()

                fim_espera    = time.time() + (EXPIRACAO_MIN * 60) + FOLGA_RESULTADO_SEGUNDOS
                vela_entrada_id = int(time.time() // TIMEFRAME)
                precheck_feito  = False

                while estado["rodando"] and time.time() < fim_espera:
                    await asyncio.sleep(min(1, max(0.1, fim_espera - time.time())))
                    restante_expiracao = fim_espera - time.time()
                    vela_agora_id      = int(time.time() // TIMEFRAME)
                    segundos_da_vela   = int(time.time()) % TIMEFRAME

                    if (
                        PRECHECK_RESULTADO
                        and modo_precheck_ativo()
                        and not precheck_feito
                        and restante_expiracao <= PRECHECK_SEGUNDOS_ANTES
                    ):
                        precheck_feito = True
                        try:
                            preco_agora = await obter_preco_atual(iq, ATIVO_FIXO)
                            pts         = pontos_a_favor(sinal, preco_entrada, preco_agora)
                            provavel    = classificar_resultado_provavel(pts)
                            if estado["ultima_operacao"]:
                                estado["ultima_operacao"]["preco_precheck"]     = preco_agora
                                estado["ultima_operacao"]["pontos_precheck"]    = pts
                                estado["ultima_operacao"]["resultado_provavel"] = provavel
                            estado["status"] = f"{provavel} faltando {PRECHECK_SEGUNDOS_ANTES}s | {pts} pts"
                            log(f"Precheck {provavel}: {pts} pts | entrada={preco_entrada} atual={preco_agora}")
                            salvar_estado_runtime()
                            await broadcast()
                        except Exception as e:
                            log(f"Erro precheck resultado: {e}")

                    # Preparação da próxima análise gerenciada por loop_analise_continua

                if not estado["rodando"]:
                    break

                try:
                    lucro_op = await obter_lucro_por_id(iq, id_op)
                    try:
                        banca_nova        = await obter_banca(iq)
                        estado["banca_atual"] = banca_nova
                        estado["lucro"]   = banca_nova - estado["banca_inicial"]
                    except Exception:
                        estado["lucro"]       = estado["lucro"] + lucro_op
                        estado["banca_atual"] = estado["banca_atual"] + lucro_op
                    log(f"Resultado por ID: ${lucro_op:.2f}")
                except Exception as e_id:
                    log(f"Resultado por ID indisponivel: {e_id}. Usando banca.")
                    try:
                        banca_nova = await obter_banca_com_retry(iq)
                    except Exception as e:
                        estado["trade_ativo"] = False
                        estado["rodando"]     = False
                        estado["status"]      = "resultado_desconhecido"
                        log(f"Resultado desconhecido: {e}. Parando para evitar gale errado.")
                        await broadcast()
                        break
                    lucro_op              = round(banca_nova - estado["banca_atual"], 2)
                    estado["banca_atual"] = banca_nova
                    estado["lucro"]       = banca_nova - estado["banca_inicial"]

                resultado = "WIN" if lucro_op > 0 else "LOSS"
                estado["ultima_operacao"]["resultado"] = resultado
                estado["ultima_operacao"]["lucro_op"]  = lucro_op
                estado["historico"].append({
                    "hora":      datetime.now().strftime("%H:%M"),
                    "ativo":     ATIVO_FIXO,
                    "tf":        "M1",
                    "dir":       sinal,
                    "stake":     stake,
                    "resultado": resultado,
                    "lucro":     lucro_op,
                    "padrao":    analise.get("padrao", ""),
                    "confianca": analise.get("confianca", 0),
                    "mg_nivel":  estado["mg_nivel"],
                    "forca":     analise.get("forca", "NORMAL"),
                })

                if lucro_op > 0:
                    on_ganho(lucro_op, sinal=sinal)
                else:
                    on_perda(sinal=sinal)

                estado["trade_ativo"] = False
                await broadcast()

            except Exception as e:
                estado["trade_ativo"] = False
                log(f"Erro trade: {e}")
                await broadcast()
                await asyncio.sleep(5)

    except Exception as e:
        estado["status"] = f"Erro: {e}"
        log(f"Erro critico: {e}")
    finally:
        estado["rodando"]     = False
        estado["trade_ativo"] = False
        if analise_bg_task is not None and not analise_bg_task.done():
            analise_bg_task.cancel()
        if estado["status"] not in ("stop_gain", "stop_loss") and not str(estado["status"]).startswith("Erro:"):
            estado["status"] = "parado"
        log("Bot Claude M1 encerrado.")
        await broadcast()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

async def main():
    import websockets
    carregar_estado_runtime()
    log("IQBOT Claude M1 iniciando...")
    log(f"Dashboard WS em ws://localhost:{DASHBOARD_PORT}")
    log(f"Ativo: {ATIVO_FIXO} | MG {MG_FATOR}x{MG_NIVEIS} | pausa>{MAX_LOSS_SEQ} losses | conf>={CONFIANCA_MIN_CLAUDE}%")
    log(f"Claude: {'ATIVO' if CLAUDE_KEY and not CLAUDE_KEY.startswith('sk-ant-api03-SEU') else 'SEM CHAVE — usando EMA fallback'}")
    asyncio.create_task(loop_cronometro())
    async with websockets.serve(handler_ws, "0.0.0.0", DASHBOARD_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
