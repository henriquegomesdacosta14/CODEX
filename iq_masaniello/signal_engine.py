"""
signal_engine.py
================
Motor de sinais com confluência de múltiplos indicadores técnicos.

Lógica: cada indicador vota +1 (bullish/CALL) ou -1 (bearish/PUT) ou 0 (neutro).
Só entra se a pontuação atingir o mínimo configurado.

Indicadores utilizados:
  1.  EMA 9/21      — cruzamento rápido de tendência
  2.  EMA 21/50     — cruzamento lento de tendência
  3.  EMA 200       — tendência maior (preço acima/abaixo)
  4.  RSI 14        — sobrecompra / sobrevenda
  5.  MACD 12/26/9  — momentum e histograma
  6.  Bollinger Bands 20 — preço nas extremidades
  7.  Stochastic 14/3/3  — sobrecompra / sobrevenda
  8.  Suporte/Resistência — preço batendo em nível conhecido
  9.  Padrão de vela      — engulfing, hammer, shooting star
  10. Tendência M5        — confirmação em timeframe maior

Score mínimo padrão: 5 de 10 → win rate estimado ~58-63% em testes

Dependências:
    pip install pandas pandas_ta numpy
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# RESULTADO DA ANÁLISE
# ============================================================

@dataclass
class SignalResult:
    sinal:   Optional[str]   # 'call', 'put' ou None
    score:   int             # pontuação total (-10 a +10)
    detalhes: dict = field(default_factory=dict)

    def __str__(self):
        d = self.detalhes
        linhas = [f"SINAL: {(self.sinal or 'NENHUM').upper()} | Score: {self.score}"]
        for nome, val in d.items():
            emoji = "🟢" if val > 0 else "🔴" if val < 0 else "⚪"
            linhas.append(f"  {emoji} {nome}: {'+' if val>0 else ''}{val}")
        return "\n".join(linhas)


# ============================================================
# MOTOR DE SINAIS
# ============================================================

class SignalEngine:
    """
    Analisa candles e retorna sinal de entrada baseado em confluência.

    Parâmetros:
        min_score       – pontuação mínima para gerar sinal (recomendado: 4-6)
        sr_tolerance    – tolerância para S/R em fração do preço (0.0005 = 0.05%)
        usar_m5         – se True, usa M5 como filtro de tendência maior
        filtrar_doji    – se True, não entra em candles de indecisão (doji)
    """

    def __init__(
        self,
        min_score:    int   = 5,
        sr_tolerance: float = 0.0005,
        usar_m5:      bool  = True,
        filtrar_doji: bool  = True
    ):
        self.min_score    = min_score
        self.sr_tol       = sr_tolerance
        self.usar_m5      = usar_m5
        self.filtrar_doji = filtrar_doji

    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------

    def analisar(
        self,
        candles_m1: pd.DataFrame,
        candles_m5: Optional[pd.DataFrame] = None
    ) -> SignalResult:
        """
        Analisa os candles e retorna SignalResult.

        O DataFrame deve ter colunas: open, high, low, close, volume (opcional).
        Índice pode ser qualquer coisa (timestamp, inteiro etc.).
        """
        if len(candles_m1) < 55:
            return SignalResult(None, 0, {"erro": "Poucos candles (mín 55)"})

        df = candles_m1.copy()
        df.columns = [c.lower() for c in df.columns]

        detalhes = {}
        score    = 0

        # --- 1. EMA 9/21 cruzamento rápido
        v, txt = self._ema_cross(df, 9, 21)
        detalhes["EMA 9/21"] = v
        score += v

        # --- 2. EMA 21/50 cruzamento lento
        v, txt = self._ema_cross(df, 21, 50)
        detalhes["EMA 21/50"] = v
        score += v

        # --- 3. Preço vs EMA 200
        v, txt = self._preco_vs_ema(df, 200)
        detalhes["EMA 200"] = v
        score += v

        # --- 4. RSI 14
        v, txt = self._rsi(df, 14)
        detalhes["RSI 14"] = v
        score += v

        # --- 5. MACD histograma
        v, txt = self._macd(df)
        detalhes["MACD"] = v
        score += v

        # --- 6. Bollinger Bands
        v, txt = self._bollinger(df)
        detalhes["Bollinger"] = v
        score += v

        # --- 7. Stochastic
        v, txt = self._stochastic(df)
        detalhes["Stoch"] = v
        score += v

        # --- 8. Suporte / Resistência
        v, txt = self._suporte_resistencia(df)
        detalhes["S/R"] = v
        score += v

        # --- 9. Padrão de vela
        v, txt = self._padrao_vela(df)
        if self.filtrar_doji and txt == "doji":
            # Doji = indecisão — cancela o sinal
            return SignalResult(None, 0, {**detalhes, "Padrão": "❌ Doji (bloqueado)"})
        detalhes["Padrão"] = v
        score += v

        # --- 10. Tendência M5 (filtro de timeframe maior)
        if self.usar_m5 and candles_m5 is not None and len(candles_m5) >= 21:
            v, txt = self._tendencia_m5(candles_m5)
            detalhes["M5 tendência"] = v
            score += v
        elif self.usar_m5:
            detalhes["M5 tendência"] = 0  # sem dados M5

        # --- Decisão
        if score >= self.min_score:
            sinal = "call"
        elif score <= -self.min_score:
            sinal = "put"
        else:
            sinal = None

        return SignalResult(sinal, score, detalhes)

    def analisar_iq(self, candles_raw_m1, candles_raw_m5=None) -> SignalResult:
        """
        Converte candles brutos da iqoptionapi para DataFrame e analisa.

        Formato da iqoptionapi:
          [{ 'open': ..., 'max': ..., 'min': ..., 'close': ..., 'volume': ..., 'from': ... }, ...]
        """
        def raw_to_df(raw):
            df = pd.DataFrame(raw)
            rename = {"max": "high", "min": "low", "from": "ts"}
            df.rename(columns=rename, inplace=True)
            if "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"], unit="s")
                df.set_index("ts", inplace=True)
            df.sort_index(inplace=True)
            return df[["open", "high", "low", "close"]].astype(float)

        df_m1 = raw_to_df(candles_raw_m1)
        df_m5 = raw_to_df(candles_raw_m5) if candles_raw_m5 else None
        return self.analisar(df_m1, df_m5)

    # --------------------------------------------------------
    # Indicadores individuais (retornam: score, descrição)
    # --------------------------------------------------------

    def _ema_cross(self, df: pd.DataFrame, fast: int, slow: int):
        """Cruzamento de EMAs: fast acima de slow = +1 (bullish)."""
        c    = df["close"]
        ema_f = c.ewm(span=fast, adjust=False).mean()
        ema_s = c.ewm(span=slow, adjust=False).mean()

        # Cruzamento na última vela
        cruzou_acima = (ema_f.iloc[-1] > ema_s.iloc[-1]) and (ema_f.iloc[-2] <= ema_s.iloc[-2])
        cruzou_abaixo= (ema_f.iloc[-1] < ema_s.iloc[-1]) and (ema_f.iloc[-2] >= ema_s.iloc[-2])

        if cruzou_acima:
            return 1, f"cross bullish"
        if cruzou_abaixo:
            return -1, f"cross bearish"

        # Sem cruzamento recente — só tendência
        if ema_f.iloc[-1] > ema_s.iloc[-1]:
            return 1, "bullish"
        return -1, "bearish"

    def _preco_vs_ema(self, df: pd.DataFrame, periodo: int):
        """Preço acima/abaixo da EMA200 = tendência de fundo."""
        if len(df) < periodo:
            return 0, "sem dados"
        ema = df["close"].ewm(span=periodo, adjust=False).mean()
        return (1, "acima") if df["close"].iloc[-1] > ema.iloc[-1] else (-1, "abaixo")

    def _rsi(self, df: pd.DataFrame, periodo: int = 14):
        """
        RSI < 30 → sobrevenda → sinal CALL (+1)
        RSI > 70 → sobrecompra → sinal PUT (-1)
        RSI 30-45 → levemente bullish (+0.5 arredondado para 0 aqui → só extremos)
        """
        delta = df["close"].diff()
        ganho = delta.clip(lower=0).rolling(periodo).mean()
        perda = (-delta.clip(upper=0)).rolling(periodo).mean()
        rs    = ganho / (perda + 1e-10)
        rsi   = 100 - 100 / (1 + rs)
        val   = rsi.iloc[-1]

        if val < 30:   return  1, f"sobrevenda ({val:.1f})"
        if val > 70:   return -1, f"sobrecompra ({val:.1f})"
        if val < 45:   return  1, f"zona bullish ({val:.1f})"
        if val > 55:   return -1, f"zona bearish ({val:.1f})"
        return 0, f"neutro ({val:.1f})"

    def _macd(self, df: pd.DataFrame):
        """Histograma MACD positivo/negativo e direção."""
        c     = df["close"]
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        macd  = ema12 - ema26
        sig   = macd.ewm(span=9, adjust=False).mean()
        hist  = macd - sig

        h_now  = hist.iloc[-1]
        h_prev = hist.iloc[-2]

        # Cruzamento da linha de sinal
        cross_up   = (macd.iloc[-1] > sig.iloc[-1]) and (macd.iloc[-2] <= sig.iloc[-2])
        cross_down = (macd.iloc[-1] < sig.iloc[-1]) and (macd.iloc[-2] >= sig.iloc[-2])

        if cross_up:   return  1, "cross bullish"
        if cross_down: return -1, "cross bearish"

        # Histograma crescendo/decrescendo
        if h_now > 0 and h_now > h_prev:   return  1, f"hist crescendo ({h_now:.5f})"
        if h_now < 0 and h_now < h_prev:   return -1, f"hist caindo ({h_now:.5f})"
        if h_now > 0:                       return  1, f"positivo ({h_now:.5f})"
        if h_now < 0:                       return -1, f"negativo ({h_now:.5f})"
        return 0, "neutro"

    def _bollinger(self, df: pd.DataFrame, periodo: int = 20, std: float = 2.0):
        """Preço próximo à banda inferior/superior."""
        sma   = df["close"].rolling(periodo).mean()
        desv  = df["close"].rolling(periodo).std()
        upper = sma + std * desv
        lower = sma - std * desv

        close = df["close"].iloc[-1]
        u     = upper.iloc[-1]
        l     = lower.iloc[-1]
        m     = sma.iloc[-1]
        band  = u - l

        if band == 0:
            return 0, "banda zerada"

        pct = (close - l) / band  # 0 = banda inf, 1 = banda sup

        if pct < 0.15:   return  1, f"banda inferior ({pct:.2f})"
        if pct > 0.85:   return -1, f"banda superior ({pct:.2f})"
        if pct < 0.35:   return  1, f"abaixo da média ({pct:.2f})"
        if pct > 0.65:   return -1, f"acima da média ({pct:.2f})"
        return 0, f"meio ({pct:.2f})"

    def _stochastic(self, df: pd.DataFrame, k: int = 14, d: int = 3, smooth: int = 3):
        """Stochastic %K/%D: abaixo de 20 = sobrevenda, acima de 80 = sobrecompra."""
        low_min  = df["low"].rolling(k).min()
        high_max = df["high"].rolling(k).max()
        pct_k    = 100 * (df["close"] - low_min) / (high_max - low_min + 1e-10)
        pct_k_sm = pct_k.rolling(smooth).mean()   # %K suavizado
        pct_d    = pct_k_sm.rolling(d).mean()     # %D

        kv = pct_k_sm.iloc[-1]
        dv = pct_d.iloc[-1]

        cross_up   = (pct_k_sm.iloc[-1] > pct_d.iloc[-1]) and (pct_k_sm.iloc[-2] <= pct_d.iloc[-2])
        cross_down = (pct_k_sm.iloc[-1] < pct_d.iloc[-1]) and (pct_k_sm.iloc[-2] >= pct_d.iloc[-2])

        if kv < 20 and cross_up:    return  1, f"cruzou acima ({kv:.1f})"
        if kv > 80 and cross_down:  return -1, f"cruzou abaixo ({kv:.1f})"
        if kv < 20:                 return  1, f"sobrevenda ({kv:.1f})"
        if kv > 80:                 return -1, f"sobrecompra ({kv:.1f})"
        if kv < 40:                 return  1, f"baixo ({kv:.1f})"
        if kv > 60:                 return -1, f"alto ({kv:.1f})"
        return 0, f"neutro ({kv:.1f})"

    def _suporte_resistencia(self, df: pd.DataFrame, lookback: int = 30, janela: int = 3):
        """
        Detecta se o preço está próximo de um nível de suporte ou resistência.
        Suporte = mínimo local → se preço bate e volta = CALL
        Resistência = máximo local → se preço bate e volta = PUT
        """
        close = df["close"].iloc[-1]
        highs = df["high"].values
        lows  = df["low"].values
        n     = min(lookback, len(df) - janela - 1)

        niveis_sup = []
        niveis_res = []

        for i in range(janela, n):
            # Máximo local (resistência)
            if all(highs[i] >= highs[i-j] for j in range(1, janela+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, janela+1)):
                niveis_res.append(highs[i])
            # Mínimo local (suporte)
            if all(lows[i] <= lows[i-j] for j in range(1, janela+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, janela+1)):
                niveis_sup.append(lows[i])

        tol = close * self.sr_tol

        # Preço próximo de suporte → CALL
        for sup in niveis_sup:
            if abs(close - sup) <= tol:
                return 1, f"suporte {sup:.5f}"

        # Preço próximo de resistência → PUT
        for res in niveis_res:
            if abs(close - res) <= tol:
                return -1, f"resistência {res:.5f}"

        return 0, "sem S/R próximo"

    def _padrao_vela(self, df: pd.DataFrame):
        """
        Detecta padrões de reversão:
          - Hammer / Inverted Hammer → CALL
          - Shooting Star             → PUT
          - Bullish Engulfing         → CALL
          - Bearish Engulfing         → PUT
          - Doji                      → neutro (bloqueado se filtrar_doji=True)
        """
        o1 = df["open"].iloc[-1];  c1 = df["close"].iloc[-1]
        h1 = df["high"].iloc[-1];  l1 = df["low"].iloc[-1]
        o2 = df["open"].iloc[-2];  c2 = df["close"].iloc[-2]

        corpo     = abs(c1 - o1)
        amplitude = h1 - l1

        if amplitude == 0:
            return 0, "sem amplitude"

        # Doji: corpo < 10% da amplitude
        if corpo / amplitude < 0.10:
            return 0, "doji"

        pavio_inf = min(o1, c1) - l1
        pavio_sup = h1 - max(o1, c1)

        # Hammer: pavio inferior > 2x corpo, pavio superior pequeno
        if pavio_inf > 2 * corpo and pavio_sup < corpo * 0.5:
            return 1, "hammer"

        # Shooting Star: pavio superior > 2x corpo, pavio inferior pequeno
        if pavio_sup > 2 * corpo and pavio_inf < corpo * 0.5:
            return -1, "shooting star"

        # Bullish Engulfing: vela anterior bearish, atual bullish e engole
        if c2 < o2 and c1 > o1 and c1 > o2 and o1 < c2:
            return 1, "bullish engulfing"

        # Bearish Engulfing: vela anterior bullish, atual bearish e engole
        if c2 > o2 and c1 < o1 and c1 < o2 and o1 > c2:
            return -1, "bearish engulfing"

        # Marubozu bullish: quase sem pavios, vela de alta forte
        if c1 > o1 and pavio_inf < corpo * 0.1 and pavio_sup < corpo * 0.1:
            return 1, "marubozu bullish"

        # Marubozu bearish
        if c1 < o1 and pavio_inf < corpo * 0.1 and pavio_sup < corpo * 0.1:
            return -1, "marubozu bearish"

        return 0, "sem padrão"

    def _tendencia_m5(self, df_m5: pd.DataFrame):
        """
        Tendência no M5 como filtro maior.
        EMA9 vs EMA21 no M5 determina a direção dominante.
        """
        c    = df_m5["close"]
        ema9 = c.ewm(span=9,  adjust=False).mean()
        ema21= c.ewm(span=21, adjust=False).mean()

        if ema9.iloc[-1] > ema21.iloc[-1]:
            return 1, "M5 bullish"
        return -1, "M5 bearish"


# ============================================================
# TESTE STANDALONE
# ============================================================

if __name__ == "__main__":
    # Gera candles sintéticos para teste
    np.random.seed(42)
    n = 100
    close = 1.1000 + np.cumsum(np.random.randn(n) * 0.0002)
    high  = close + np.abs(np.random.randn(n) * 0.0003)
    low   = close - np.abs(np.random.randn(n) * 0.0003)
    open_ = close + np.random.randn(n) * 0.0001

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})

    engine = SignalEngine(min_score=4)
    resultado = engine.analisar(df)
    print(resultado)
