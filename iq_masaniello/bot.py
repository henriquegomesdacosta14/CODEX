"""
IQBOT — Masaniello + Claude AI Vision
IQ Option + Anthropic Vision API + Masaniello stake management
"""

import asyncio
import json
import time
import base64
import io
from math import lgamma, exp
from datetime import datetime
from collections import deque

# ════════════════════════════════════
#  CONFIGURAÇÕES
# ════════════════════════════════════
IQ_EMAIL    = "SEU_EMAIL@exemplo.com"
IQ_PASSWORD = "SUA_SENHA"
CLAUDE_KEY  = "sk-ant-api03-SEU_CLAUDE_API_KEY"

# Masaniello
BANCA_TRABALHO = 480.0
META_CICLO     = 70.0
TOTAL_OPS      = 7
MIN_WINS       = 4
ENTRADA_MIN    = 2.0

# Trading
CONTA_DEMO      = True
DASHBOARD_PORT  = 8765
CANDLES_ANALISE = 30        # precisa de pelo menos 21 para SMA21
CONFIANCA_MIN   = 75
TIMEFRAMES      = [60, 120]
STOP_SESSAO     = 100.0
SO_TENDENCIA    = False
INVERTER_TUDO   = False
MODO_ATIVOS     = "auto"    # "auto" | "forex" | "otc"
PADROES_INVERTER = ['bearish engulfing','bearish engolfo','three black crows','três corvos negros']

# ════════════════════════════════════
#  ESTADO
# ════════════════════════════════════
estado = {
    # Bot
    "rodando":        False,
    "banca_atual":    0.0,
    "banca_sessao":   0.0,   # banca no início da sessão (para stop sessão)
    "lucro_sessao":   0.0,
    "ganhos":         0,
    "perdas":         0,
    "stake_atual":    ENTRADA_MIN,
    "payout_atual":   0.85,

    # Masaniello ciclo
    "ciclo_num":          0,
    "op_atual":           1,
    "wins_ciclo":         0,
    "losses_ciclo":       0,
    "ciclo_resultados":   [],   # sequência real: ["W","L","L","W",...]
    "banca_inicio_ciclo": BANCA_TRABALHO,
    "cycle_status":       "AGUARDANDO",
    "proxima":            0.0,
    "cofre":              0.0,
    "ciclos_ganhos":      0,
    "ciclos_perdidos":    0,

    # Params (ajustáveis pelo dashboard)
    "banca_trabalho": BANCA_TRABALHO,
    "meta_ciclo":     META_CICLO,
    "total_ops":      TOTAL_OPS,
    "min_wins":       MIN_WINS,

    # Claude API
    "api_credito":  0.0,
    "api_gasto":    0.0,
    "api_chamadas": 0,
    "api_alerta":   False,

    # Trade
    "ativo_atual":     "—",
    "tf_atual":        "—",
    "varrendo":        False,
    "varredura_log":   [],
    "historico":       [],
    "status":          "Aguardando...",
    "log":             deque(maxlen=100),
    "crono_entrada":   0,
    "crono_sessao":    0,
    "trade_ativo":     False,
    "sessao_inicio":   0,
    "ultima_operacao": None,
    "ultima_analise":  None,

    # Controles
    "inverter_tudo":        False,
    "inverter_tendencia":   False,
    "inverter_three_black": False,
    "so_tendencia":         False,
    "modo_ativos":          "auto",   # auto | forex | otc

    # EMA info (último filtro)
    "ema3":  0.0,
    "ema10": 0.0,
    "sma21": 0.0,
}

clientes_ws = set()

# ════════════════════════════════════
#  MASANIELLO
# ════════════════════════════════════
def _logComb(n, k):
    if k < 0 or k > n: return float('-inf')
    if k == 0 or k == n: return 0.0
    return lgamma(n+1) - lgamma(k+1) - lgamma(n-k+1)

def calcular_proxima():
    op    = estado["op_atual"]
    total = estado["total_ops"]
    wins  = estado["wins_ciclo"]
    min_w = estado["min_wins"]
    pay   = max(0.01, estado["payout_atual"])
    saldo = estado["banca_atual"]
    tgt   = estado["banca_inicio_ciclo"] + estado["meta_ciclo"]

    rem_ops  = total - op + 1
    rem_wins = max(0, min_w - wins)

    if rem_ops <= 0 or rem_wins <= 0 or rem_wins > rem_ops:
        return 0.0

    divisor = pay * exp(_logComb(rem_ops - 1, rem_wins - 1))
    if divisor <= 0:
        return 0.0

    return max(ENTRADA_MIN, round((tgt - saldo) / divisor, 2))

def _status_ciclo():
    wins  = estado["wins_ciclo"]
    min_w = estado["min_wins"]
    op    = estado["op_atual"]
    total = estado["total_ops"]
    if wins >= min_w:
        return "META"
    rem_ops  = total - op + 1
    rem_wins = min_w - wins
    if rem_wins > rem_ops:
        return "QUEBRADO"
    return "ANDAMENTO"

def on_win(lucro_op=0):
    estado["ciclo_resultados"].append("W")
    estado["ganhos"]     += 1
    estado["wins_ciclo"] += 1
    estado["op_atual"]   += 1
    s = _status_ciclo()
    estado["cycle_status"] = s
    if s != "ANDAMENTO":
        asyncio.get_event_loop().create_task(_processar_fim_ciclo(s))
    else:
        estado["proxima"] = calcular_proxima()
    log(f"✅ WIN {estado['wins_ciclo']}W/{estado['losses_ciclo']}L | Próx: ${estado['proxima']:.2f}")

def on_loss():
    estado["ciclo_resultados"].append("L")
    estado["perdas"]       += 1
    estado["losses_ciclo"] += 1
    estado["op_atual"]     += 1
    s = _status_ciclo()
    estado["cycle_status"] = s
    if s != "ANDAMENTO":
        asyncio.get_event_loop().create_task(_processar_fim_ciclo(s))
    else:
        estado["proxima"] = calcular_proxima()
    log(f"❌ LOSS {estado['wins_ciclo']}W/{estado['losses_ciclo']}L | Próx: ${estado['proxima']:.2f}")

async def _processar_fim_ciclo(status):
    lucro = round(estado["banca_atual"] - estado["banca_inicio_ciclo"], 2)
    if status == "META":
        estado["cofre"]        = round(estado["cofre"] + lucro, 2)
        estado["ciclos_ganhos"] += 1
        log(f"🏆 CICLO #{estado['ciclo_num']} META! +${lucro:.2f} → Cofre: ${estado['cofre']:.2f}")
        if estado["ciclos_ganhos"] % 10 == 0:
            log(f"💰 {estado['ciclos_ganhos']} ciclos! Cofre total: ${estado['cofre']:.2f}")
    else:
        estado["ciclos_perdidos"] += 1
        log(f"💔 CICLO #{estado['ciclo_num']} QUEBRADO | {lucro:+.2f}")

    await asyncio.sleep(8)
    estado["ciclo_num"]          += 1
    estado["op_atual"]            = 1
    estado["wins_ciclo"]          = 0
    estado["losses_ciclo"]        = 0
    estado["ciclo_resultados"]    = []
    estado["banca_inicio_ciclo"]  = estado["banca_atual"]
    estado["cycle_status"]        = "ANDAMENTO"
    estado["proxima"]             = calcular_proxima()
    log(f"🔄 CICLO #{estado['ciclo_num']} | Banca: ${estado['banca_atual']:.2f} | Meta: +${estado['meta_ciclo']:.2f}")
    await broadcast()

# ════════════════════════════════════
#  CRONÔMETROS
# ════════════════════════════════════
async def loop_cronometro():
    while True:
        await asyncio.sleep(1)
        if estado["trade_ativo"]:
            estado["crono_entrada"] += 1
        if estado["rodando"] and estado["sessao_inicio"] > 0:
            estado["crono_sessao"] = int(time.time() - estado["sessao_inicio"])
        await broadcast()

# ════════════════════════════════════
#  GRÁFICO
# ════════════════════════════════════
def gerar_grafico_base64(candles, titulo=""):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor('#0c0f1a')
        ax.set_facecolor('#0c0f1a')

        for i, c in enumerate(candles):
            o, h, l, cl = c['open'], c['high'], c['low'], c['close']
            cor = '#00e5a0' if cl >= o else '#ff3e6c'
            ax.plot([i, i], [l, h], color=cor, linewidth=1.2)
            rect = mpatches.FancyBboxPatch(
                (i-0.35, min(o,cl)), 0.7, max(abs(cl-o), 0.00001),
                boxstyle="square,pad=0", facecolor=cor, edgecolor=cor
            )
            ax.add_patch(rect)

        ax.set_xlim(-1, len(candles))
        ax.tick_params(colors='#6b7aa0', labelsize=8)
        for s in ['top','right']: ax.spines[s].set_visible(False)
        for s in ['bottom','left']: ax.spines[s].set_color('#1e2540')
        ax.yaxis.grid(True, color='#1e2540', linewidth=0.5)
        ax.set_title(titulo, color='#dde4f8', fontsize=11)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor='#0c0f1a', dpi=90)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        log(f"Erro gráfico: {e}")
        return None

# ════════════════════════════════════
#  CLAUDE — ANÁLISE VISION
# ════════════════════════════════════
async def analisar_ativo(candles, ativo, timeframe):
    import urllib.request, ssl

    img_b64 = gerar_grafico_base64(candles, f"{ativo} M{timeframe//60}")
    if not img_b64:
        return None

    dados_txt = ""
    for i, c in enumerate(candles[-5:]):
        d = "▲" if c['close'] >= c['open'] else "▼"
        dados_txt += f"  [{i+1}] O:{c['open']:.5f} H:{c['high']:.5f} L:{c['low']:.5f} C:{c['close']:.5f} {d}\n"

    prompt = f"""Você é um analista sênior de price action para opções binárias de 1-5 minutos.

Ativo: {ativo} | Timeframe: M{timeframe//60}
Últimos 5 candles fechados:
{dados_txt}

Analise SOMENTE estes padrões de alta confiabilidade:
- Engolfo de Alta (Bullish Engulfing) apenas
- Pin Bar / Hammer / Shooting Star
- Three White Soldiers / Three Black Crows
- Morning Star / Evening Star
- Tendência forte (3+ candles consecutivos com máximas/mínimas progressivas)
- Rejeição clara de suporte ou resistência

IMPORTANTE: IGNORE completamente Bearish Engulfing — se aparecer retorne NEUTRO.
{"Se não for Tendência Forte, retorne NEUTRO." if estado["so_tendencia"] else ""}
Se não identificar um desses padrões com clareza, retorne NEUTRO.
Seja rigoroso: só retorne CALL ou PUT se o padrão for inequívoco.
Confiança acima de 80% apenas se o padrão for perfeito.

Responda APENAS com JSON:
{{"sinal": "CALL", "padrao": "nome exato do padrão", "confianca": 85, "motivo": "uma linha"}}

Responda SOMENTE o JSON."""

    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 150,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": CLAUDE_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST"
    )

    # Atualiza custo estimado (~$0.003/chamada Sonnet com imagem)
    estado["api_chamadas"] += 1
    estado["api_gasto"]     = round(estado["api_gasto"] + 0.003, 4)
    if estado["api_credito"] > 0:
        restante = estado["api_credito"] - estado["api_gasto"]
        if restante < 1.0 and not estado["api_alerta"]:
            estado["api_alerta"] = True
            log(f"⚠️ Crédito API baixo: ${restante:.2f}")

    def fazer_req():
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        data = await asyncio.get_event_loop().run_in_executor(None, fazer_req)
        txt  = data['content'][0]['text'].strip()
        txt  = txt.replace('```json','').replace('```','').strip()
        r    = json.loads(txt)
        r['ativo']     = ativo
        r['timeframe'] = timeframe
        return r
    except Exception as e:
        log(f"⚠️ Erro Claude ({ativo}): {e}")
        return None

# ════════════════════════════════════
#  FILTRO LOCAL (sem custo de API)
# ════════════════════════════════════
def filtro_local(candles):
    if len(candles) < 5:
        return False, ""

    dirs = ['a' if c['close'] >= c['open'] else 'b' for c in candles[-5:]]
    ca = cb = 0
    for d in reversed(dirs):
        if d == 'a': ca += 1
        else: break
    for d in reversed(dirs):
        if d == 'b': cb += 1
        else: break
    if ca >= 3: return True, "tendencia_alta"
    if cb >= 3: return True, "tendencia_baixa"

    c1, c2 = candles[-2], candles[-1]
    if (c1['close'] < c1['open'] and c2['close'] > c2['open'] and
        c2['open'] <= c1['close'] and c2['close'] >= c1['open'] and
        abs(c2['close']-c2['open']) > abs(c1['close']-c1['open'])):
        return True, "engolfo_alta"

    u   = candles[-1]
    rng = u['high'] - u['low']
    if rng == 0: return False, ""
    corpo = abs(u['close'] - u['open'])
    s_inf = min(u['open'],u['close']) - u['low']
    s_sup = u['high'] - max(u['open'],u['close'])
    if s_inf >= 2*corpo and corpo/rng < 0.35 and s_inf > s_sup*1.5:
        return True, "pin_bar_alta"
    if s_sup >= 2*corpo and corpo/rng < 0.35 and s_sup > s_inf*1.5:
        return True, "pin_bar_baixa"

    media = sum(c['high']-c['low'] for c in candles[-5:]) / 5
    if media < 0.0003: return False, "baixa_volatilidade"

    return False, ""

# ════════════════════════════════════
#  FILTRO EMA 3 / EMA 10 / SMA 21
# ════════════════════════════════════
def _ema(prices, period):
    k = 2.0 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e

def filtro_ema(candles):
    """
    Confirma tendência usando EMA3, EMA10, SMA21.
    Sinal forte: EMA3 diverge de EMA10 e ambas confirmam SMA21.
    Retorna (passou, direcao_sugerida, descricao)
    """
    if len(candles) < 21:
        return False, "", "candles insuficientes"

    prices = [c['close'] for c in candles]

    ema3  = _ema(prices[-10:],  3)
    ema10 = _ema(prices[-21:], 10)
    sma21 = sum(prices[-21:]) / 21

    estado["ema3"]  = round(ema3,  5)
    estado["ema10"] = round(ema10, 5)
    estado["sma21"] = round(sma21, 5)

    dist_pct = abs(ema3 - ema10) / ema10 if ema10 > 0 else 0

    # Sem distância suficiente = mercado lateral, não entrar
    if dist_pct < 0.0003:
        return False, "", "lateralizacao_ema"

    if ema3 > ema10:
        # Alta: EMA3 acima de EMA10, EMA10 acima de SMA21
        if ema10 >= sma21 * 0.9998:
            return True, "CALL", f"EMA3>EMA10>SMA21 (+{dist_pct*100:.3f}%)"
        return False, "", "EMA alta mas contra SMA21"
    else:
        # Baixa: EMA3 abaixo de EMA10, EMA10 abaixo de SMA21
        if ema10 <= sma21 * 1.0002:
            return True, "PUT", f"EMA3<EMA10<SMA21 (-{dist_pct*100:.3f}%)"
        return False, "", "EMA baixa mas contra SMA21"

# ════════════════════════════════════
#  VARREDURA
# ════════════════════════════════════
async def varrer_ativos(iq):
    import re
    estado["varrendo"]      = True
    estado["varredura_log"] = []
    estado["status"]        = "Buscando ativos..."
    await broadcast()

    log("🔍 Iniciando varredura...")
    melhores = []

    modo = estado.get("modo_ativos", "auto")

    try:
        todos = await asyncio.get_event_loop().run_in_executor(None, iq.get_all_open_time)
        disponiveis = []
        for tipo in ["binary", "turbo", "digital"]:
            for nome, info in todos.get(tipo, {}).items():
                if info.get("open") and nome not in disponiveis:
                    disponiveis.append(nome)
        reais = [a for a in disponiveis if re.match(r'^[A-Z]{6}$', a)]
        otcs  = [a for a in disponiveis if re.match(r'^[A-Z]{6}-OTC$', a)]

        if modo == "forex":
            lista = reais
            if not lista:
                log("⏸ Modo FOREX: nenhum ativo real aberto — aguardando mercado")
                estado["varrendo"] = False
                estado["status"]   = "Aguardando mercado Forex..."
                await broadcast()
                return None
        elif modo == "otc":
            lista = otcs if otcs else ["EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC"]
        else:  # auto
            lista = (reais + otcs) if reais else otcs
            if not lista:
                lista = ["EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC"]

        log(f"📋 Modo {modo.upper()} | {len(lista)} ativos ({len(reais)} reais + {len(otcs)} OTC)")
    except Exception as e:
        log(f"⚠️ Erro ativos: {e}")
        lista = ["EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC"]

    for ativo in lista:
        for tf in TIMEFRAMES:
            try:
                estado["status"] = f"Analisando {ativo} M{tf//60}..."
                await broadcast()

                try:
                    candles_raw = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, lambda a=ativo, t=tf: iq.get_candles(a, t, CANDLES_ANALISE, time.time())
                        ), timeout=10
                    )
                except asyncio.TimeoutError:
                    continue

                if not candles_raw or len(candles_raw) < 5:
                    continue

                candles = [{"open":c["open"],"high":c["max"],"low":c["min"],"close":c["close"]} for c in candles_raw]

                passou, motivo = filtro_local(candles[:-1])
                if not passou:
                    linha = f"{ativo} M{tf//60} | FILTRADO | 0% | {motivo or 'sem padrão'}"
                    estado["varredura_log"].append(linha)
                    await broadcast()
                    continue

                # Filtro EMA 3/10/SMA21
                ema_ok, ema_dir, ema_desc = filtro_ema(candles[:-1])
                if not ema_ok:
                    linha = f"{ativo} M{tf//60} | EMA-SKIP | 0% | {ema_desc}"
                    estado["varredura_log"].append(linha)
                    await broadcast()
                    continue

                log(f"🔎 {ativo} M{tf//60} | {motivo} | {ema_desc} → Claude...")
                try:
                    r = await asyncio.wait_for(analisar_ativo(candles[:-1], ativo, tf), timeout=30)
                except asyncio.TimeoutError:
                    continue

                if r:
                    sinal     = r.get('sinal','NEUTRO')
                    confianca = r.get('confianca', 0)
                    padrao    = r.get('padrao','—')
                    linha     = f"{ativo} M{tf//60} | {sinal} | {confianca}% | {padrao}"
                    estado["varredura_log"].append(linha)
                    log(f"📊 {linha}")
                    if sinal != 'NEUTRO' and confianca >= CONFIANCA_MIN:
                        melhores.append({**r, "candles": candles})

                await asyncio.sleep(0.5)
            except Exception as e:
                log(f"⚠️ {ativo}: {e}")
                continue

    estado["varrendo"] = False

    if not melhores:
        log("❌ Sem sinal forte — aguardando 60s")
        return None

    melhores.sort(key=lambda x: x["confianca"], reverse=True)
    escolhido = melhores[0]
    log(f"🏆 Melhor: {escolhido['ativo']} M{escolhido['timeframe']//60} | {escolhido['sinal']} | {escolhido['confianca']}%")
    return escolhido

async def aguardar_fechamento_vela(timeframe):
    agora    = time.time()
    restante = timeframe - (agora % timeframe)
    espera   = restante + 2
    log(f"⏳ Aguardando vela fechar ({int(restante)}s)...")
    estado["status"] = f"Aguardando vela ({int(restante)}s)..."
    await broadcast()
    await asyncio.sleep(espera)

# ════════════════════════════════════
#  LOG + BROADCAST
# ════════════════════════════════════
def log(msg):
    ts  = datetime.now().strftime("%H:%M:%S")
    txt = f"[{ts}] {msg}"
    estado["log"].appendleft(txt)
    print(txt)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast())
    except Exception:
        pass

async def broadcast():
    if not clientes_ws:
        return
    payload = json.dumps({
        # Bot
        "rodando":      estado["rodando"],
        "banca":        round(estado["banca_atual"], 2),
        "lucro_sessao": round(estado["lucro_sessao"], 2),
        "ganhos":       estado["ganhos"],
        "perdas":       estado["perdas"],
        "stake":        round(estado["stake_atual"], 2),
        "payout_atual": estado["payout_atual"],
        # Masaniello
        "ciclo_num":    estado["ciclo_num"],
        "op_atual":     estado["op_atual"],
        "total_ops":    estado["total_ops"],
        "wins_ciclo":   estado["wins_ciclo"],
        "losses_ciclo": estado["losses_ciclo"],
        "min_wins":     estado["min_wins"],
        "cycle_status": estado["cycle_status"],
        "proxima":      round(estado["proxima"], 2),
        "cofre":        round(estado["cofre"], 2),
        "ciclos_ganhos":    estado["ciclos_ganhos"],
        "ciclos_perdidos":  estado["ciclos_perdidos"],
        "ciclo_resultados": estado["ciclo_resultados"],
        "meta_ciclo":   estado["meta_ciclo"],
        "banca_trabalho":estado["banca_trabalho"],
        # Trade
        "ativo_atual":  estado["ativo_atual"],
        "tf_atual":     estado["tf_atual"],
        "varrendo":     estado["varrendo"],
        "varredura_log":estado["varredura_log"][-12:],
        "historico":    estado["historico"][-20:],
        "status":       estado["status"],
        "log":          list(estado["log"])[:40],
        "ultima_op":    estado["ultima_operacao"],
        "analise":      estado["ultima_analise"],
        "crono_entrada":estado["crono_entrada"],
        "crono_sessao": estado["crono_sessao"],
        "trade_ativo":  estado["trade_ativo"],
        # API
        "api_credito":  estado["api_credito"],
        "api_gasto":    estado["api_gasto"],
        "api_chamadas": estado["api_chamadas"],
        "api_alerta":   estado["api_alerta"],
        # Controles
        "inverter_tudo":        estado["inverter_tudo"],
        "inverter_tendencia":   estado["inverter_tendencia"],
        "inverter_three_black": estado["inverter_three_black"],
        "so_tendencia":         estado["so_tendencia"],
        "modo_ativos":          estado["modo_ativos"],
        # EMA
        "ema3":  estado["ema3"],
        "ema10": estado["ema10"],
        "sma21": estado["sma21"],
    })
    mortos = set()
    for ws in clientes_ws:
        try:
            await ws.send(payload)
        except Exception:
            mortos.add(ws)
    clientes_ws.difference_update(mortos)

# ════════════════════════════════════
#  DASHBOARD WS
# ════════════════════════════════════
async def handler_ws(websocket):
    global CONTA_DEMO, CONFIANCA_MIN
    clientes_ws.add(websocket)
    try:
        await broadcast()
        async for msg in websocket:
            data = json.loads(msg)
            cmd  = data.get("cmd")

            if cmd == "start" and not estado["rodando"]:
                asyncio.create_task(loop_bot())

            elif cmd == "stop":
                estado["rodando"] = False
                log("🛑 Bot parado")

            elif cmd == "shutdown":
                estado["rodando"] = False
                estado["trade_ativo"] = False
                estado["status"] = "Parado"
                await broadcast()

            elif cmd == "reiniciar":
                estado["rodando"] = False
                estado["trade_ativo"] = False
                await broadcast()
                await asyncio.sleep(2)
                import os, signal as _sig
                os.kill(os.getpid(), _sig.SIGTERM)

            elif cmd == "reset":
                estado["ganhos"]        = 0
                estado["perdas"]        = 0
                estado["lucro_sessao"]  = 0.0
                estado["historico"]     = []
                estado["crono_sessao"]  = 0
                estado["sessao_inicio"] = time.time()
                log("🔄 Contadores resetados!")

            elif cmd == "set_credito":
                estado["api_credito"] = float(data.get("valor", 0))
                estado["api_gasto"]   = 0.0
                estado["api_alerta"]  = False
                log(f"💳 Crédito API: ${estado['api_credito']:.2f}")

            elif cmd == "set_modo":
                modo = data.get("modo", "auto")
                if modo in ("auto", "forex", "otc"):
                    estado["modo_ativos"] = modo
                    log(f"📡 Modo ativos: {modo.upper()}")

            elif cmd == "inverter":
                estado["inverter_tudo"] = data.get("ativo", False)
                log(f"🔄 Inverter: {'ON' if estado['inverter_tudo'] else 'OFF'}")

            elif cmd == "inverter_tendencia":
                estado["inverter_tendencia"] = data.get("ativo", False)
                log(f"🔄 Inv. Tendência: {'ON' if estado['inverter_tendencia'] else 'OFF'}")

            elif cmd == "inverter_three_black":
                estado["inverter_three_black"] = data.get("ativo", False)
                log(f"🔄 Inv. Three Black: {'ON' if estado['inverter_three_black'] else 'OFF'}")

            elif cmd == "so_tendencia":
                estado["so_tendencia"] = data.get("ativo", False)
                log(f"📈 Só Tendência: {'ON' if estado['so_tendencia'] else 'OFF'}")

            elif cmd == "config":
                estado["banca_trabalho"] = float(data.get("banca",      estado["banca_trabalho"]))
                estado["meta_ciclo"]     = float(data.get("meta",        estado["meta_ciclo"]))
                estado["total_ops"]      = int(data.get("total_ops",     estado["total_ops"]))
                estado["min_wins"]       = int(data.get("min_wins",      estado["min_wins"]))
                CONTA_DEMO               = data.get("demo", CONTA_DEMO)
                CONFIANCA_MIN            = int(data.get("confianca_min", CONFIANCA_MIN))
                estado["proxima"]        = calcular_proxima()
                log(f"⚙️ Config: banca=${estado['banca_trabalho']} meta=${estado['meta_ciclo']} ops={estado['total_ops']} wins={estado['min_wins']}")

            await broadcast()
    except Exception:
        pass
    finally:
        clientes_ws.discard(websocket)

# ════════════════════════════════════
#  LOOP PRINCIPAL
# ════════════════════════════════════
async def loop_bot():
    if estado["rodando"]:
        return

    estado["rodando"]      = True
    estado["sessao_inicio"] = time.time()
    estado["status"]       = "Conectando na IQ Option..."
    await broadcast()

    try:
        from iqoptionapi.stable_api import IQ_Option
        import nest_asyncio
        nest_asyncio.apply()

        log("🔌 Conectando...")
        iq = IQ_Option(IQ_EMAIL, IQ_PASSWORD)
        check, reason = await asyncio.get_event_loop().run_in_executor(None, iq.connect)

        if not check:
            log(f"❌ Falha: {reason}")
            estado["status"]  = f"Erro: {reason}"
            estado["rodando"] = False
            return

        log("✅ Conectado!")
        iq.change_balance("PRACTICE" if CONTA_DEMO else "REAL")

        banca = iq.get_balance()
        estado["banca_atual"]        = banca
        estado["banca_sessao"]       = banca
        estado["banca_inicio_ciclo"] = banca
        estado["ciclo_num"]          = 1
        estado["op_atual"]           = 1
        estado["wins_ciclo"]         = 0
        estado["losses_ciclo"]       = 0
        estado["ciclo_resultados"]   = []
        estado["cycle_status"]       = "ANDAMENTO"
        estado["proxima"]            = calcular_proxima()
        log(f"💰 Banca: ${banca:.2f} | Ciclo 1 | Meta: +${estado['meta_ciclo']:.2f} | Próx: ${estado['proxima']:.2f}")

        ultima_reconexao   = time.time()
        erros_consecutivos = 0

        while estado["rodando"]:

            # Stop de sessão
            estado["lucro_sessao"] = estado["banca_atual"] - estado["banca_sessao"]
            if estado["lucro_sessao"] <= -STOP_SESSAO:
                log(f"🛑 Stop Sessão: {estado['lucro_sessao']:.2f}")
                estado["status"] = "stop_loss"
                break

            # Ciclo encerrado aguardando reinício
            if estado["cycle_status"] in ("META", "QUEBRADO"):
                await asyncio.sleep(2)
                continue

            # Reconexão preventiva (5 min)
            if time.time() - ultima_reconexao > 300:
                try:
                    def _recon():
                        try: iq.connect()
                        except Exception: pass
                        iq.change_balance("PRACTICE" if CONTA_DEMO else "REAL")
                    await asyncio.get_event_loop().run_in_executor(None, _recon)
                    erros_consecutivos = 0
                except Exception as e:
                    log(f"⚠️ Reconexão: {e}")
                ultima_reconexao = time.time()

            # Calcula próxima entrada
            stake = calcular_proxima()
            if stake <= 0:
                log("⚠️ Entrada inválida — aguardando...")
                await asyncio.sleep(5)
                continue
            estado["stake_atual"] = stake
            estado["proxima"]     = stake

            # Varredura de ativos
            try:
                escolhido = await varrer_ativos(iq)
                erros_consecutivos = 0
            except Exception as e:
                erros_consecutivos += 1
                log(f"⚠️ Erro varredura ({erros_consecutivos}): {e}")
                if erros_consecutivos >= 3:
                    ultima_reconexao = 0
                    erros_consecutivos = 0
                await asyncio.sleep(15)
                continue

            if not escolhido:
                estado["status"] = "Sem oportunidade — nova varredura em 60s"
                await broadcast()
                await asyncio.sleep(60)
                continue

            ativo     = escolhido["ativo"]
            timeframe = escolhido["timeframe"]
            sinal     = escolhido["sinal"]
            confianca = escolhido["confianca"]
            padrao    = escolhido["padrao"]

            estado["ativo_atual"]    = ativo
            estado["tf_atual"]       = f"M{timeframe//60}"
            estado["ultima_analise"] = escolhido
            await broadcast()

            await aguardar_fechamento_vela(timeframe)
            if not estado["rodando"]: break

            # Inversão de sinal
            padrao_lower = padrao.lower()
            inverter = estado["inverter_tudo"]
            if not inverter:
                if estado["inverter_tendencia"] and "tend" in padrao_lower:
                    inverter = True
                    log("🔄 Tendência invertida")
                elif estado["inverter_three_black"] and "black" in padrao_lower:
                    inverter = True
                    log("🔄 Three Black invertido")
            if not inverter and any(p in padrao_lower for p in PADROES_INVERTER):
                inverter = True
                log(f"🔄 Padrão {padrao} invertido")
            if inverter:
                sinal = "PUT" if sinal == "CALL" else "CALL"
                log(f"🔄 → {sinal}")

            # Busca payout real
            try:
                def _payout():
                    try:
                        pp = iq.get_all_profit()
                        for t in ("turbo","binary","digital"):
                            v = pp.get(t, {}).get(ativo, {})
                            if isinstance(v, dict):
                                for k, pv in v.items():
                                    if pv: return round(float(pv), 4)
                            elif v:
                                return round(float(v), 4)
                    except Exception:
                        pass
                    return 0.85
                payout = await asyncio.get_event_loop().run_in_executor(None, _payout)
                estado["payout_atual"] = payout
                log(f"💹 Payout {ativo}: {round(payout*100)}%")
            except Exception:
                payout = 0.85

            # Recalcula stake com payout atualizado
            stake = calcular_proxima()
            estado["stake_atual"] = stake
            direcao    = "call" if sinal == "CALL" else "put"
            expiracao  = max(1, timeframe // 60)

            log(f"🎯 {sinal} | {ativo} M{expiracao} | {padrao} | {confianca}% | ${stake:.2f} | op {estado['op_atual']}/{estado['total_ops']}")
            estado["status"]        = f"{sinal} ${stake:.2f} — {ativo}"
            estado["trade_ativo"]   = True
            estado["crono_entrada"] = 0
            await broadcast()

            try:
                check, id_op = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: iq.buy(stake, ativo, direcao, expiracao)
                )

                if check:
                    log(f"🟢 Ordem #{id_op}")
                    estado["ultima_operacao"] = {
                        "id": id_op, "dir": sinal, "stake": stake,
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "padrao": padrao, "ativo": ativo,
                    }
                    estado["status"] = f"{sinal} ${stake:.2f} — aguardando..."
                    await broadcast()

                    await asyncio.sleep(expiracao * 60 + 5)
                    estado["trade_ativo"] = False

                    try:
                        banca_nova = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, iq.get_balance),
                            timeout=15
                        )
                        lucro_op = round(banca_nova - estado["banca_atual"], 2)
                        estado["banca_atual"]  = banca_nova
                        estado["lucro_sessao"] = banca_nova - estado["banca_sessao"]

                        resultado = "WIN" if lucro_op > 0 else "LOSS"
                        estado["ultima_operacao"]["resultado"] = resultado
                        estado["ultima_operacao"]["lucro_op"]  = lucro_op

                        estado["historico"].append({
                            "hora":      datetime.now().strftime("%H:%M"),
                            "ativo":     ativo, "tf": f"M{expiracao}",
                            "dir":       sinal,  "stake": stake,
                            "resultado": resultado, "lucro": lucro_op,
                            "padrao":    padrao,
                            "op":        f"{estado['op_atual']}/{estado['total_ops']}",
                        })

                        if lucro_op > 0:
                            on_win(lucro_op)
                        else:
                            on_loss()

                    except Exception as e:
                        estado["trade_ativo"] = False
                        log(f"⚠️ Erro banca: {e}")
                else:
                    estado["trade_ativo"] = False
                    log("⚠️ Falha ao abrir trade")

            except Exception as e:
                estado["trade_ativo"] = False
                log(f"⚠️ Erro trade: {e}")

            await broadcast()
            await asyncio.sleep(5)

    except Exception as e:
        log(f"💥 Erro crítico: {e}")
        estado["status"] = f"Erro: {e}"
    finally:
        estado["rodando"]     = False
        estado["trade_ativo"] = False
        log("🔴 Bot encerrado")
        await broadcast()

# ════════════════════════════════════
#  MAIN
# ════════════════════════════════════
async def main():
    import websockets
    log("🚀 IQBOT Masaniello + Claude Vision")
    log(f"📡 Dashboard → ws://localhost:{DASHBOARD_PORT}")
    asyncio.create_task(loop_cronometro())
    async with websockets.serve(handler_ws, "0.0.0.0", DASHBOARD_PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
