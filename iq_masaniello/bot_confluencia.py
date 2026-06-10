"""
bot_confluencia.py
==================
Bot Masaniello + Preservação de Lucro + Motor de Confluência.

Combina:
  - Masaniello para gestão de banca
  - Preservação de lucro (cofre separado)
  - Signal Engine com 10 indicadores + confluência
  - Análise M1 + M5 (multi-timeframe)
  - Filtro anti-doji e anti-lateralização

Dependências:
    pip install iqoptionapi pandas pandas_ta numpy

Uso:
    python bot_confluencia.py
"""

import time
import json
import logging
import signal as _signal
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

from iqoptionapi.stable_api import IQ_Option
from masaniello_core import MasanielloManager, StatusCiclo
from signal_engine import SignalEngine, SignalResult

CONFIG_FILE = Path("/opt/masaniello/iq_masaniello/masaniello_config.json")

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_confluencia.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

_CONFIG_BASE = Path("/opt/masaniello/iq_masaniello")

_DEFAULTS = {
    # -- Credenciais
    "email":        "SEU_EMAIL@iqoption.com",
    "password":     "SUA_SENHA",
    "account_type": "PRACTICE",

    # -- Ativos reais (mercado aberto, seg-sex) — prioridade
    "assets_reais": [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
        "NZDUSD", "USDCHF", "EURGBP", "EURJPY", "GBPJPY",
    ],

    # -- OTC fallback (24/7, fins de semana)
    "assets_otc": [
        "EURUSD-OTC", "GBPUSD-OTC", "AUDUSD-OTC",
        "NZDUSD-OTC", "USDCAD-OTC",
    ],

    # -- Duração das opções
    "duration": 1,

    # -- Masaniello
    "banca_trabalho": 1000.0,
    "meta_ciclo":       80.0,
    "total_ops":        10,
    "min_wins":          5,
    "payout":           0.85,

    # -- Confluência
    "min_score":    5,
    "sr_tolerance": 0.0005,
    "usar_m5":      True,
    "filtrar_doji": True,

    # -- Candles
    "candles_m1_qtd": 100,
    "candles_m5_qtd":  50,

    # -- Anti-lateral (ADX)
    "adx_minimo": 20,

    # -- Scan
    "scan_interval": 15,

    # -- Preservação de lucro
    "meta_lucro_por_ciclo":   80.0,
    "ciclos_para_saque":      10,
    "banca_minima_trabalho": 200.0,
    "banca_minima":          200.0,
    "ao_quebrar":            "continuar",
    "pausa_ciclos":           5,

    # -- Claude AI
    "claude_key":     "",
    "claude_model":   "claude-haiku-4-5-20251001",
    "claude_enabled": False,

    # -- Arquivos (relativos à base)
    "cofre_file":     str(_CONFIG_BASE / "cofre_confluencia.json"),
    "historico_file": str(_CONFIG_BASE / "historico_confluencia.json"),
    "state_file":     str(_CONFIG_BASE / "state_confluencia.json"),
}


def _carregar_config() -> dict:
    cfg = dict(_DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            salvo = json.loads(CONFIG_FILE.read_text())
            cfg.update(salvo)
            # Garante caminhos absolutos dos arquivos JSON de estado
            for k in ("cofre_file", "historico_file", "state_file"):
                if not Path(cfg[k]).is_absolute():
                    cfg[k] = str(_CONFIG_BASE / cfg[k])
    except Exception as e:
        logging.warning(f"Config file error: {e} — using defaults")
    return cfg


CONFIG = _carregar_config()


# ============================================================
# COFRE (mesmo do bot_preservar)
# ============================================================

class Cofre:
    def __init__(self, arquivo: str):
        self.arquivo = Path(arquivo)
        self._d = self._load()

    def _load(self):
        try:
            if self.arquivo.exists():
                return json.loads(self.arquivo.read_text())
        except Exception: pass
        return {"total": 0.0, "ciclos_ganhos": 0, "entradas": []}

    def _save(self):
        try: self.arquivo.write_text(json.dumps(self._d, indent=2, ensure_ascii=False))
        except Exception as e: log.error(f"Cofre save error: {e}")

    def depositar(self, valor: float, ciclo: int):
        self._d["total"] = round(self._d["total"] + valor, 2)
        self._d["ciclos_ganhos"] += 1
        self._d["entradas"].append({"ciclo": ciclo, "valor": valor,
                                    "total": self._d["total"],
                                    "ts": datetime.now().isoformat()})
        self._save()
        log.info(f"💰 COFRE +R${valor:.2f} | Total: R${self._d['total']:.2f}")

    def descontar(self, valor: float):
        self._d["total"] = round(max(0, self._d["total"] - valor), 2)
        self._save()

    @property
    def total(self): return self._d["total"]

    @property
    def ciclos_ganhos(self): return self._d["ciclos_ganhos"]


# ============================================================
# BOT PRINCIPAL
# ============================================================

class BotConfluencia:

    def __init__(self, cfg: dict):
        self.cfg     = cfg
        self.iq      = None
        self.running = False

        self.ciclo_num      = 0
        self.ciclos_ganhos  = 0
        self.banca_trabalho = cfg["banca_trabalho"]

        self.cofre     = Cofre(cfg["cofre_file"])
        self.historico = self._load_hist()

        # Motor de sinais
        self.engine = SignalEngine(
            min_score    = cfg["min_score"],
            sr_tolerance = cfg["sr_tolerance"],
            usar_m5      = cfg["usar_m5"],
            filtrar_doji = cfg["filtrar_doji"]
        )

        # Ativo atualmente selecionado pelo scanner
        self.ativo_atual = (cfg.get("assets_reais") or cfg.get("assets_otc") or ["EURUSD-OTC"])[0]

        # Claude AI client (lazy init)
        self._claude = None
        if cfg.get("claude_enabled") and cfg.get("claude_key"):
            try:
                import anthropic
                self._claude = anthropic.Anthropic(api_key=cfg["claude_key"])
                log.info(f"Claude AI ativado — modelo: {cfg['claude_model']}")
            except ImportError:
                log.warning("anthropic não instalado. pip install anthropic")
            except Exception as e:
                log.warning(f"Claude init error: {e}")

        # Estatísticas da sessão
        self.stats = {
            "sinais_gerados":  0,
            "sinais_pulados":  0,
            "claude_aprovados": 0,
            "claude_pulados":   0,
            "wins": 0, "losses": 0
        }

    # --------------------------------------------------------
    # Conexão
    # --------------------------------------------------------

    def conectar(self) -> bool:
        log.info("Conectando à IQ Option...")
        self.iq = IQ_Option(self.cfg["email"], self.cfg["password"])
        ok, motivo = self.iq.connect()
        if not ok:
            log.error(f"Falha: {motivo}")
            return False
        self.iq.change_balance(self.cfg["account_type"])
        saldo = self.iq.get_balance()
        log.info(f"Conectado | {self.cfg['account_type']} | Saldo: R${saldo:.2f}")
        return True

    def reconectar(self) -> bool:
        espera = 10
        for i in range(1, 7):
            log.warning(f"Reconectando ({i}/6) em {espera}s...")
            time.sleep(espera)
            if self.conectar(): return True
            espera = min(espera * 2, 120)
        return False

    def _checar_conexao(self):
        try:
            if not self.iq.check_connect():
                self.reconectar()
        except Exception:
            self.reconectar()

    # --------------------------------------------------------
    # Loop principal
    # --------------------------------------------------------

    def iniciar(self):
        if not self.conectar(): return
        self.running = True
        self._banner()

        while self.running:
            if self.banca_trabalho < self.cfg["banca_minima_trabalho"]:
                log.error(
                    f"🛑 BANCA MÍNIMA ATINGIDA (R${self.banca_trabalho:.2f}). "
                    f"Cofre salvo: R${self.cofre.total:.2f}. Encerrando."
                )
                break

            try:
                self._executar_ciclo()
            except KeyboardInterrupt:
                log.info("Interrompido.")
                break
            except Exception as e:
                log.exception(f"Erro no ciclo: {e}")
                time.sleep(10)

            if self.running:
                time.sleep(self.cfg["pausa_ciclos"])

        self._banner_fim()

    def parar(self): self.running = False

    # --------------------------------------------------------
    # Ciclo completo
    # --------------------------------------------------------

    def _executar_ciclo(self):
        self.ciclo_num += 1
        payout = self._payout_real(self.ativo_atual) or self.cfg["payout"]

        log.info(f"\n{'─'*58}")
        log.info(
            f"CICLO #{self.ciclo_num} | "
            f"Banca: R${self.cfg['banca_trabalho']:.2f} | "
            f"Meta: +R${self.cfg['meta_ciclo']:.2f} | "
            f"Payout: {payout*100:.1f}% | "
            f"Cofre: R${self.cofre.total:.2f}"
        )
        log.info(f"{'─'*58}")

        Path(self.cfg["state_file"]).unlink(missing_ok=True)

        mgr = MasanielloManager(
            banca      = self.cfg["banca_trabalho"],
            meta       = self.cfg["meta_ciclo"],
            total_ops  = self.cfg["total_ops"],
            min_wins   = self.cfg["min_wins"],
            payout     = payout,
            state_file = self.cfg["state_file"]
        )

        inicio_ts = datetime.now().isoformat()

        while mgr.status == StatusCiclo.ANDAMENTO and self.running:
            self._checar_conexao()

            # Atualiza payout do ativo atual
            p_real = self._payout_real(self.ativo_atual)
            if p_real and abs(p_real - mgr.cfg["payout"]) > 0.02:
                mgr.alterar_payout(p_real)

            # Entrada Masaniello
            entrada = mgr.entrada_atual()
            if entrada < 0.01:
                time.sleep(2)
                continue

            # ── VARREDURA MULTI-ATIVO (real → OTC) ──────────
            sinal, resultado_analise = self._varrer_ativos()
            if sinal is None:
                continue   # nenhum ativo com sinal de qualidade
            # ─────────────────────────────────────────────────

            # Log da análise antes de entrar
            log.info(f"\n{resultado_analise}")

            # ── FILTRO CLAUDE AI (opcional) ──────────────────
            if self._claude:
                decisao_claude = self._consultar_claude(sinal, resultado_analise)
                if decisao_claude == "SKIP":
                    log.info("🤖 Claude: SKIP — entrada ignorada.")
                    self.stats["claude_pulados"] += 1
                    time.sleep(self.cfg["scan_interval"])
                    continue
                self.stats["claude_aprovados"] += 1
                log.info(f"🤖 Claude: {decisao_claude} — confirmado.")
            # ─────────────────────────────────────────────────

            # Executa o trade no ativo selecionado pelo scanner
            win = self._executar_trade(sinal, entrada, self.ativo_atual)
            if win is None:
                time.sleep(5)
                continue

            if win: self.stats["wins"] += 1
            else:   self.stats["losses"] += 1

            mgr.registrar_resultado(win)
            self._log_op(mgr)

        # Fim do ciclo
        r = mgr.resumo()
        self._processar_resultado(r, inicio_ts)

    # --------------------------------------------------------
    # Varredura multi-ativo (real → OTC fallback)
    # --------------------------------------------------------

    def _varrer_ativos(self):
        """
        Varre ativos reais abertos e, se nenhum tiver sinal, varre OTC.
        Seleciona o ativo com maior score de confluência acima do mínimo.
        Atualiza self.ativo_atual com o ativo escolhido.
        Retorna (sinal, SignalResult) ou (None, None).
        """
        try:
            abertos = self.iq.get_all_open_time()
        except Exception:
            abertos = {}

        def esta_aberto(asset):
            for t in ("binary", "turbo"):
                if abertos.get(t, {}).get(asset, {}).get("open"):
                    return True
            return False

        # Prioridade: reais abertos → OTC disponíveis
        reais_abertos = [a for a in self.cfg.get("assets_reais", []) if esta_aberto(a)]
        otcs          = self.cfg.get("assets_otc", ["EURUSD-OTC"])

        if reais_abertos:
            modo = "REAL"
            lista = reais_abertos
        else:
            modo = "OTC"
            lista = [a for a in otcs if esta_aberto(a)] or otcs

        log.info(f"Varrendo {len(lista)} ativo(s) [{modo}]: {', '.join(lista)}")

        melhor_score    = -1
        melhor_sinal    = None
        melhor_resultado = None
        melhor_ativo    = None

        for asset in lista:
            sinal, resultado = self._analisar_ativo(asset)
            if sinal is not None and resultado.score > melhor_score:
                melhor_score    = resultado.score
                melhor_sinal    = sinal
                melhor_resultado = resultado
                melhor_ativo    = asset

        if melhor_sinal is not None:
            self.ativo_atual = melhor_ativo
            self.stats["sinais_gerados"] += 1
            log.info(
                f"Melhor ativo: {melhor_ativo} | "
                f"Score: {melhor_score}/10 | Sinal: {melhor_sinal.upper()}"
            )
            return melhor_sinal, melhor_resultado

        log.debug(f"Nenhum ativo com score ≥ {self.cfg['min_score']}. Aguardando...")
        self.stats["sinais_pulados"] += 1
        time.sleep(self.cfg["scan_interval"])
        return None, None

    def _analisar_ativo(self, asset: str):
        """
        Analisa um único ativo e retorna (sinal, SignalResult) ou (None, None).
        """
        raw_m1 = self._buscar_candles(asset, 60,  self.cfg["candles_m1_qtd"])
        raw_m5 = self._buscar_candles(asset, 300, self.cfg["candles_m5_qtd"]) \
                 if self.cfg["usar_m5"] else None

        if not raw_m1 or len(raw_m1) < 55:
            return None, None

        df_m1 = self._raw_to_df(raw_m1)

        if not self._mercado_em_tendencia(df_m1):
            log.debug(f"{asset}: ADX baixo — lateral, ignorando.")
            return None, None

        df_m5    = self._raw_to_df(raw_m5) if raw_m5 else None
        resultado = self.engine.analisar(df_m1, df_m5)

        if resultado.sinal is not None:
            return resultado.sinal, resultado

        return None, None

    def _consultar_claude(self, sinal: str, resultado) -> str:
        """
        Envia a análise técnica para Claude e retorna CALL, PUT ou SKIP.
        Em caso de erro, retorna o sinal original para não bloquear o bot.
        """
        try:
            votos = getattr(resultado, "votos", {})
            score = getattr(resultado, "score", 0)
            motivos = getattr(resultado, "motivos", [])
            adx_val = getattr(resultado, "adx", None)

            prompt = (
                f"Você é um analista de opções binárias de alta frequência (M1). "
                f"Avalie o seguinte sinal técnico e responda APENAS com: CALL, PUT ou SKIP.\n\n"
                f"Ativo: {self.ativo_atual}\n"
                f"Sinal confluence: {sinal.upper()}\n"
                f"Score: {score}/10 indicadores alinhados\n"
                f"ADX: {adx_val if adx_val else 'n/d'}\n"
                f"Motivos: {', '.join(motivos) if motivos else 'n/d'}\n"
                f"Votos por indicador: {json.dumps(votos)}\n\n"
                f"Critérios para SKIP: score < 6, ADX < 22, votos contraditórios, "
                f"padrões de reversão fortes contra a direção.\n"
                f"Resposta (somente CALL, PUT ou SKIP):"
            )

            msg = self._claude.messages.create(
                model      = self.cfg.get("claude_model", "claude-haiku-4-5-20251001"),
                max_tokens = 10,
                messages   = [{"role": "user", "content": prompt}]
            )
            resposta = msg.content[0].text.strip().upper()
            for palavra in ("CALL", "PUT", "SKIP"):
                if palavra in resposta:
                    return palavra
            return sinal.upper()  # fallback: confia no sinal original
        except Exception as e:
            log.warning(f"Claude error: {e} — usando sinal original")
            return sinal.upper()

    def _mercado_em_tendencia(self, df: pd.DataFrame) -> bool:
        """
        Calcula ADX para verificar se há tendência.
        ADX < min → mercado lateral → evita entradas falsas.
        """
        if len(df) < 20: return True  # sem dados suficientes, deixa passar

        high  = df["high"]
        low   = df["low"]
        close = df["close"]

        dm_p = (high.diff()).clip(lower=0)
        dm_n = (-low.diff()).clip(lower=0)
        tr   = pd.concat([high - low,
                          (high - close.shift()).abs(),
                          (low  - close.shift()).abs()], axis=1).max(axis=1)

        periodo = 14
        tr_sm   = tr.rolling(periodo).mean()
        dm_p_sm = dm_p.rolling(periodo).mean()
        dm_n_sm = dm_n.rolling(periodo).mean()

        di_p = 100 * dm_p_sm / (tr_sm + 1e-10)
        di_n = 100 * dm_n_sm / (tr_sm + 1e-10)
        dx   = 100 * (di_p - di_n).abs() / (di_p + di_n + 1e-10)
        adx  = dx.rolling(periodo).mean()

        adx_val = adx.iloc[-1]
        log.debug(f"ADX: {adx_val:.1f} (mín: {self.cfg['adx_minimo']})")
        return adx_val >= self.cfg["adx_minimo"]

    # --------------------------------------------------------
    # Trade
    # --------------------------------------------------------

    def _executar_trade(self, direcao: str, entrada: float, asset: str = None):
        asset    = asset or self.ativo_atual
        duration = self.cfg["duration"]

        log.info(f"🔵 {asset} | {direcao.upper()} | R${entrada:.2f} | {duration}min")

        if not self._ativo_aberto(asset):
            log.warning(f"{asset} fechado. Aguardando 60s...")
            time.sleep(60)
            return None

        oid, ok = self.iq.buy(entrada, asset, direcao, duration)
        if not ok:
            log.error(f"Ordem rejeitada: {oid}")
            return None

        log.info(f"Ordem #{oid} — aguardando resultado...")
        timeout = duration * 60 + 30
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(3)
            res = self.iq.check_win_v3(oid)
            if res is not None:
                win = float(res) > 0
                log.info(f"{'✅ WIN' if win else '❌ LOSS'} | R${float(res):.2f}")
                return win

        log.warning("Timeout resultado.")
        return None

    # --------------------------------------------------------
    # Resultado do ciclo
    # --------------------------------------------------------

    def _processar_resultado(self, r: dict, inicio_ts: str):
        lucro = r["lucro"]

        if r["status"] == StatusCiclo.META.value:
            self.cofre.depositar(lucro, self.ciclo_num)
            self.ciclos_ganhos += 1
            log.info(f"✅ CICLO #{self.ciclo_num} META ATINGIDA | +R${lucro:.2f} → COFRE R${self.cofre.total:.2f}")

            if self.ciclos_ganhos % self.cfg["ciclos_para_saque"] == 0:
                log.info("=" * 58)
                log.info(f"🏦 SAQUE DISPONÍVEL! {self.ciclos_ganhos} ciclos ganhos")
                log.info(f"   Cofre: R${self.cofre.total:.2f}")
                log.info("=" * 58)

        elif r["status"] == StatusCiclo.QUEBRADO.value:
            perda = abs(lucro)
            if self.cofre.total >= perda:
                self.cofre.descontar(perda)
                log.warning(f"🚫 QUEBRADO — R${perda:.2f} do cofre | Cofre: R${self.cofre.total:.2f}")
            else:
                self.banca_trabalho = round(self.banca_trabalho - perda, 2)
                log.warning(f"🚫 QUEBRADO — R${perda:.2f} da banca | Banca: R${self.banca_trabalho:.2f}")

            if self.cfg["ao_quebrar"] == "parar":
                self.parar()

        # Estatísticas da sessão
        total_ops   = self.stats["wins"] + self.stats["losses"]
        taxa        = self.stats["wins"] / total_ops * 100 if total_ops else 0
        pulados     = self.stats["sinais_pulados"]
        gerados     = self.stats["sinais_gerados"]
        log.info(
            f"📊 SESSÃO | {total_ops} ops | "
            f"{self.stats['wins']}W/{self.stats['losses']}L ({taxa:.1f}%) | "
            f"Sinais: {gerados} gerados, {pulados} pulados"
        )

        self._save_hist(r, inicio_ts)

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _buscar_candles(self, asset, interval_sec, count):
        try:
            candles = self.iq.get_candles(asset, interval_sec, count, time.time())
            return candles
        except Exception as e:
            log.error(f"Erro ao buscar candles: {e}")
            return []

    def _raw_to_df(self, raw: list) -> pd.DataFrame:
        df = pd.DataFrame(raw)
        rename = {"max": "high", "min": "low", "from": "ts"}
        df.rename(columns=rename, inplace=True)
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "ts" in df.columns:
            df["ts"] = pd.to_datetime(df["ts"], unit="s")
            df.set_index("ts", inplace=True)
        df.sort_index(inplace=True)
        return df[["open", "high", "low", "close"]]

    def _payout_real(self, asset: str = None):
        try:
            asset  = asset or self.ativo_atual
            profit = self.iq.get_all_profit()
            dur    = str(self.cfg["duration"]) + "min"
            for tipo in ("binary", "turbo"):
                p = profit.get(tipo, {}).get(asset, {}).get(dur)
                if p:
                    return round(float(p), 4)
        except Exception:
            pass
        return None

    def _ativo_aberto(self, asset: str) -> bool:
        try:
            ab = self.iq.get_all_open_time()
            for t in ("binary", "turbo"):
                if ab.get(t, {}).get(asset, {}).get("open"):
                    return True
        except Exception: pass
        return False

    def _log_op(self, mgr):
        r = mgr.resumo()
        taxa = self.stats["wins"] / max(1, self.stats["wins"] + self.stats["losses"]) * 100
        log.info(
            f"  [{self.ativo_atual}] Op {r['op_atual']-1}/{r['total_ops']} | "
            f"Saldo: R${r['saldo_atual']:.2f} | "
            f"{r['wins']}W/{r['losses']}L | "
            f"Taxa sessão: {taxa:.1f}% | "
            f"Próx: R${r['proxima_entrada']:.2f}"
        )
        # Persiste ativo_atual no state file para o dashboard
        try:
            sf = Path(self.cfg["state_file"])
            if sf.exists():
                st = json.loads(sf.read_text())
                st["ativo_atual"] = self.ativo_atual
                sf.write_text(json.dumps(st, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _load_hist(self):
        try:
            f = Path(self.cfg["historico_file"])
            if f.exists(): return json.loads(f.read_text())
        except Exception: pass
        return []

    def _save_hist(self, r, inicio_ts):
        self.historico.append({
            "ciclo":       self.ciclo_num, "inicio": inicio_ts,
            "fim":         datetime.now().isoformat(), "status": r["status"],
            "ativo":       self.ativo_atual,
            "lucro":       r["lucro"], "wins": r["wins"], "losses": r["losses"],
            "cofre":       self.cofre.total
        })
        try:
            Path(self.cfg["historico_file"]).write_text(
                json.dumps(self.historico, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            log.error(f"Erro histórico: {e}")

    def _banner(self):
        claude_info = "on" if self._claude else "off"
        reais = ", ".join(self.cfg.get("assets_reais", []))
        otcs  = ", ".join(self.cfg.get("assets_otc",   []))
        log.info("=" * 58)
        log.info("  BOT CONFLUÊNCIA — Masaniello + 10 Indicadores")
        log.info(f"  Modo: REAL → OTC | M1 + {'M5' if self.cfg['usar_m5'] else 'off'}")
        log.info(f"  Reais : {reais}")
        log.info(f"  OTC   : {otcs}")
        log.info(f"  Score mínimo: {self.cfg['min_score']}/10 | ADX mín: {self.cfg['adx_minimo']}")
        log.info(f"  Banca: R${self.cfg['banca_trabalho']:.2f} | Meta: +R${self.cfg['meta_ciclo']:.2f}")
        log.info(f"  Cofre: R${self.cofre.total:.2f} | Claude AI: {claude_info}")
        log.info("=" * 58)

    def _banner_fim(self):
        total_ops = self.stats["wins"] + self.stats["losses"]
        taxa      = self.stats["wins"] / max(1, total_ops) * 100
        log.info("=" * 58)
        log.info(f"  SESSÃO ENCERRADA | {self.ciclo_num} ciclos")
        log.info(f"  Taxa de acerto: {taxa:.1f}% ({self.stats['wins']}W/{self.stats['losses']}L)")
        log.info(f"  Sinais gerados: {self.stats['sinais_gerados']} | "
                 f"pulados: {self.stats['sinais_pulados']}")
        if self._claude:
            log.info(f"  Claude aprovados: {self.stats['claude_aprovados']} | "
                     f"pulados: {self.stats['claude_pulados']}")
        log.info(f"  💰 COFRE: R${self.cofre.total:.2f}")
        log.info(f"  Banca de trabalho: R${self.banca_trabalho:.2f}")
        log.info("=" * 58)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # Recarrega config do arquivo em disco antes de iniciar
    CONFIG = _carregar_config()
    bot = BotConfluencia(CONFIG)

    def _sair(sig, frame):
        log.info("Encerrando...")
        bot.parar()

    _signal.signal(_signal.SIGINT,  _sair)
    _signal.signal(_signal.SIGTERM, _sair)

    bot.iniciar()
