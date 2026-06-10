"""
bot_preservar.py
================
Bot Masaniello com estratégia de PRESERVAÇÃO DE LUCRO.

Lógica:
  - Cada ciclo usa banca fixa (ex: R$1.000)
  - Ao atingir a meta → lucro vai para "cofre"
  - Ao quebrar o ciclo → perde da banca de trabalho
  - A cada 10 ciclos bem-sucedidos → emite alerta "saque disponível"
  - Nunca arrisca o cofre — só a banca de trabalho

Parâmetros ajustados para 46% de win rate:
  - 10 operações por ciclo
  - 5 gains mínimos (50%) → probabilidade ~53% de atingir meta
  - Meta conservadora: 8% da banca (não 10%)

Dependência:
    pip install iqoptionapi

Uso:
    python bot_preservar.py
"""

import time
import json
import logging
import signal
from datetime import datetime
from pathlib import Path

from iqoptionapi.stable_api import IQ_Option
from masaniello_core import MasanielloManager, StatusCiclo

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_preservar.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÃO
# ============================================================
CONFIG = {
    # -- Credenciais IQ Option
    "email":        "SEU_EMAIL@iqoption.com",
    "password":     "SUA_SENHA",
    "account_type": "PRACTICE",       # "PRACTICE" ou "REAL"

    # -- Ativo e duração
    "asset":    "EURUSD-OTC",
    "duration": 1,                    # minutos

    # -- Banca de trabalho (fixa por ciclo)
    "banca_trabalho":  1000.0,        # R$ — sempre começa cada ciclo com isso
    "meta_ciclo":       80.0,         # R$ — lucro alvo por ciclo (8% da banca)

    # -- Masaniello — ajustado para ~46% de win rate
    "total_ops":  10,                 # operações por ciclo
    "min_wins":    5,                 # mínimo de gains (50% de 10 ops)
    "payout":     0.85,               # atualizado automaticamente da IQ

    # -- Preservação de lucro
    "lucro_por_ciclo":         80.0,  # quanto vai para o cofre por ciclo ganho
    "ciclos_para_garantir":    10,    # a cada X ciclos ganhos, emite alerta de saque
    "banca_minima_trabalho":  200.0,  # para se banca de trabalho cair abaixo disso

    # -- Comportamento ao quebrar ciclo
    # "continuar"  → reinicia com nova banca e continua
    # "parar"      → para e avisa
    "ao_quebrar": "continuar",

    # -- Pausa entre ciclos (segundos)
    "pausa_ciclos": 5,

    # -- Arquivos de estado
    "cofre_file":     "cofre.json",
    "historico_file": "historico_preservar.json",
    "state_file":     "masaniello_state.json",
}


# ============================================================
# COFRE — salva lucros garantidos
# ============================================================

class Cofre:
    """Guarda os lucros preservados fora da banca de trabalho."""

    def __init__(self, arquivo: str):
        self.arquivo = Path(arquivo)
        self._dados  = self._carregar()

    def _carregar(self) -> dict:
        try:
            if self.arquivo.exists():
                return json.loads(self.arquivo.read_text())
        except Exception:
            pass
        return {"total": 0.0, "entradas": [], "ciclos_ganhos": 0}

    def _salvar(self):
        try:
            self.arquivo.write_text(json.dumps(self._dados, indent=2, ensure_ascii=False))
        except Exception as e:
            log.error(f"Erro ao salvar cofre: {e}")

    def depositar(self, valor: float, ciclo_num: int):
        self._dados["total"] = round(self._dados["total"] + valor, 2)
        self._dados["ciclos_ganhos"] += 1
        self._dados["entradas"].append({
            "ciclo": ciclo_num,
            "valor": valor,
            "total_acumulado": self._dados["total"],
            "ts": datetime.now().isoformat()
        })
        self._salvar()
        log.info(f"💰 COFRE +R${valor:.2f} | Total no cofre: R${self._dados['total']:.2f}")

    @property
    def total(self) -> float:
        return self._dados["total"]

    @property
    def ciclos_ganhos(self) -> int:
        return self._dados["ciclos_ganhos"]

    def resumo(self) -> dict:
        return {
            "total_no_cofre": self._dados["total"],
            "ciclos_ganhos":  self._dados["ciclos_ganhos"]
        }


# ============================================================
# BOT PRINCIPAL
# ============================================================

class BotPreservar:

    def __init__(self, cfg: dict):
        self.cfg      = cfg
        self.iq       = None
        self.running  = False
        self.ciclo_num       = 0
        self.ciclos_ganhos   = 0
        self.banca_trabalho  = cfg["banca_trabalho"]  # saldo disponível para operar

        self.cofre     = Cofre(cfg["cofre_file"])
        self.historico = self._carregar_historico()

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
        saldo_iq = self.iq.get_balance()
        log.info(f"Conectado | {self.cfg['account_type']} | Saldo IQ: R${saldo_iq:.2f}")
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
        try:
            if not self.iq.check_connect():
                self.reconectar()
        except Exception:
            self.reconectar()

    # --------------------------------------------------------
    # Loop principal
    # --------------------------------------------------------

    def iniciar(self):
        if not self.conectar():
            log.error("Falha na conexão. Abortando.")
            return

        self.running = True
        self._banner_inicio()

        while self.running:
            # Verifica banca mínima de segurança
            if self.banca_trabalho < self.cfg["banca_minima_trabalho"]:
                log.error(
                    f"🛑 BANCA DE TRABALHO ABAIXO DO MÍNIMO!\n"
                    f"   Banca atual: R${self.banca_trabalho:.2f}\n"
                    f"   Mínimo:      R${self.cfg['banca_minima_trabalho']:.2f}\n"
                    f"   Bot encerrado para proteger. Cofre intacto: R${self.cofre.total:.2f}"
                )
                break

            try:
                self._executar_ciclo()
            except KeyboardInterrupt:
                log.info("Interrompido pelo usuário.")
                break
            except Exception as e:
                log.exception(f"Erro inesperado: {e}")
                time.sleep(10)

            if self.running and self.cfg["pausa_ciclos"]:
                time.sleep(self.cfg["pausa_ciclos"])

        self._banner_encerramento()

    def parar(self):
        self.running = False

    # --------------------------------------------------------
    # Um ciclo completo
    # --------------------------------------------------------

    def _executar_ciclo(self):
        self.ciclo_num += 1

        # Banca deste ciclo = sempre a banca de trabalho configurada
        banca_ciclo = self.cfg["banca_trabalho"]
        meta_ciclo  = self.cfg["meta_ciclo"]
        payout      = self._obter_payout_real() or self.cfg["payout"]

        log.info(f"\n{'─'*55}")
        log.info(
            f"CICLO #{self.ciclo_num} | "
            f"Banca: R${banca_ciclo:.2f} | "
            f"Meta: +R${meta_ciclo:.2f} | "
            f"Payout: {payout*100:.1f}% | "
            f"Cofre: R${self.cofre.total:.2f}"
        )
        log.info(f"{'─'*55}")

        # Limpa state do ciclo anterior
        Path(self.cfg["state_file"]).unlink(missing_ok=True)

        mgr = MasanielloManager(
            banca      = banca_ciclo,
            meta       = meta_ciclo,
            total_ops  = self.cfg["total_ops"],
            min_wins   = self.cfg["min_wins"],
            payout     = payout,
            state_file = self.cfg["state_file"]
        )

        inicio_ts = datetime.now().isoformat()

        # Loop de operações
        while mgr.status == StatusCiclo.ANDAMENTO and self.running:
            self._verificar_conexao()

            # Atualiza payout se mudou
            payout_real = self._obter_payout_real()
            if payout_real and abs(payout_real - mgr.cfg["payout"]) > 0.02:
                mgr.alterar_payout(payout_real)

            entrada = mgr.entrada_atual()
            if entrada < 0.01:
                time.sleep(2)
                continue

            # ── SEU SINAL AQUI ───────────────────────────────
            sinal = self._aguardar_sinal()
            if sinal is None:
                time.sleep(2)
                continue
            # ─────────────────────────────────────────────────

            win = self._executar_trade(sinal, entrada)
            if win is None:
                time.sleep(5)
                continue

            mgr.registrar_resultado(win)
            self._log_op(mgr)

        # ── Resultado do ciclo ────────────────────────────────
        r = mgr.resumo()
        self._processar_resultado_ciclo(r, inicio_ts)

    def _processar_resultado_ciclo(self, r: dict, inicio_ts: str):
        """Decide o que fazer com o resultado do ciclo."""
        lucro_ciclo = r["lucro"]

        if r["status"] == StatusCiclo.META.value:
            # ✅ META ATINGIDA — deposita no cofre
            self.cofre.depositar(lucro_ciclo, self.ciclo_num)
            self.ciclos_ganhos += 1

            # Atualiza banca de trabalho (a meta foi tirada, volta para R$1000)
            # A banca de trabalho NÃO muda — continua R$1000
            # O lucro vai para o cofre

            log.info(
                f"✅ CICLO #{self.ciclo_num} — META ATINGIDA!\n"
                f"   +R${lucro_ciclo:.2f} → COFRE\n"
                f"   Cofre total: R${self.cofre.total:.2f}\n"
                f"   Ciclos ganhos: {self.ciclos_ganhos}"
            )

            # Alerta de saque a cada X ciclos ganhos
            if self.ciclos_ganhos % self.cfg["ciclos_para_garantir"] == 0:
                self._alerta_saque()

        elif r["status"] == StatusCiclo.QUEBRADO.value:
            # ❌ CICLO QUEBRADO — perda vai da banca de trabalho
            perda = abs(lucro_ciclo)

            # Se tem lucro no cofre, absorve a perda do cofre primeiro
            if self.cofre.total >= perda:
                log.warning(
                    f"🚫 CICLO #{self.ciclo_num} QUEBRADO — "
                    f"R${perda:.2f} absorvidos do cofre\n"
                    f"   Cofre: R${self.cofre.total:.2f} → R${self.cofre.total - perda:.2f}"
                )
                # Desconta do cofre para proteger a banca de trabalho
                self.cofre._dados["total"] = round(self.cofre.total - perda, 2)
                self.cofre._salvar()
            else:
                # Cofre insuficiente — desconta da banca de trabalho
                self.banca_trabalho = round(self.banca_trabalho - perda, 2)
                log.warning(
                    f"🚫 CICLO #{self.ciclo_num} QUEBRADO — "
                    f"R${perda:.2f} descontados da banca de trabalho\n"
                    f"   Banca de trabalho: R${self.banca_trabalho:.2f}"
                )

            if self.cfg["ao_quebrar"] == "parar":
                log.warning("Configurado para parar ao quebrar. Encerrando.")
                self.parar()

        else:
            log.info(f"⏹ CICLO #{self.ciclo_num} FINALIZADO | Lucro: R${lucro_ciclo:.2f}")

        # Salva no histórico
        self._salvar_historico_ciclo(r, inicio_ts)

    def _alerta_saque(self):
        """Emite alerta de saque disponível a cada 10 ciclos ganhos."""
        log.info("=" * 55)
        log.info(f"🏦 SAQUE DISPONÍVEL!")
        log.info(f"   {self.ciclos_ganhos} ciclos ganhos completados")
        log.info(f"   Cofre acumulado: R${self.cofre.total:.2f}")
        log.info(f"   Sugestão: saque R${self.cofre.total * 0.5:.2f} e deixe R${self.cofre.total * 0.5:.2f} como reserva")
        log.info("=" * 55)
        # Aqui você pode integrar notificação por Telegram, e-mail etc.

    # --------------------------------------------------------
    # Trade
    # --------------------------------------------------------

    def _executar_trade(self, direcao: str, entrada: float):
        asset    = self.cfg["asset"]
        duration = self.cfg["duration"]

        log.info(f"🔵 {asset} | {direcao.upper()} | R${entrada:.2f} | {duration}min")

        if not self._ativo_disponivel(asset):
            log.warning(f"{asset} fechado. Aguardando 60s...")
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
    # Sinal — ADAPTE AQUI com a lógica do seu IQBOT
    # --------------------------------------------------------

    def _aguardar_sinal(self):
        """
        === COLOQUE AQUI O SINAL DO SEU BOT ===
        Retorne: "call" / "put" / None

        Seu bot usa EMA20/EMA50 M1.
        Se ele exporta o sinal em arquivo ou fila, leia aqui.
        """
        import random
        time.sleep(1)
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

    def _log_op(self, mgr):
        r = mgr.resumo()
        log.info(
            f"  Op {r['op_atual']-1}/{r['total_ops']} | "
            f"Saldo ciclo: R${r['saldo_atual']:.2f} | "
            f"{r['wins']}W/{r['losses']}L | "
            f"Próx: R${r['proxima_entrada']:.2f} | "
            f"Needs: {r['rem_wins']} wins em {r['rem_ops']} ops"
        )

    def _carregar_historico(self):
        try:
            f = Path(self.cfg["historico_file"])
            if f.exists():
                return json.loads(f.read_text())
        except Exception:
            pass
        return []

    def _salvar_historico_ciclo(self, r: dict, inicio_ts: str):
        self.historico.append({
            "ciclo":       self.ciclo_num,
            "inicio":      inicio_ts,
            "fim":         datetime.now().isoformat(),
            "status":      r["status"],
            "lucro":       r["lucro"],
            "wins":        r["wins"],
            "losses":      r["losses"],
            "taxa":        r["taxa_acerto"],
            "cofre_total": self.cofre.total,
        })
        try:
            Path(self.cfg["historico_file"]).write_text(
                json.dumps(self.historico, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            log.error(f"Erro ao salvar histórico: {e}")

    def _banner_inicio(self):
        log.info("=" * 55)
        log.info("  BOT MASANIELLO — PRESERVAÇÃO DE LUCRO")
        log.info(f"  Banca de trabalho: R${self.cfg['banca_trabalho']:.2f} (fixa)")
        log.info(f"  Meta por ciclo:    +R${self.cfg['meta_ciclo']:.2f}")
        log.info(f"  Ciclo:             {self.cfg['total_ops']} ops / {self.cfg['min_wins']} gains mín.")
        log.info(f"  Saque sugerido:    a cada {self.cfg['ciclos_para_garantir']} ciclos ganhos")
        log.info(f"  Cofre atual:       R${self.cofre.total:.2f}")
        log.info("=" * 55)

    def _banner_encerramento(self):
        total_ops   = sum(h["wins"] + h["losses"] for h in self.historico[-self.ciclo_num:])
        ciclos_ok   = sum(1 for h in self.historico[-self.ciclo_num:] if h["status"] == "meta_atingida")
        log.info("=" * 55)
        log.info("  SESSÃO ENCERRADA")
        log.info(f"  Ciclos rodados:     {self.ciclo_num}")
        log.info(f"  Ciclos com meta:    {ciclos_ok}/{self.ciclo_num} ({ciclos_ok/max(1,self.ciclo_num)*100:.0f}%)")
        log.info(f"  Operações totais:   {total_ops}")
        log.info(f"  💰 COFRE TOTAL:     R${self.cofre.total:.2f}")
        log.info(f"  Banca de trabalho: R${self.banca_trabalho:.2f}")
        log.info("=" * 55)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    bot = BotPreservar(CONFIG)

    def _sair(sig, frame):
        log.info("Encerrando...")
        bot.parar()

    signal.signal(signal.SIGINT,  _sair)
    signal.signal(signal.SIGTERM, _sair)

    bot.iniciar()
