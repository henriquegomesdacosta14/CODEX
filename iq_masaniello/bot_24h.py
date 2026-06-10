"""
bot_24h.py
==========
Bot Masaniello para IQ Option — modo 24h contínuo.
Reinicia ciclos automaticamente, atualiza a banca e para só se
a banca cair abaixo do limite de segurança configurado.

Dependência:
    pip install iqoptionapi

Uso:
    python bot_24h.py

Para rodar em background no Linux/VPS:
    nohup python bot_24h.py &
    ou com screen: screen -S masaniello   →   python bot_24h.py   →   Ctrl+A D
"""

import time
import json
import logging
from datetime import datetime
from pathlib import Path

from iqoptionapi.stable_api import IQ_Option
from masaniello_core import MasanielloManager, StatusCiclo

# ============================================================
# LOGGING — grava em arquivo e no terminal
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_24h.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÃO
# ============================================================
CONFIG = {
    # -- Credenciais
    "email":        "SEU_EMAIL@iqoption.com",
    "password":     "SUA_SENHA",
    "account_type": "PRACTICE",      # "PRACTICE" ou "REAL"

    # -- Ativo
    "asset":    "EURUSD-OTC",
    "duration": 1,                   # minutos

    # -- Masaniello por ciclo
    "meta_pct":   0.10,              # meta de lucro = 10% da banca atual
    "total_ops":  10,                # operações por ciclo
    "min_wins":   6,                 # mínimo de gains por ciclo
    "payout":     0.85,              # 85% — atualizado automaticamente

    # -- Segurança
    "banca_minima":    50.0,         # para se banca cair abaixo disso
    "max_ciclos":      0,            # 0 = infinito; N = para após N ciclos
    "pausa_entre_ciclos": 5,         # segundos de pausa entre ciclos

    # -- Arquivos
    "state_file":    "masaniello_state.json",
    "historico_file": "historico_ciclos.json",
    "log_file":      "bot_24h.log",
}


# ============================================================
# HISTÓRICO DE CICLOS
# ============================================================

def carregar_historico(arquivo):
    try:
        if Path(arquivo).exists():
            return json.loads(Path(arquivo).read_text())
    except Exception:
        pass
    return []

def salvar_historico(arquivo, historico):
    try:
        Path(arquivo).write_text(json.dumps(historico, indent=2, ensure_ascii=False))
    except Exception as e:
        log.error(f"Erro ao salvar histórico: {e}")


# ============================================================
# BOT 24H
# ============================================================

class Bot24h:

    def __init__(self, cfg):
        self.cfg      = cfg
        self.iq       = None
        self.running  = False
        self.ciclo_num = 0
        self.banca_atual = None          # banca real da IQ após cada ciclo
        self.historico   = carregar_historico(cfg["historico_file"])

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
        self.banca_atual = self.iq.get_balance()
        log.info(f"Conectado | {self.cfg['account_type']} | Saldo: R${self.banca_atual:.2f}")
        return True

    def reconectar(self) -> bool:
        espera = 10
        for i in range(1, 7):
            log.warning(f"Reconectando ({i}/6) em {espera}s...")
            time.sleep(espera)
            if self.conectar():
                return True
            espera = min(espera * 2, 120)
        return False

    def _verificar_conexao(self):
        """Reconecta silenciosamente se necessário."""
        try:
            if not self.iq.check_connect():
                log.warning("Conexão caiu. Reconectando...")
                self.reconectar()
        except Exception:
            self.reconectar()

    # --------------------------------------------------------
    # Loop principal
    # --------------------------------------------------------

    def iniciar(self):
        if not self.conectar():
            log.error("Não foi possível conectar. Abortando.")
            return

        self.running = True
        log.info("=" * 60)
        log.info("  BOT 24H INICIADO")
        log.info(f"  Meta por ciclo: {self.cfg['meta_pct']*100:.0f}% da banca")
        log.info(f"  Ciclo: {self.cfg['total_ops']} ops / {self.cfg['min_wins']} gains mín.")
        log.info(f"  Banca mínima de segurança: R${self.cfg['banca_minima']:.2f}")
        log.info(f"  Máx. ciclos: {'infinito' if not self.cfg['max_ciclos'] else self.cfg['max_ciclos']}")
        log.info("=" * 60)

        while self.running:
            # Verifica banca mínima
            self._verificar_conexao()
            self.banca_atual = self.iq.get_balance()

            if self.banca_atual < self.cfg["banca_minima"]:
                log.error(
                    f"🛑 BANCA ABAIXO DO MÍNIMO! "
                    f"R${self.banca_atual:.2f} < R${self.cfg['banca_minima']:.2f}. "
                    f"Bot encerrado para proteger a banca."
                )
                break

            # Verifica limite de ciclos
            if self.cfg["max_ciclos"] and self.ciclo_num >= self.cfg["max_ciclos"]:
                log.info(f"Limite de {self.cfg['max_ciclos']} ciclos atingido. Encerrando.")
                break

            # Executa um ciclo completo
            try:
                self._executar_ciclo()
            except KeyboardInterrupt:
                log.info("Interrompido pelo usuário.")
                break
            except Exception as e:
                log.exception(f"Erro no ciclo: {e}")
                time.sleep(10)

            # Pausa entre ciclos
            if self.running and self.cfg["pausa_entre_ciclos"]:
                log.info(f"Pausa de {self.cfg['pausa_entre_ciclos']}s antes do próximo ciclo...")
                time.sleep(self.cfg["pausa_entre_ciclos"])

        self._imprimir_resumo_geral()
        log.info("Bot encerrado.")

    def parar(self):
        self.running = False

    # --------------------------------------------------------
    # Um ciclo completo
    # --------------------------------------------------------

    def _executar_ciclo(self):
        self.ciclo_num += 1

        # Meta do ciclo = % da banca atual
        banca  = self.banca_atual
        meta   = round(banca * self.cfg["meta_pct"], 2)
        payout = self._obter_payout_real() or self.cfg["payout"]

        log.info(f"\n{'─'*50}")
        log.info(f"CICLO #{self.ciclo_num} | Banca: R${banca:.2f} | Meta: +R${meta:.2f} | Payout: {payout*100:.1f}%")
        log.info(f"{'─'*50}")

        # Cria novo manager para este ciclo
        # Apaga state_file para forçar ciclo limpo
        Path(self.cfg["state_file"]).unlink(missing_ok=True)

        mgr = MasanielloManager(
            banca      = banca,
            meta       = meta,
            total_ops  = self.cfg["total_ops"],
            min_wins   = self.cfg["min_wins"],
            payout     = payout,
            state_file = self.cfg["state_file"]
        )

        ciclo_inicio = datetime.now().isoformat()

        # Loop de operações do ciclo
        while mgr.status == StatusCiclo.ANDAMENTO and self.running:

            self._verificar_conexao()

            # Atualiza payout antes de cada entrada
            payout_atual = self._obter_payout_real()
            if payout_atual and abs(payout_atual - mgr.cfg["payout"]) > 0.02:
                mgr.alterar_payout(payout_atual)

            entrada = mgr.entrada_atual()
            if entrada < 0.01:
                time.sleep(2)
                continue

            # ── INTEGRAÇÃO COM SEU SINAL ─────────────────────
            # Substitua _aguardar_sinal() pelo gerador de sinais do seu bot.
            # Deve retornar "call", "put" ou None.
            sinal = self._aguardar_sinal()
            if sinal is None:
                time.sleep(2)
                continue
            # ─────────────────────────────────────────────────

            win = self._executar_trade(sinal, entrada)
            if win is None:
                log.warning("Resultado indeterminado. Aguardando próximo sinal...")
                time.sleep(5)
                continue

            mgr.registrar_resultado(win)
            self._log_resumo(mgr)

        # Ciclo encerrado — registra no histórico
        r = mgr.resumo()
        self._registrar_historico(ciclo_inicio, r)

        # Atualiza banca real da IQ
        time.sleep(2)
        self._verificar_conexao()
        self.banca_atual = self.iq.get_balance()

        # Log do resultado do ciclo
        emoji = "🎉" if mgr.status == StatusCiclo.META else "🚫" if mgr.status == StatusCiclo.QUEBRADO else "⏹"
        log.info(
            f"{emoji} CICLO #{self.ciclo_num} ENCERRADO | "
            f"Status: {mgr.status.value} | "
            f"Lucro: {'+'if r['lucro']>=0 else ''}{r['lucro']:.2f} | "
            f"Banca IQ agora: R${self.banca_atual:.2f}"
        )

    # --------------------------------------------------------
    # Trade
    # --------------------------------------------------------

    def _executar_trade(self, direcao: str, entrada: float):
        asset    = self.cfg["asset"]
        duration = self.cfg["duration"]

        log.info(f"🔵 {asset} | {direcao.upper()} | R${entrada:.2f} | {duration}min")

        if not self._ativo_disponivel(asset):
            log.warning(f"Ativo {asset} fechado. Aguardando...")
            time.sleep(60)
            return None

        order_id, ok = self.iq.buy(entrada, asset, direcao, duration)
        if not ok:
            log.error(f"Ordem rejeitada: {order_id}")
            return None

        log.info(f"Ordem #{order_id} — aguardando resultado...")
        timeout = duration * 60 + 30
        inicio  = time.time()

        while time.time() - inicio < timeout:
            time.sleep(3)
            resultado = self.iq.check_win_v3(order_id)
            if resultado is not None:
                win = float(resultado) > 0
                log.info(f"{'✅ WIN' if win else '❌ LOSS'} | R${float(resultado):.2f}")
                return win

        log.warning("Timeout aguardando resultado.")
        return None

    # --------------------------------------------------------
    # Sinal — ADAPTE AQUI
    # --------------------------------------------------------

    def _aguardar_sinal(self):
        """
        === COLOQUE AQUI A LÓGICA DO SEU BOT ===
        Retorne: "call" / "put" / None
        """
        # STUB de teste: alterna call/put aleatoriamente
        import random
        time.sleep(2)  # simula tempo de espera pelo sinal
        return random.choice(["call", "put"])

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _obter_payout_real(self):
        try:
            profit = self.iq.get_all_profit()
            dur    = str(self.cfg["duration"]) + "min"
            p = profit.get("binary", {}).get(self.cfg["asset"], {}).get(dur)
            if p:
                return round(float(p), 4)
        except Exception:
            pass
        return None

    def _ativo_disponivel(self, asset: str) -> bool:
        try:
            abertos = self.iq.get_all_open_time()
            for tipo in ("binary", "turbo"):
                if abertos.get(tipo, {}).get(asset, {}).get("open"):
                    return True
        except Exception:
            pass
        return False

    def _log_resumo(self, mgr):
        r = mgr.resumo()
        log.info(
            f"📊 Op {r['op_atual']-1}/{r['total_ops']} | "
            f"Saldo: R${r['saldo_atual']:.2f} | "
            f"Lucro: {'+'if r['lucro']>=0 else ''}{r['lucro']:.2f} | "
            f"{r['wins']}W/{r['losses']}L | "
            f"Próx. entrada: R${r['proxima_entrada']:.2f}"
        )

    def _registrar_historico(self, inicio, resumo):
        entrada = {
            "ciclo":       self.ciclo_num,
            "inicio":      inicio,
            "fim":         datetime.now().isoformat(),
            "status":      resumo["status"],
            "banca_ini":   resumo["banca_inicial"],
            "saldo_final": resumo["saldo_atual"],
            "lucro":       resumo["lucro"],
            "roi_pct":     resumo["roi_pct"],
            "wins":        resumo["wins"],
            "losses":      resumo["losses"],
        }
        self.historico.append(entrada)
        salvar_historico(self.cfg["historico_file"], self.historico)

    def _imprimir_resumo_geral(self):
        if not self.historico:
            return
        total_lucro = sum(h["lucro"] for h in self.historico)
        wins_ciclos = sum(1 for h in self.historico if h["status"] == "meta_atingida")
        log.info("=" * 60)
        log.info(f"  RESUMO GERAL — {self.ciclo_num} ciclos rodados")
        log.info(f"  Ciclos com meta atingida: {wins_ciclos}/{self.ciclo_num}")
        log.info(f"  Lucro total acumulado: R${total_lucro:.2f}")
        log.info(f"  Banca final: R${self.banca_atual:.2f}")
        log.info("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import signal

    bot = Bot24h(CONFIG)

    # Ctrl+C encerra limpo
    def _sair(sig, frame):
        log.info("Sinal de encerramento recebido. Finalizando...")
        bot.parar()

    signal.signal(signal.SIGINT,  _sair)
    signal.signal(signal.SIGTERM, _sair)

    bot.iniciar()
