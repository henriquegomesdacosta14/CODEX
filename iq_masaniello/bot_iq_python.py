"""
bot_iq_python.py
================
Bot Masaniello para IQ Option — Python
Integra o módulo masaniello_core com a API da IQ Option.

Dependência:
    pip install iqoptionapi

Como usar:
    1. Edite o bloco CONFIG abaixo com seus dados
    2. Execute: python bot_iq_python.py
    3. O bot vai aguardar sua lógica de sinal (adapte _aguardar_sinal)

ATENÇÃO: Use conta PRACTICE para testar antes de operar com dinheiro real.
"""

import time
import logging
import threading
from datetime import datetime

# API não-oficial da IQ Option (compatível com Python 3.6+)
# Repositório: https://github.com/Lu-Yi-Hsun/iqoptionapi
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
        logging.FileHandler("masaniello_bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÃO — edite aqui
# ============================================================
CONFIG = {
    # -- Credenciais IQ Option
    "email":        "SEU_EMAIL@iqoption.com",
    "password":     "SUA_SENHA",
    "account_type": "PRACTICE",   # "PRACTICE" para demo, "REAL" para conta real

    # -- Ativo e parâmetros de trade
    "asset":        "EURUSD-OTC",  # nome do ativo (OTC para fins de semana)
    "duration":     1,             # duração em minutos (1, 2, 5...)

    # -- Masaniello
    "banca_inicial": 1000.0,   # R$ — banca do ciclo
    "meta_lucro":     100.0,   # R$ — lucro desejado no ciclo
    "total_ops":        8,     # número total de operações no ciclo
    "min_wins":         5,     # mínimo de acertos para atingir a meta
    "payout":          0.85,   # 85% — ajuste conforme o ativo/horário

    # -- Tolerância mínima de banca para entrar
    "banca_minima": 1.0,       # não entra se saldo cair abaixo disso

    # -- Intervalo entre verificações (segundos)
    "loop_interval": 2,
}


# ============================================================
# BOT
# ============================================================

class MasanielloBot:

    def __init__(self, config: dict):
        self.cfg = config
        self.iq  = None

        # Inicializa o gerenciador Masaniello
        self.manager = MasanielloManager(
            banca      = config["banca_inicial"],
            meta       = config["meta_lucro"],
            total_ops  = config["total_ops"],
            min_wins   = config["min_wins"],
            payout     = config["payout"],
            state_file = "masaniello_state.json"
        )

        self._running = False

    # ----------------------------------------------------------
    # Conexão
    # ----------------------------------------------------------

    def conectar(self) -> bool:
        """Conecta e autentica na IQ Option."""
        logger.info("Conectando à IQ Option...")
        self.iq = IQ_Option(self.cfg["email"], self.cfg["password"])
        check, reason = self.iq.connect()
        if not check:
            logger.error(f"Falha na conexão: {reason}")
            return False

        self.iq.change_balance(self.cfg["account_type"])
        saldo = self.iq.get_balance()
        logger.info(f"Conectado! Conta: {self.cfg['account_type']} | Saldo IQ: R${saldo:.2f}")
        return True

    def reconectar(self):
        """Tenta reconectar em loop com backoff exponencial."""
        espera = 5
        for tentativa in range(1, 6):
            logger.warning(f"Tentativa de reconexão {tentativa}/5 em {espera}s...")
            time.sleep(espera)
            if self.conectar():
                return True
            espera = min(espera * 2, 60)
        logger.error("Não foi possível reconectar. Encerrando.")
        return False

    # ----------------------------------------------------------
    # Loop principal
    # ----------------------------------------------------------

    def iniciar(self):
        """Inicia o loop principal do bot."""
        if not self.conectar():
            return

        self._running = True
        logger.info("Bot iniciado. Aguardando sinais...")
        self._imprimir_resumo()

        while self._running:
            try:
                self._ciclo()
            except ConnectionError:
                logger.error("Conexão perdida.")
                if not self.reconectar():
                    break
            except KeyboardInterrupt:
                logger.info("Bot interrompido pelo usuário.")
                break
            except Exception as e:
                logger.exception(f"Erro inesperado: {e}")
                time.sleep(5)

        logger.info("Bot encerrado.")

    def parar(self):
        self._running = False

    # ----------------------------------------------------------
    # Lógica de ciclo
    # ----------------------------------------------------------

    def _ciclo(self):
        """Uma iteração do loop principal."""
        status = self.manager.status

        # Ciclo encerrado — verifica se deve reiniciar
        if status != StatusCiclo.ANDAMENTO:
            self._tratar_ciclo_encerrado(status)
            return

        # Verifica se tem saldo suficiente
        entrada = self.manager.entrada_atual()
        if entrada < self.cfg["banca_minima"]:
            logger.debug("Entrada abaixo do mínimo — aguardando sinal...")
            time.sleep(self.cfg["loop_interval"])
            return

        # -------------------------------------------------------
        # PONTO DE INTEGRAÇÃO COM SEU SINAL
        # Substitua _aguardar_sinal() pela lógica do seu bot.
        # Deve retornar: ("call" ou "put") ou None se não há sinal.
        # -------------------------------------------------------
        sinal = self._aguardar_sinal()
        if sinal is None:
            time.sleep(self.cfg["loop_interval"])
            return

        # Atualiza payout real do ativo antes de entrar
        payout_real = self._obter_payout_real()
        if payout_real and abs(payout_real - self.manager.cfg["payout"]) > 0.01:
            logger.info(f"Payout atualizado: {payout_real*100:.1f}%")
            self.manager.alterar_payout(payout_real)
            entrada = self.manager.entrada_atual()  # recalcula com novo payout

        # Executa a operação
        win = self._executar_trade(sinal, entrada)
        if win is None:
            logger.warning("Resultado da operação indeterminado — aguardando...")
            return

        # Registra resultado no Masaniello
        status = self.manager.registrar_resultado(win)
        self._imprimir_resumo()

        # Verifica encerramento
        if status != StatusCiclo.ANDAMENTO:
            self._tratar_ciclo_encerrado(status)

    def _tratar_ciclo_encerrado(self, status: StatusCiclo):
        """Ação ao encerrar ciclo."""
        if status == StatusCiclo.META:
            logger.info("=" * 50)
            logger.info("🎉 META ATINGIDA! Ciclo encerrado com sucesso.")
            logger.info("=" * 50)
        elif status == StatusCiclo.QUEBRADO:
            logger.warning("=" * 50)
            logger.warning("🚫 Ciclo quebrado — impossível recuperar matematicamente.")
            logger.warning("=" * 50)
        elif status == StatusCiclo.FINALIZADO:
            logger.info("Ciclo finalizado normalmente.")

        self._imprimir_resumo()

        # Pergunta se deseja reiniciar (modo interativo)
        # Em produção, comente isso e gerencie externamente
        resp = input("\nIniciar novo ciclo? (s/n): ").strip().lower()
        if resp == 's':
            self.manager.reiniciar_ciclo()
            logger.info("Novo ciclo iniciado.")
        else:
            self.parar()

    # ----------------------------------------------------------
    # Execução de trade
    # ----------------------------------------------------------

    def _executar_trade(self, direcao: str, entrada: float):
        """
        Executa a operação na IQ Option e aguarda o resultado.

        Retorna:
            True  → WIN
            False → LOSS
            None  → erro / resultado indeterminado
        """
        asset    = self.cfg["asset"]
        duration = self.cfg["duration"]

        logger.info(
            f"🔵 ENTRANDO | Op#{self.manager.op_atual} | "
            f"{asset} | {direcao.upper()} | "
            f"R${entrada:.2f} | {duration}min"
        )

        # Verifica se o ativo está aberto
        if not self._ativo_disponivel(asset):
            logger.warning(f"Ativo {asset} não disponível no momento.")
            return None

        # Coloca a ordem
        order_id, status = self.iq.buy(entrada, asset, direcao, duration)
        if not status:
            logger.error(f"Falha ao colocar ordem: {order_id}")
            return None

        logger.info(f"Ordem enviada — ID: {order_id}. Aguardando resultado ({duration}min)...")

        # Aguarda o resultado (com timeout)
        timeout = (duration * 60) + 30  # tempo da operação + 30s de tolerância
        inicio  = time.time()

        while time.time() - inicio < timeout:
            time.sleep(3)
            resultado = self.iq.check_win_v3(order_id)
            if resultado is not None:
                lucro = round(float(resultado), 2)
                win   = lucro > 0
                logger.info(
                    f"{'✅ WIN' if win else '❌ LOSS'} | "
                    f"Resultado: {'+'if win else ''}{lucro:.2f}"
                )
                return win

        logger.warning("Timeout ao aguardar resultado da operação.")
        return None

    # ----------------------------------------------------------
    # Sinal — ADAPTE AQUI COM A LÓGICA DO SEU BOT
    # ----------------------------------------------------------

    def _aguardar_sinal(self):
        """
        === INTEGRAÇÃO COM SEU BOT ===

        Substitua este método pelo gerador de sinais do seu bot.
        Deve retornar:
            "call"  → entrada de alta
            "put"   → entrada de baixa
            None    → nenhum sinal neste momento

        Exemplos de fontes:
            - Leitura de arquivo/fila com sinais externos
            - Conexão com Telegram via pyTelegramBotAPI
            - Cálculo de indicadores via pandas_ta / talib
            - Webhook recebido de outro sistema

        -------------------------------------------------
        EXEMPLO STUB: entrada manual via terminal
        Remove em produção e integra seu sinal aqui.
        -------------------------------------------------
        """
        try:
            entrada_usuario = input(
                f"\n[Op#{self.manager.op_atual}] Sinal? "
                f"(c=call / p=put / s=skip / q=sair): "
            ).strip().lower()
        except EOFError:
            return None

        if entrada_usuario == 'c':
            return 'call'
        if entrada_usuario == 'p':
            return 'put'
        if entrada_usuario == 'q':
            self.parar()
            return None
        return None  # skip / outro

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _obter_payout_real(self) -> float | None:
        """Consulta o payout real do ativo na plataforma."""
        try:
            all_asset = self.iq.get_all_open_time()
            asset_info = (
                all_asset.get("binary", {}).get(self.cfg["asset"])
                or all_asset.get("turbo", {}).get(self.cfg["asset"])
            )
            if asset_info and asset_info.get("open"):
                # Payout varia por ativo/horário
                profit = self.iq.get_all_profit()
                p = profit.get("binary", {}).get(self.cfg["asset"], {}).get("1min")
                if p:
                    return round(float(p), 4)
        except Exception:
            pass
        return None

    def _ativo_disponivel(self, asset: str) -> bool:
        """Verifica se o ativo está aberto para negociação."""
        try:
            all_open = self.iq.get_all_open_time()
            for tipo in ("binary", "turbo"):
                info = all_open.get(tipo, {}).get(asset, {})
                if info.get("open"):
                    return True
        except Exception:
            pass
        return False

    def _imprimir_resumo(self):
        """Imprime resumo do estado atual no log."""
        r = self.manager.resumo()
        logger.info(
            f"📊 RESUMO | Saldo: R${r['saldo_atual']:.2f} | "
            f"Lucro: {'+'if r['lucro']>=0 else ''}{r['lucro']:.2f} | "
            f"ROI: {r['roi_pct']:.2f}% | "
            f"{r['wins']}W/{r['losses']}L ({r['taxa_acerto']:.1f}%) | "
            f"Próxima entrada: R${r['proxima_entrada']:.2f} | "
            f"Op {r['op_atual']}/{r['total_ops']}"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  MASANIELLO BOT — IQ Option (Python)")
    print("=" * 60)
    print(f"  Conta:      {CONFIG['account_type']}")
    print(f"  Banca:      R${CONFIG['banca_inicial']:.2f}")
    print(f"  Meta:       +R${CONFIG['meta_lucro']:.2f}")
    print(f"  Ciclo:      {CONFIG['total_ops']} ops / {CONFIG['min_wins']} acertos mín.")
    print(f"  Payout:     {CONFIG['payout']*100:.0f}%")
    print("=" * 60)

    if CONFIG["account_type"] == "REAL":
        confirmar = input("\n⚠️  CONTA REAL ATIVA. Deseja continuar? (sim/nao): ")
        if confirmar.strip().lower() != "sim":
            print("Abortado.")
            exit(0)

    bot = MasanielloBot(CONFIG)
    bot.iniciar()
