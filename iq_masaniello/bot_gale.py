"""
IQBOT — Gale + Claude Vision Analítico
Analisa fluxo de velas (EMA3/10/21 + Fractal) e entra no instante zero.
"""

import asyncio, json, time, base64, io, ssl, urllib.request
from datetime import datetime
from collections import deque

# ════════════════════════════════════
#  CREDENCIAIS
# ════════════════════════════════════
IQ_EMAIL    = "SEU_EMAIL@exemplo.com"
IQ_PASSWORD = "SUA_SENHA"
CLAUDE_KEY  = "sk-ant-api03-SEU_CLAUDE_API_KEY"

# ════════════════════════════════════
#  CONFIG
# ════════════════════════════════════
ATIVO_FOCO      = "EURUSD-OTC"
TIMEFRAME       = 60            # M1 em segundos
GALE_INICIAL    = 2.0           # stake inicial R$
GALE_FATOR      = 2.0
GALE_MAX        = 6             # 7 níveis (0..6)
MAX_LOSS_SEQ    = 3             # pausa após N losses seguidos
CONFIANCA_MIN   = 72
CANDLES_ANALISE = 35            # precisa de 21+ para SMA21
CONTA_DEMO      = True
DASHBOARD_PORT  = 8765
STOP_SESSAO     = 200.0
ANALISE_ANTEC   = 12            # segundos antes do fechamento para analisar

# Stakes: [2, 4, 8, 16, 32, 64, 128]
GALE_STAKES = [round(GALE_INICIAL * (GALE_FATOR ** i), 2) for i in range(GALE_MAX + 1)]

# ════════════════════════════════════
#  ESTADO
# ════════════════════════════════════
estado = {
    # Bot
    "rodando":         False,
    "banca_atual":     0.0,
    "banca_sessao":    0.0,
    "lucro_sessao":    0.0,
    "ganhos":          0,
    "perdas":          0,
    "payout_atual":    0.85,

    # Gale
    "gale_nivel":      0,
    "gale_stake":      GALE_INICIAL,
    "gale_inicial":    GALE_INICIAL,
    "gale_fator":      GALE_FATOR,
    "gale_max":        GALE_MAX,
    "loss_seq":        0,
    "gale_pausado":    False,
    "gale_wins":       0,
    "gale_ciclos":     0,
    "gale_stakes_list":GALE_STAKES,

    # Trade
    "ativo_foco":      ATIVO_FOCO,
    "timeframe":       TIMEFRAME,
    "ativo_atual":     ATIVO_FOCO,
    "tf_atual":        f"M{TIMEFRAME//60}",
    "trade_ativo":     False,
    "crono_entrada":   0,
    "crono_sessao":    0,
    "sessao_inicio":   0,
    "status":          "Aguardando...",
    "prox_vela":       0,

    # Indicadores
    "ema3":            0.0,
    "ema10":           0.0,
    "ema21":           0.0,
    "fractal_up_dist":  None,
    "fractal_down_dist":None,
    "direcao_ema":     "—",

    # Análise
    "ultima_analise":  None,
    "ultima_operacao": None,
    "historico":       [],
    "log":             deque(maxlen=120),
    "varredura_log":   [],

    # API
    "api_credito":     0.0,
    "api_gasto":       0.0,
    "api_chamadas":    0,
    "api_alerta":      False,

    # Config (ajustável pelo dashboard)
    "confianca_min":   CONFIANCA_MIN,
    "max_loss_seq":    MAX_LOSS_SEQ,
    "conta_demo":      CONTA_DEMO,

    # Controles
    "inverter_tudo":   False,
    "modo_pausa":      False,
}

clientes_ws = set()


# ════════════════════════════════════
#  INDICADORES TÉCNICOS
# ════════════════════════════════════
def _ema(prices, period):
    if not prices: return 0.0
    k = 2.0 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e

def calcular_indicadores(candles):
    if len(candles) < 21:
        return
    prices = [c['close'] for c in candles]
    ema3  = _ema(prices[-12:],  3)
    ema10 = _ema(prices[-25:], 10)
    ema21 = sum(prices[-21:]) / 21
    estado["ema3"]  = round(ema3,  5)
    estado["ema10"] = round(ema10, 5)
    estado["ema21"] = round(ema21, 5)
    if ema3 > ema10:
        estado["direcao_ema"] = "ALTA"
    elif ema3 < ema10:
        estado["direcao_ema"] = "BAIXA"
    else:
        estado["direcao_ema"] = "LATERAL"
    return ema3, ema10, ema21

def detectar_fractais(candles):
    """Williams Fractal (5 candles): pico/vale com 2 vizinhos menores de cada lado."""
    ups, downs = [], []
    for i in range(2, len(candles) - 2):
        c = candles[i]
        if all(c['high'] > candles[j]['high'] for j in [i-2,i-1,i+1,i+2]):
            ups.append(i)
        if all(c['low'] < candles[j]['low'] for j in [i-2,i-1,i+1,i+2]):
            downs.append(i)
    total = len(candles) - 1
    estado["fractal_up_dist"]   = total - ups[-1]   if ups   else None
    estado["fractal_down_dist"] = total - downs[-1] if downs else None
    return ups, downs


# ════════════════════════════════════
#  GRÁFICO BASE64
# ════════════════════════════════════
def gerar_grafico(candles, titulo=""):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mp
        import numpy as np

        prices = [c['close'] for c in candles]
        ema3_line  = []
        ema10_line = []
        ema21_line = []
        e3 = prices[0]; e10 = prices[0]
        k3 = 2/4; k10 = 2/11
        for p in prices:
            e3  = p*k3  + e3*(1-k3)
            e10 = p*k10 + e10*(1-k10)
            ema3_line.append(e3)
            ema10_line.append(e10)
        for i in range(len(prices)):
            if i < 20:
                ema21_line.append(sum(prices[:i+1])/(i+1))
            else:
                ema21_line.append(sum(prices[i-20:i+1])/21)

        _, fractais_up, fractais_down = [], [], []
        try:
            for i in range(2, len(candles)-2):
                if all(candles[i]['high'] > candles[j]['high'] for j in [i-2,i-1,i+1,i+2]):
                    fractais_up.append(i)
                if all(candles[i]['low'] < candles[j]['low'] for j in [i-2,i-1,i+1,i+2]):
                    fractais_down.append(i)
        except Exception:
            pass

        fig, ax = plt.subplots(figsize=(11, 5))
        fig.patch.set_facecolor('#0b0e1a')
        ax.set_facecolor('#0b0e1a')

        for i, c in enumerate(candles):
            o, h, l, cl = c['open'], c['high'], c['low'], c['close']
            cor = '#00e5a0' if cl >= o else '#ff3e6c'
            ax.plot([i,i],[l,h], color=cor, lw=1.0)
            ax.add_patch(mp.FancyBboxPatch(
                (i-.35, min(o,cl)), .7, max(abs(cl-o), 1e-8),
                boxstyle="square,pad=0", fc=cor, ec=cor
            ))

        xs = list(range(len(candles)))
        ax.plot(xs, ema3_line,  color='#f7c948', lw=1.2, label='EMA3')
        ax.plot(xs, ema10_line, color='#ff3e6c', lw=1.2, label='EMA10')
        ax.plot(xs, ema21_line, color='#4f8ef7', lw=1.2, label='SMA21')

        for fi in fractais_up:
            ax.scatter(fi, candles[fi]['high']*1.0002, marker='^', color='#00e5a0', s=40, zorder=5)
        for fi in fractais_down:
            ax.scatter(fi, candles[fi]['low']*0.9998, marker='v', color='#ff3e6c', s=40, zorder=5)

        ax.legend(fontsize=8, facecolor='#111827', labelcolor='#dde4f8', loc='upper left')
        ax.set_title(titulo, color='#dde4f8', fontsize=10)
        ax.set_xlim(-1, len(candles))
        ax.tick_params(colors='#6b7aa0', labelsize=7)
        for s in ['top','right']: ax.spines[s].set_visible(False)
        for s in ['bottom','left']: ax.spines[s].set_color('#1e2a42')
        ax.yaxis.grid(True, color='#1e2a42', lw=.5)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor='#0b0e1a', dpi=90)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        log(f"Gráfico: {e}")
        return None


# ════════════════════════════════════
#  CLAUDE — ANÁLISE DE FLUXO
# ════════════════════════════════════
async def analisar_vela(candles, ativo, tf_seg):
    inds = calcular_indicadores(candles)
    if not inds:
        return None
    ema3, ema10, ema21 = inds
    detectar_fractais(candles[:-2])  # exclui vela atual em formação

    preco     = candles[-2]['close']  # última vela fechada
    pos_ema21 = "ACIMA" if preco > ema21 else "ABAIXO"
    cruzamento= "EMA3 > EMA10 → ALTA" if ema3 > ema10 else "EMA3 < EMA10 → BAIXA"
    dist_pct  = round(abs(ema3 - ema10) / ema10 * 100, 4) if ema10 > 0 else 0

    # Últimas 6 velas fechadas
    ultimas = candles[-7:-1]
    candles_txt = ""
    for i, c in enumerate(ultimas):
        d = "▲" if c['close'] >= c['open'] else "▼"
        body = abs(c['close'] - c['open'])
        rng  = max(c['high'] - c['low'], 1e-10)
        cp   = round(body / rng * 100)
        candles_txt += f"  [{i+1}] {d} O:{c['open']:.5f} H:{c['high']:.5f} L:{c['low']:.5f} C:{c['close']:.5f} | corpo {cp}%\n"

    # Contexto fractal
    frac_txt = ""
    if estado["fractal_up_dist"] is not None:
        frac_txt += f"Fractal ALTA: {estado['fractal_up_dist']} velas atrás\n"
    if estado["fractal_down_dist"] is not None:
        frac_txt += f"Fractal BAIXA: {estado['fractal_down_dist']} velas atrás\n"

    nivel    = estado["gale_nivel"]
    loss_seq = estado["loss_seq"]

    prompt = f"""Você é um analista de price action especialista em opções binárias de {tf_seg//60} minuto(s).
Sua análise determina se devemos CALL, PUT ou SKIP na próxima vela.

ATIVO: {ativo} | M{tf_seg//60}

INDICADORES:
- EMA3:  {ema3:.5f}
- EMA10: {ema10:.5f}
- SMA21: {ema21:.5f}
- Preço: {preco:.5f} → {pos_ema21} da SMA21
- {cruzamento} | Distância EMA3/EMA10: {dist_pct:.4f}%
{frac_txt}
ÚLTIMAS 6 VELAS FECHADAS (1=mais antiga, 6=mais recente):
{candles_txt}
CONTEXTO: Gale nível {nivel}/6 | {loss_seq} losses consecutivos

REGRAS:
1. Preço ACIMA da SMA21 → analise apenas CALL. ABAIXO → apenas PUT.
2. EMA3 distanciando de EMA10 (>0.03%) = tendência confirmada = maior confiança.
3. Se o fluxo de velas sugere direção OPOSTA às médias → retorne SKIP.
4. Com nível Gale >= 4 ou >= 2 losses consecutivos → seja mais rigoroso, exija sinal claro.
5. Fractal recente (<5 velas) na direção da entrada = confirmação extra.
6. Fluxo muito limpo e consistente (3+ velas na mesma direção + EMA alinhada) → forca "FORTE".
7. Se incerto → SKIP. Não force entrada. Preservar o ciclo Gale é prioridade.

Responda SOMENTE com JSON:
{{"sinal": "CALL", "confianca": 82, "padrao": "tendência EMA3>EMA10>SMA21", "motivo": "3 velas alta + EMA alinhada + fractal", "forca": "NORMAL"}}

sinal: CALL | PUT | SKIP
forca: NORMAL | FORTE"""

    img = gerar_grafico(candles[:-1], f"{ativo} M{tf_seg//60}")
    msgs_content = []
    if img:
        msgs_content.append({"type":"image","source":{"type":"base64","media_type":"image/png","data":img}})
    msgs_content.append({"type":"text","text":prompt})

    payload = json.dumps({
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": 200,
        "messages":   [{"role":"user","content":msgs_content}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":          CLAUDE_KEY,
            "anthropic-version":  "2023-06-01",
            "content-type":       "application/json",
        },
        method="POST"
    )

    estado["api_chamadas"] += 1
    estado["api_gasto"]     = round(estado["api_gasto"] + 0.003, 4)
    if estado["api_credito"] > 0 and not estado["api_alerta"]:
        if estado["api_credito"] - estado["api_gasto"] < 1.0:
            estado["api_alerta"] = True
            log("⚠️ Crédito API baixo!")

    def _req():
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode())

    try:
        data = await asyncio.get_event_loop().run_in_executor(None, _req)
        txt  = data['content'][0]['text'].strip()
        txt  = txt.replace('```json','').replace('```','').strip()
        r    = json.loads(txt)
        r['ativo']     = ativo
        r['timeframe'] = tf_seg
        estado["ultima_analise"] = r
        return r
    except Exception as e:
        log(f"⚠️ Claude ({ativo}): {e}")
        return None


# ════════════════════════════════════
#  GALE
# ════════════════════════════════════
def gale_on_win():
    estado["ganhos"]    += 1
    estado["gale_wins"] += 1
    estado["loss_seq"]   = 0
    estado["gale_nivel"] = 0
    estado["gale_stake"] = estado["gale_stakes_list"][0]
    estado["gale_ciclos"] += 1
    estado["gale_pausado"] = False
    log(f"✅ WIN → Gale resetado | Banca: R${estado['banca_atual']:.2f}")

def gale_on_loss():
    estado["perdas"]   += 1
    estado["loss_seq"] += 1
    nivel_ant = estado["gale_nivel"]
    if estado["gale_nivel"] < estado["gale_max"]:
        estado["gale_nivel"] += 1
    estado["gale_stake"] = estado["gale_stakes_list"][estado["gale_nivel"]]
    estado["gale_ciclos"] += 1

    if estado["loss_seq"] >= estado["max_loss_seq"]:
        estado["gale_pausado"] = True
        log(f"⏸ {estado['loss_seq']} losses seguidos → PAUSADO. Aguardando setup limpo...")
    else:
        log(f"❌ LOSS → Gale {nivel_ant}→{estado['gale_nivel']} | Próx: R${estado['gale_stake']:.2f}")


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
        # Atualiza countdown para próxima vela
        agora = time.time()
        tf = estado["timeframe"]
        estado["prox_vela"] = int(tf - (agora % tf))
        await broadcast()


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
        "rodando":       estado["rodando"],
        "banca":         round(estado["banca_atual"], 2),
        "lucro_sessao":  round(estado["lucro_sessao"], 2),
        "ganhos":        estado["ganhos"],
        "perdas":        estado["perdas"],
        "payout_atual":  estado["payout_atual"],
        # Gale
        "gale_nivel":    estado["gale_nivel"],
        "gale_stake":    round(estado["gale_stake"], 2),
        "gale_max":      estado["gale_max"],
        "gale_inicial":  estado["gale_inicial"],
        "loss_seq":      estado["loss_seq"],
        "gale_pausado":  estado["gale_pausado"],
        "gale_wins":     estado["gale_wins"],
        "gale_ciclos":   estado["gale_ciclos"],
        "gale_stakes_list": estado["gale_stakes_list"],
        "max_loss_seq":  estado["max_loss_seq"],
        # Trade
        "ativo_foco":    estado["ativo_foco"],
        "ativo_atual":   estado["ativo_atual"],
        "tf_atual":      estado["tf_atual"],
        "trade_ativo":   estado["trade_ativo"],
        "crono_entrada": estado["crono_entrada"],
        "crono_sessao":  estado["crono_sessao"],
        "prox_vela":     estado["prox_vela"],
        "status":        estado["status"],
        # Indicadores
        "ema3":          estado["ema3"],
        "ema10":         estado["ema10"],
        "ema21":         estado["ema21"],
        "direcao_ema":   estado["direcao_ema"],
        "fractal_up_dist":   estado["fractal_up_dist"],
        "fractal_down_dist": estado["fractal_down_dist"],
        # Análise
        "analise":       estado["ultima_analise"],
        "ultima_op":     estado["ultima_operacao"],
        "historico":     estado["historico"][-20:],
        "log":           list(estado["log"])[:50],
        # API
        "api_credito":   estado["api_credito"],
        "api_gasto":     estado["api_gasto"],
        "api_chamadas":  estado["api_chamadas"],
        "api_alerta":    estado["api_alerta"],
        # Config
        "confianca_min": estado["confianca_min"],
        "max_loss_seq":  estado["max_loss_seq"],
        "conta_demo":    estado["conta_demo"],
        # Controles
        "inverter_tudo": estado["inverter_tudo"],
        "modo_pausa":    estado["modo_pausa"],
    })
    mortos = set()
    for ws in clientes_ws:
        try:
            await ws.send(payload)
        except Exception:
            mortos.add(ws)
    clientes_ws.difference_update(mortos)


# ════════════════════════════════════
#  BUSCAR CANDLES
# ════════════════════════════════════
async def buscar_candles(iq, ativo, tf):
    try:
        raw = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: iq.get_candles(ativo, tf, CANDLES_ANALISE, time.time())
            ),
            timeout=12
        )
        if not raw or len(raw) < 10:
            return None
        return [{"open":c["open"],"high":c["max"],"low":c["min"],"close":c["close"]} for c in raw]
    except Exception as e:
        log(f"⚠️ Candles ({ativo}): {e}")
        return None


# ════════════════════════════════════
#  LOOP PRINCIPAL
# ════════════════════════════════════
async def loop_bot():
    if estado["rodando"]:
        return

    estado["rodando"]       = True
    estado["sessao_inicio"] = time.time()
    estado["status"]        = "Conectando na IQ Option..."
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
        modo = "PRACTICE" if estado["conta_demo"] else "REAL"
        iq.change_balance(modo)
        log(f"💼 Conta {modo}")

        banca = iq.get_balance()
        estado["banca_atual"]   = banca
        estado["banca_sessao"]  = banca
        estado["gale_nivel"]    = 0
        estado["gale_stake"]    = estado["gale_stakes_list"][0]
        estado["loss_seq"]      = 0
        estado["gale_pausado"]  = False
        log(f"💰 Banca: R${banca:.2f} | Stake inicial: R${estado['gale_stakes_list'][0]:.2f}")
        log(f"📋 Stakes Gale: {estado['gale_stakes_list']}")

        ativo = estado["ativo_foco"]
        tf    = estado["timeframe"]
        estado["ativo_atual"] = ativo
        estado["tf_atual"]    = f"M{tf//60}"

        # Atualiza payout
        try:
            def _pay():
                pp = iq.get_all_profit()
                for t in ("turbo","binary","digital"):
                    v = pp.get(t, {}).get(ativo, {})
                    if isinstance(v, dict):
                        for k, pv in v.items():
                            if pv: return round(float(pv), 4)
                    elif v:
                        return round(float(v), 4)
                return 0.85
            estado["payout_atual"] = await asyncio.get_event_loop().run_in_executor(None, _pay)
            log(f"💹 Payout: {round(estado['payout_atual']*100)}%")
        except Exception:
            pass

        await broadcast()

        tarefa_analise = None  # análise paralela durante trade

        while estado["rodando"]:
            # Stop de sessão
            estado["lucro_sessao"] = estado["banca_atual"] - estado["banca_sessao"]
            if estado["lucro_sessao"] <= -STOP_SESSAO:
                log(f"🛑 Stop Sessão: R${estado['lucro_sessao']:.2f}")
                estado["status"] = "Stop Loss Sessão"
                break

            if estado["modo_pausa"]:
                estado["status"] = "⏸ Pausado manualmente"
                await asyncio.sleep(3)
                await broadcast()
                continue

            # ── ESPERA MOMENTO DE ANÁLISE (10-12s antes do fechamento) ──
            agora   = time.time()
            pos_vel = agora % tf
            restante= tf - pos_vel

            if restante > ANALISE_ANTEC:
                espera = restante - ANALISE_ANTEC
                estado["status"] = f"⏳ Próxima análise em {int(espera)}s"
                await broadcast()
                await asyncio.sleep(espera)

            if not estado["rodando"]:
                break

            # ── ANÁLISE ──
            estado["status"] = f"🔍 Analisando {ativo} M{tf//60}..."
            await broadcast()

            candles = await buscar_candles(iq, ativo, tf)
            if not candles:
                await asyncio.sleep(5)
                continue

            resultado = await analisar_vela(candles, ativo, tf)
            await broadcast()

            # ── AGUARDA INSTANTE ZERO (abertura da nova vela) ──
            agora2   = time.time()
            restante2= tf - (agora2 % tf)

            # Se ainda tem mais de 2s, espera o fechamento
            if restante2 > 2:
                estado["status"] = f"⏱ Entrada em {int(restante2)}s..."
                await broadcast()
                await asyncio.sleep(restante2 - 0.3)  # 0.3s de buffer para chegar antes

            if not estado["rodando"]:
                break

            # ── DECISÃO DE ENTRADA ──
            # Não entrar se pausado por losses ou sem resultado
            if estado["gale_pausado"]:
                # Verifica se o sinal atual é bom o suficiente para retomar
                if resultado and resultado.get('sinal') != 'SKIP' and resultado.get('confianca', 0) >= 80:
                    estado["gale_pausado"] = False
                    estado["loss_seq"]     = 0
                    log(f"▶️ Retomando! Sinal: {resultado['sinal']} {resultado.get('confianca')}% — {resultado.get('padrao','')}")
                else:
                    estado["status"] = f"⏸ Pausado ({estado['loss_seq']} losses) — aguardando setup..."
                    await broadcast()
                    continue

            if not resultado or resultado.get('sinal') == 'SKIP':
                sinal_txt = "SKIP" if resultado else "sem resposta"
                conf_txt  = resultado.get('confianca', 0) if resultado else 0
                log(f"⏭ {sinal_txt} ({conf_txt}%) — aguardando próxima vela")
                estado["status"] = "Aguardando sinal..."
                await broadcast()
                continue

            sinal     = resultado.get('sinal', 'SKIP')
            confianca = resultado.get('confianca', 0)
            padrao    = resultado.get('padrao', '—')
            forca     = resultado.get('forca', 'NORMAL')

            if confianca < estado["confianca_min"]:
                log(f"⏭ Confiança baixa: {confianca}% < {estado['confianca_min']}% ({padrao})")
                continue

            # Stake (com boost em FORTE e nível 0)
            stake = estado["gale_stake"]
            if forca == "FORTE" and estado["gale_nivel"] == 0:
                stake = round(stake * 1.5, 2)
                log(f"💪 Sinal FORTE — stake boosted: R${stake:.2f}")

            # Inversão de sinal
            if estado["inverter_tudo"]:
                sinal = "PUT" if sinal == "CALL" else "CALL"
                log(f"🔄 Invertido → {sinal}")

            direcao   = "call" if sinal == "CALL" else "put"
            expiracao = max(1, tf // 60)

            log(f"🎯 {sinal} | {ativo} M{expiracao} | {padrao} | {confianca}% | R${stake:.2f} | Gale N{estado['gale_nivel']}")
            estado["status"]        = f"{sinal} R${stake:.2f} — {ativo} M{expiracao}"
            estado["trade_ativo"]   = True
            estado["crono_entrada"] = 0
            await broadcast()

            try:
                check_t, id_op = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: iq.buy(stake, ativo, direcao, expiracao)
                )

                if check_t:
                    log(f"🟢 Ordem #{id_op} aberta")
                    estado["ultima_operacao"] = {
                        "id": id_op, "dir": sinal, "stake": stake,
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "padrao": padrao, "ativo": ativo,
                        "gale_nivel": estado["gale_nivel"],
                    }
                    estado["status"] = f"{sinal} R${stake:.2f} — aguardando..."
                    await broadcast()

                    # Aguarda resultado
                    await asyncio.sleep(expiracao * 60 + 5)
                    estado["trade_ativo"]   = False
                    estado["crono_entrada"] = 0

                    try:
                        banca_nova = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, iq.get_balance),
                            timeout=15
                        )
                        lucro_op = round(banca_nova - estado["banca_atual"], 2)
                        estado["banca_atual"]  = banca_nova
                        estado["lucro_sessao"] = banca_nova - estado["banca_sessao"]

                        resultado_str = "WIN" if lucro_op > 0 else "LOSS"
                        estado["ultima_operacao"]["resultado"] = resultado_str
                        estado["ultima_operacao"]["lucro_op"]  = lucro_op

                        estado["historico"].append({
                            "hora":      datetime.now().strftime("%H:%M"),
                            "ativo":     ativo,
                            "tf":        f"M{expiracao}",
                            "dir":       sinal,
                            "stake":     stake,
                            "resultado": resultado_str,
                            "lucro":     lucro_op,
                            "padrao":    padrao,
                            "gale_n":    estado["gale_nivel"],
                            "confianca": confianca,
                        })

                        if lucro_op > 0:
                            gale_on_win()
                        else:
                            gale_on_loss()

                    except Exception as e:
                        estado["trade_ativo"] = False
                        log(f"⚠️ Erro banca: {e}")
                else:
                    estado["trade_ativo"] = False
                    log("⚠️ Falha ao abrir ordem")

            except Exception as e:
                estado["trade_ativo"] = False
                log(f"⚠️ Erro trade: {e}")

            await broadcast()

    except Exception as e:
        log(f"💥 Erro crítico: {e}")
        import traceback
        log(traceback.format_exc()[:300])
        estado["status"] = f"Erro: {e}"
    finally:
        estado["rodando"]     = False
        estado["trade_ativo"] = False
        log("🔴 Bot encerrado")
        await broadcast()


# ════════════════════════════════════
#  WEBSOCKET HANDLER
# ════════════════════════════════════
async def handler_ws(websocket):
    global CONTA_DEMO
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

            elif cmd == "reiniciar":
                estado["rodando"] = False
                estado["trade_ativo"] = False
                await broadcast()
                await asyncio.sleep(2)
                import os, signal as _s
                os.kill(os.getpid(), _s.SIGTERM)

            elif cmd == "reset":
                estado["ganhos"]      = 0
                estado["perdas"]      = 0
                estado["lucro_sessao"]= 0.0
                estado["historico"]   = []
                estado["gale_nivel"]  = 0
                estado["gale_stake"]  = estado["gale_stakes_list"][0]
                estado["loss_seq"]    = 0
                estado["gale_wins"]   = 0
                estado["gale_ciclos"] = 0
                estado["gale_pausado"]= False
                estado["crono_sessao"]= 0
                estado["sessao_inicio"]=time.time()
                log("🔄 Resetado!")

            elif cmd == "retomar":
                estado["gale_pausado"] = False
                estado["loss_seq"]     = 0
                log("▶️ Retomado manualmente!")

            elif cmd == "set_pausa":
                estado["modo_pausa"] = data.get("ativo", False)
                log(f"{'⏸ Pausa' if estado['modo_pausa'] else '▶️ Retomado'} manual")

            elif cmd == "set_credito":
                estado["api_credito"] = float(data.get("valor", 0))
                estado["api_gasto"]   = 0.0
                estado["api_alerta"]  = False
                log(f"💳 Crédito: ${estado['api_credito']:.2f}")

            elif cmd == "inverter":
                estado["inverter_tudo"] = data.get("ativo", False)
                log(f"🔄 Inverter: {'ON' if estado['inverter_tudo'] else 'OFF'}")

            elif cmd == "config":
                estado["ativo_foco"]    = data.get("ativo",    estado["ativo_foco"])
                estado["timeframe"]     = int(data.get("tf",   estado["timeframe"]))
                estado["confianca_min"] = int(data.get("conf", estado["confianca_min"]))
                estado["max_loss_seq"]  = int(data.get("max_loss", estado["max_loss_seq"]))
                estado["conta_demo"]    = data.get("demo", estado["conta_demo"])
                estado["ativo_atual"]   = estado["ativo_foco"]
                estado["tf_atual"]      = f"M{estado['timeframe']//60}"
                # Recalcula stakes se gale_inicial foi enviado
                gi = float(data.get("gale_inicial", estado["gale_inicial"]))
                gi = max(0.5, round(gi, 2))
                estado["gale_inicial"]   = gi
                fator = estado["gale_fator"]
                gmax  = estado["gale_max"]
                estado["gale_stakes_list"] = [round(gi * (fator ** i), 2) for i in range(gmax + 1)]
                estado["gale_stake"]     = estado["gale_stakes_list"][estado["gale_nivel"]]
                log(f"⚙️ Config: {estado['ativo_foco']} M{estado['timeframe']//60} | conf≥{estado['confianca_min']}% | pausa>{estado['max_loss_seq']} losses | stake_ini=R${gi:.2f}")
                log(f"📋 Stakes Gale: {estado['gale_stakes_list']}")

            await broadcast()
    except Exception:
        pass
    finally:
        clientes_ws.discard(websocket)


# ════════════════════════════════════
#  MAIN
# ════════════════════════════════════
async def main():
    import websockets
    log("🚀 IQBOT — Gale + Claude Vision Analítico")
    log(f"📋 Stakes: {estado['gale_stakes_list']}")
    log(f"📡 Dashboard → ws://localhost:{DASHBOARD_PORT}")
    asyncio.create_task(loop_cronometro())
    async with websockets.serve(handler_ws, "0.0.0.0", DASHBOARD_PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
