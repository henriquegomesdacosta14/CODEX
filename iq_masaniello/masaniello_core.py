"""
masaniello_core.py
==================
Núcleo do algoritmo Masaniello — sem dependência de IQ Option.
Pode ser importado por qualquer bot ou script.

Uso básico:
    from masaniello_core import MasanielloManager
    mgr = MasanielloManager(banca=1000, meta=100, total_ops=8, min_wins=5, payout=0.85)
    stake = mgr.entrada_atual()         # valor a apostar
    mgr.registrar_resultado(win=True)   # registra resultado
"""

import math
import json
import logging
from datetime import datetime
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class StatusCiclo(Enum):
    ANDAMENTO   = "andamento"
    META        = "meta_atingida"
    QUEBRADO    = "ciclo_quebrado"
    FINALIZADO  = "finalizado"


# ============================================================
# MATEMÁTICA
# ============================================================

def _log_comb(n: int, k: int) -> float:
    """
    Logaritmo do coeficiente binomial C(n,k).
    Usa soma de logaritmos para evitar overflow com n/k grandes.
    """
    if k < 0 or k > n:
        return float('-inf')
    if k == 0 or k == n:
        return 0.0
    k = min(k, n - k)  # simetria: C(n,k) = C(n,n-k)
    lc = 0.0
    for i in range(k):
        lc += math.log(n - i) - math.log(i + 1)
    return lc


def calcular_entrada(target: float, saldo: float, rem_ops: int,
                     rem_wins: int, payout: float) -> float:
    """
    Calcula a entrada Masaniello para o estado atual.

    Fórmula: entrada = (target - saldo) / (payout * C(rem_ops-1, rem_wins-1))

    Parâmetros:
        target   – saldo-alvo (banca_inicial + meta)
        saldo    – saldo atual
        rem_ops  – operações restantes (incluindo a atual)
        rem_wins – acertos ainda necessários
        payout   – fração de lucro (ex: 0.85 para 85%)

    Retorna:
        Valor da entrada, arredondado para 2 casas. 0 se impossível ou desnecessário.
    """
    if rem_wins <= 0:
        return 0.0  # meta já atingida
    if rem_wins > rem_ops:
        return 0.0  # matematicamente impossível
    numerador = target - saldo
    if numerador <= 0:
        return 0.0  # saldo já >= target
    log_den = math.log(payout) + _log_comb(rem_ops - 1, rem_wins - 1)
    denominador = math.exp(log_den)
    return round(max(0.0, numerador / denominador), 2)


# ============================================================
# MANAGER
# ============================================================

class MasanielloManager:
    """
    Gerencia um ciclo Masaniello completo.
    Persiste estado em arquivo JSON para sobreviver a reinicializações.
    """

    def __init__(
        self,
        banca: float,
        meta: float,
        total_ops: int,
        min_wins: int,
        payout: float,
        state_file: str = "masaniello_state.json"
    ):
        """
        Parâmetros:
            banca      – banca inicial do ciclo
            meta       – lucro desejado ao final do ciclo
            total_ops  – número total de operações (N)
            min_wins   – mínimo de acertos necessários (K ≤ N)
            payout     – fração de lucro por acerto (ex: 0.85)
            state_file – arquivo JSON para salvar estado
        """
        if min_wins > total_ops:
            raise ValueError("min_wins não pode ser maior que total_ops")
        if payout <= 0:
            raise ValueError("payout deve ser positivo")

        self.cfg = dict(
            banca=banca,
            meta=meta,
            total_ops=total_ops,
            min_wins=min_wins,
            payout=payout
        )
        self.state_file = Path(state_file)

        # Tenta carregar estado salvo; senão inicia novo ciclo
        if not self._carregar_estado():
            self._novo_ciclo()

    # ----------------------------------------------------------
    # API pública
    # ----------------------------------------------------------

    def entrada_atual(self) -> float:
        """Retorna o valor da entrada para a operação corrente."""
        if self.status != StatusCiclo.ANDAMENTO:
            return 0.0
        return calcular_entrada(
            target   = self._target(),
            saldo    = self.saldo,
            rem_ops  = self._rem_ops(),
            rem_wins = self._rem_wins(),
            payout   = self._payout_atual()
        )

    def registrar_resultado(self, win: bool) -> StatusCiclo:
        """
        Registra o resultado (win=True / win=False) da operação atual.
        Atualiza saldo, contadores e persiste o estado.

        Retorna o StatusCiclo atualizado.
        """
        if self.status != StatusCiclo.ANDAMENTO:
            logger.warning("Ciclo não está em andamento — resultado ignorado.")
            return self.status

        entrada = self.entrada_atual()
        op_num  = self.op_atual

        if win:
            lucro = round(entrada * self._payout_atual(), 2)
            self.saldo = round(self.saldo + lucro, 2)
            self.wins  += 1
            resultado = f"+R${lucro:.2f}"
        else:
            self.saldo  = round(self.saldo - entrada, 2)
            self.losses += 1
            resultado = f"-R${entrada:.2f}"

        # Registra na lista de operações
        self.historico_ops.append({
            "op":       op_num,
            "entrada":  entrada,
            "resultado": "win" if win else "loss",
            "saldo_pos": self.saldo,
            "rem_wins":  self._rem_wins(),
            "rem_ops":   self._rem_ops(),
            "ts":        datetime.now().isoformat()
        })

        self.op_atual += 1
        self._verificar_status()
        self._salvar_estado()

        logger.info(
            f"Op#{op_num} {'WIN' if win else 'LOSS'} | "
            f"Entrada: R${entrada:.2f} | {resultado} | "
            f"Saldo: R${self.saldo:.2f} | Status: {self.status.value}"
        )
        return self.status

    def alterar_payout(self, novo_payout: float):
        """Altera o payout para as próximas operações."""
        if novo_payout <= 0:
            raise ValueError("Payout inválido")
        self.cfg["payout"] = novo_payout
        logger.info(f"Payout alterado para {novo_payout*100:.1f}%")
        self._salvar_estado()

    def reiniciar_ciclo(self):
        """Reinicia o ciclo com os mesmos parâmetros."""
        self._novo_ciclo()
        self._salvar_estado()
        logger.info("Ciclo reiniciado.")

    def resumo(self) -> dict:
        """Retorna um resumo completo do estado atual."""
        lucro = round(self.saldo - self.cfg["banca"], 2)
        total = self.wins + self.losses
        return {
            "status":        self.status.value,
            "saldo_atual":   self.saldo,
            "banca_inicial": self.cfg["banca"],
            "lucro":         lucro,
            "roi_pct":       round(lucro / self.cfg["banca"] * 100, 2),
            "wins":          self.wins,
            "losses":        self.losses,
            "taxa_acerto":   round(self.wins / total * 100, 1) if total else 0,
            "op_atual":      self.op_atual,
            "total_ops":     self.cfg["total_ops"],
            "rem_ops":       self._rem_ops(),
            "rem_wins":      self._rem_wins(),
            "proxima_entrada": self.entrada_atual(),
            "meta":          self._target(),
            "payout_atual":  self.cfg["payout"]
        }

    # ----------------------------------------------------------
    # Internos
    # ----------------------------------------------------------

    def _target(self) -> float:
        return self.cfg["banca"] + self.cfg["meta"]

    def _rem_ops(self) -> int:
        """Operações restantes (incluindo a atual)."""
        return max(0, self.cfg["total_ops"] - self.op_atual + 1)

    def _rem_wins(self) -> int:
        """Acertos ainda necessários."""
        return max(0, self.cfg["min_wins"] - self.wins)

    def _payout_atual(self) -> float:
        return self.cfg["payout"]

    def _verificar_status(self):
        if self.saldo >= self._target():
            self.status = StatusCiclo.META
            logger.info("🎉 META ATINGIDA!")
        elif self._rem_wins() > self._rem_ops():
            self.status = StatusCiclo.QUEBRADO
            logger.warning("🚫 Ciclo matematicamente irrecuperável.")
        elif self.op_atual > self.cfg["total_ops"]:
            self.status = StatusCiclo.FINALIZADO
            logger.info("Ciclo finalizado — todas as operações concluídas.")

    def _novo_ciclo(self):
        self.saldo         = self.cfg["banca"]
        self.wins          = 0
        self.losses        = 0
        self.op_atual      = 1
        self.status        = StatusCiclo.ANDAMENTO
        self.historico_ops = []
        self.iniciado_em   = datetime.now().isoformat()

    def _salvar_estado(self):
        data = {
            "cfg":            self.cfg,
            "saldo":          self.saldo,
            "wins":           self.wins,
            "losses":         self.losses,
            "op_atual":       self.op_atual,
            "status":         self.status.value,
            "historico_ops":  self.historico_ops,
            "iniciado_em":    self.iniciado_em
        }
        try:
            self.state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")

    def _carregar_estado(self) -> bool:
        if not self.state_file.exists():
            return False
        try:
            data = json.loads(self.state_file.read_text())
            # Valida que a config salva é compatível com a atual
            if data.get("cfg") != self.cfg:
                logger.warning("Configuração alterada — iniciando novo ciclo.")
                return False
            self.saldo         = data["saldo"]
            self.wins          = data["wins"]
            self.losses        = data["losses"]
            self.op_atual      = data["op_atual"]
            self.status        = StatusCiclo(data["status"])
            self.historico_ops = data.get("historico_ops", [])
            self.iniciado_em   = data.get("iniciado_em", datetime.now().isoformat())
            logger.info(f"Estado restaurado — Op#{self.op_atual}, Saldo: R${self.saldo:.2f}")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
            return False
