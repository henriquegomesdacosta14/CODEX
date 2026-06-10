/**
 * bot_iq_node.js
 * ==============
 * Bot Masaniello para IQ Option — Node.js
 * Integra gestão de banca Masaniello com opções binárias OTC na IQ Option.
 *
 * Dependências:
 *   npm install iq-option node-schedule chalk
 *
 * Uso:
 *   node bot_iq_node.js
 *
 * ATENÇÃO: Use conta PRACTICE para testar antes de operar com dinheiro real.
 */

'use strict';

const fs      = require('fs');
const path    = require('path');
const readline = require('readline');

// ============================================================
// CONFIGURAÇÃO — edite aqui
// ============================================================
const CONFIG = {
  // Credenciais IQ Option
  email:        'SEU_EMAIL@iqoption.com',
  password:     'SUA_SENHA',
  accountType:  'PRACTICE',  // 'PRACTICE' ou 'REAL'

  // Ativo e parâmetros de trade
  asset:        'EURUSD-OTC',
  duration:     1,            // duração em minutos

  // Masaniello
  bancaInicial:  1000.0,
  metaLucro:      100.0,
  totalOps:         8,
  minWins:          5,
  payout:          0.85,     // 85%

  // Mínimo de banca para entrar
  bancaMinima:   1.0,

  stateFile: 'masaniello_state.json',
  logFile:   'masaniello_bot.log'
};


// ============================================================
// LOGGING
// ============================================================
function log(level, msg) {
  const ts   = new Date().toLocaleString('pt-BR');
  const line = `[${ts}] [${level}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(CONFIG.logFile, line + '\n'); } catch (_) {}
}
const logger = {
  info:  m => log('INFO ', m),
  warn:  m => log('WARN ', m),
  error: m => log('ERROR', m),
  debug: m => log('DEBUG', m)
};


// ============================================================
// MATEMÁTICA MASANIELLO
// ============================================================

/** Logaritmo do coeficiente binomial C(n, k) — evita overflow. */
function logComb(n, k) {
  if (k < 0 || k > n) return -Infinity;
  if (k === 0 || k === n) return 0;
  k = Math.min(k, n - k);
  let lc = 0;
  for (let i = 0; i < k; i++) lc += Math.log(n - i) - Math.log(i + 1);
  return lc;
}

/**
 * Calcula a entrada Masaniello.
 *   entrada = (target - saldo) / (payout * C(remOps-1, remWins-1))
 */
function calcularEntrada(target, saldo, remOps, remWins, payout) {
  if (remWins <= 0 || remWins > remOps) return 0;
  const numerador = target - saldo;
  if (numerador <= 0) return 0;
  const logDen = Math.log(payout) + logComb(remOps - 1, remWins - 1);
  return Math.max(0, Math.round((numerador / Math.exp(logDen)) * 100) / 100);
}


// ============================================================
// GERENCIADOR DE ESTADO MASANIELLO
// ============================================================

const STATUS = {
  ANDAMENTO:  'andamento',
  META:       'meta_atingida',
  QUEBRADO:   'ciclo_quebrado',
  FINALIZADO: 'finalizado'
};

class MasanielloManager {
  constructor({ bancaInicial, metaLucro, totalOps, minWins, payout, stateFile }) {
    this.cfg = { bancaInicial, metaLucro, totalOps, minWins, payout };
    this.stateFile = stateFile || 'masaniello_state.json';

    if (!this._carregarEstado()) {
      this._novoCiclo();
    }
  }

  // ---- API pública ----------------------------------------

  /** Valor da entrada para a operação atual. */
  entradaAtual() {
    if (this.status !== STATUS.ANDAMENTO) return 0;
    return calcularEntrada(
      this._target(),
      this.saldo,
      this._remOps(),
      this._remWins(),
      this.cfg.payout
    );
  }

  /** Registra resultado (win: true/false). Retorna o novo status. */
  registrarResultado(win) {
    if (this.status !== STATUS.ANDAMENTO) {
      logger.warn('Ciclo não está em andamento — resultado ignorado.');
      return this.status;
    }

    const entrada = this.entradaAtual();
    const opNum   = this.opAtual;

    if (win) {
      const lucro = Math.round(entrada * this.cfg.payout * 100) / 100;
      this.saldo  = Math.round((this.saldo + lucro) * 100) / 100;
      this.wins++;
    } else {
      this.saldo  = Math.round((this.saldo - entrada) * 100) / 100;
      this.losses++;
    }

    this.historicoOps.push({
      op:        opNum,
      entrada,
      resultado: win ? 'win' : 'loss',
      saldoPos:  this.saldo,
      remWins:   this._remWins(),
      remOps:    this._remOps(),
      ts:        new Date().toISOString()
    });

    this.opAtual++;
    this._verificarStatus();
    this._salvarEstado();

    logger.info(
      `Op#${opNum} ${win ? 'WIN ✅' : 'LOSS ❌'} | ` +
      `Entrada: R$${entrada.toFixed(2)} | ` +
      `Saldo: R$${this.saldo.toFixed(2)} | Status: ${this.status}`
    );

    return this.status;
  }

  /** Altera o payout para as próximas operações. */
  alterarPayout(novoPayout) {
    this.cfg.payout = novoPayout;
    logger.info(`Payout alterado para ${(novoPayout * 100).toFixed(1)}%`);
    this._salvarEstado();
  }

  /** Reinicia o ciclo com os mesmos parâmetros. */
  reiniciarCiclo() {
    this._novoCiclo();
    this._salvarEstado();
    logger.info('Ciclo reiniciado.');
  }

  /** Resumo do estado atual. */
  resumo() {
    const lucro = Math.round((this.saldo - this.cfg.bancaInicial) * 100) / 100;
    const total = this.wins + this.losses;
    return {
      status:          this.status,
      saldoAtual:      this.saldo,
      bancaInicial:    this.cfg.bancaInicial,
      lucro,
      roiPct:          Math.round(lucro / this.cfg.bancaInicial * 10000) / 100,
      wins:            this.wins,
      losses:          this.losses,
      taxaAcerto:      total > 0 ? Math.round(this.wins / total * 1000) / 10 : 0,
      opAtual:         this.opAtual,
      totalOps:        this.cfg.totalOps,
      remOps:          this._remOps(),
      remWins:         this._remWins(),
      proximaEntrada:  this.entradaAtual(),
      meta:            this._target(),
      payoutAtual:     this.cfg.payout
    };
  }

  // ---- Internos -------------------------------------------

  _target()  { return this.cfg.bancaInicial + this.cfg.metaLucro; }
  _remOps()  { return Math.max(0, this.cfg.totalOps - this.opAtual + 1); }
  _remWins() { return Math.max(0, this.cfg.minWins - this.wins); }

  _verificarStatus() {
    if (this.saldo >= this._target()) {
      this.status = STATUS.META;
      logger.info('🎉 META ATINGIDA!');
    } else if (this._remWins() > this._remOps()) {
      this.status = STATUS.QUEBRADO;
      logger.warn('🚫 Ciclo matematicamente irrecuperável!');
    } else if (this.opAtual > this.cfg.totalOps) {
      this.status = STATUS.FINALIZADO;
      logger.info('Ciclo finalizado.');
    }
  }

  _novoCiclo() {
    this.saldo        = this.cfg.bancaInicial;
    this.wins         = 0;
    this.losses       = 0;
    this.opAtual      = 1;
    this.status       = STATUS.ANDAMENTO;
    this.historicoOps = [];
    this.iniciadoEm   = new Date().toISOString();
  }

  _salvarEstado() {
    const data = {
      cfg:           this.cfg,
      saldo:         this.saldo,
      wins:          this.wins,
      losses:        this.losses,
      opAtual:       this.opAtual,
      status:        this.status,
      historicoOps:  this.historicoOps,
      iniciadoEm:    this.iniciadoEm
    };
    try {
      fs.writeFileSync(this.stateFile, JSON.stringify(data, null, 2));
    } catch (e) {
      logger.error(`Erro ao salvar estado: ${e.message}`);
    }
  }

  _carregarEstado() {
    if (!fs.existsSync(this.stateFile)) return false;
    try {
      const data = JSON.parse(fs.readFileSync(this.stateFile, 'utf8'));
      // Verifica se a configuração é compatível
      if (JSON.stringify(data.cfg) !== JSON.stringify(this.cfg)) {
        logger.warn('Configuração alterada — iniciando novo ciclo.');
        return false;
      }
      this.saldo        = data.saldo;
      this.wins         = data.wins;
      this.losses       = data.losses;
      this.opAtual      = data.opAtual;
      this.status       = data.status;
      this.historicoOps = data.historicoOps || [];
      this.iniciadoEm   = data.iniciadoEm || new Date().toISOString();
      logger.info(`Estado restaurado — Op#${this.opAtual}, Saldo: R$${this.saldo.toFixed(2)}`);
      return true;
    } catch (e) {
      logger.error(`Erro ao carregar estado: ${e.message}`);
      return false;
    }
  }
}


// ============================================================
// BOT IQ OPTION
// ============================================================

class MasanielloBot {
  constructor(config) {
    this.cfg     = config;
    this.iq      = null;
    this.running = false;

    this.manager = new MasanielloManager({
      bancaInicial: config.bancaInicial,
      metaLucro:    config.metaLucro,
      totalOps:     config.totalOps,
      minWins:      config.minWins,
      payout:       config.payout,
      stateFile:    config.stateFile
    });
  }

  // ---- Conexão --------------------------------------------

  async conectar() {
    logger.info('Conectando à IQ Option...');
    try {
      // Importação dinâmica para compatibilidade
      const IQOption = require('iq-option');
      this.iq = new IQOption(this.cfg.email, this.cfg.password);

      await this.iq.connect();
      await this.iq.changeBalance(this.cfg.accountType);

      const profile = await this.iq.getProfile();
      logger.info(
        `Conectado! Conta: ${this.cfg.accountType} | ` +
        `Saldo IQ: R$${profile.balance.toFixed(2)}`
      );
      return true;
    } catch (err) {
      logger.error(`Falha na conexão: ${err.message}`);
      return false;
    }
  }

  async reconectar() {
    let espera = 5000;
    for (let i = 1; i <= 5; i++) {
      logger.warn(`Tentativa de reconexão ${i}/5 em ${espera / 1000}s...`);
      await sleep(espera);
      if (await this.conectar()) return true;
      espera = Math.min(espera * 2, 60000);
    }
    logger.error('Não foi possível reconectar.');
    return false;
  }

  // ---- Loop principal -------------------------------------

  async iniciar() {
    if (!(await this.conectar())) return;

    this.running = true;
    logger.info('Bot iniciado. Aguardando sinais...');
    this._imprimirResumo();

    while (this.running) {
      try {
        await this._ciclo();
      } catch (err) {
        if (err.message && err.message.includes('connection')) {
          logger.error('Conexão perdida.');
          if (!(await this.reconectar())) break;
        } else {
          logger.error(`Erro: ${err.message}`);
          await sleep(5000);
        }
      }
    }

    logger.info('Bot encerrado.');
  }

  parar() { this.running = false; }

  // ---- Ciclo ----------------------------------------------

  async _ciclo() {
    const status = this.manager.status;

    if (status !== STATUS.ANDAMENTO) {
      await this._tratarCicloEncerrado(status);
      return;
    }

    const entrada = this.manager.entradaAtual();
    if (entrada < this.cfg.bancaMinima) {
      await sleep(2000);
      return;
    }

    // -------------------------------------------------------
    // PONTO DE INTEGRAÇÃO COM SEU SINAL
    // Substitua _aguardarSinal() pela lógica do seu bot.
    // Deve retornar: 'call', 'put' ou null (sem sinal).
    // -------------------------------------------------------
    const sinal = await this._aguardarSinal();
    if (!sinal) {
      await sleep(2000);
      return;
    }

    // Atualiza payout real antes de entrar
    const payoutReal = await this._obterPayoutReal();
    if (payoutReal && Math.abs(payoutReal - this.manager.cfg.payout) > 0.01) {
      logger.info(`Payout real: ${(payoutReal * 100).toFixed(1)}%`);
      this.manager.alterarPayout(payoutReal);
    }

    // Executa o trade
    const win = await this._executarTrade(sinal, this.manager.entradaAtual());
    if (win === null) return; // resultado indeterminado

    const novoStatus = this.manager.registrarResultado(win);
    this._imprimirResumo();

    if (novoStatus !== STATUS.ANDAMENTO) {
      await this._tratarCicloEncerrado(novoStatus);
    }
  }

  async _tratarCicloEncerrado(status) {
    if (status === STATUS.META) {
      logger.info('='.repeat(50));
      logger.info('🎉 META ATINGIDA! Ciclo encerrado com sucesso.');
      logger.info('='.repeat(50));
    } else if (status === STATUS.QUEBRADO) {
      logger.warn('='.repeat(50));
      logger.warn('🚫 Ciclo quebrado — impossível recuperar matematicamente.');
      logger.warn('='.repeat(50));
    }

    this._imprimirResumo();

    const resp = await this._pergunta('\nIniciar novo ciclo? (s/n): ');
    if (resp.trim().toLowerCase() === 's') {
      this.manager.reiniciarCiclo();
      logger.info('Novo ciclo iniciado.');
    } else {
      this.parar();
    }
  }

  // ---- Execução de trade ----------------------------------

  async _executarTrade(direcao, entrada) {
    const { asset, duration } = this.cfg;

    logger.info(
      `🔵 ENTRANDO | Op#${this.manager.opAtual} | ` +
      `${asset} | ${direcao.toUpperCase()} | ` +
      `R$${entrada.toFixed(2)} | ${duration}min`
    );

    try {
      const result = await this.iq.buySimple(asset, direcao, entrada, duration);
      if (!result || !result.id) {
        logger.error('Falha ao colocar ordem.');
        return null;
      }

      logger.info(`Ordem enviada — ID: ${result.id}. Aguardando resultado...`);

      // Aguarda resultado com timeout
      const timeout = duration * 60 * 1000 + 30000;
      const win     = await this._aguardarResultado(result.id, timeout);

      if (win !== null) {
        logger.info(win ? '✅ WIN' : '❌ LOSS');
      } else {
        logger.warn('Timeout ao aguardar resultado.');
      }

      return win;
    } catch (err) {
      logger.error(`Erro ao executar trade: ${err.message}`);
      return null;
    }
  }

  async _aguardarResultado(orderId, timeout) {
    const inicio = Date.now();
    while (Date.now() - inicio < timeout) {
      await sleep(3000);
      try {
        const result = await this.iq.checkWin(orderId);
        if (result !== null && result !== undefined) {
          return parseFloat(result) > 0;
        }
      } catch (_) {}
    }
    return null;
  }

  // ---- Sinal — ADAPTE AQUI --------------------------------

  async _aguardarSinal() {
    /**
     * === INTEGRAÇÃO COM SEU BOT ===
     *
     * Substitua este método pela fonte de sinais do seu bot.
     * Retorne 'call', 'put' ou null.
     *
     * Exemplos:
     *   - Leitura de fila Redis/BullMQ
     *   - Webhook Express recebendo sinais
     *   - Bot Telegram com node-telegram-bot-api
     *   - Cálculo de indicadores com technicalindicators
     *
     * -----------------------------------------------
     * STUB: entrada manual via terminal (remova em produção)
     * -----------------------------------------------
     */
    const r = this.manager.resumo();
    const resp = await this._pergunta(
      `\n[Op#${r.opAtual}] Sinal? (c=call / p=put / s=skip / q=sair): `
    );
    const v = resp.trim().toLowerCase();
    if (v === 'c') return 'call';
    if (v === 'p') return 'put';
    if (v === 'q') { this.parar(); return null; }
    return null;
  }

  // ---- Helpers --------------------------------------------

  async _obterPayoutReal() {
    try {
      const instruments = await this.iq.getInstruments('binary-option');
      const inst = instruments.find(i => i.id === this.cfg.asset);
      if (inst && inst.payout) return inst.payout / 100;
    } catch (_) {}
    return null;
  }

  _imprimirResumo() {
    const r = this.manager.resumo();
    logger.info(
      `📊 RESUMO | Saldo: R$${r.saldoAtual.toFixed(2)} | ` +
      `Lucro: ${r.lucro >= 0 ? '+' : ''}${r.lucro.toFixed(2)} | ` +
      `ROI: ${r.roiPct.toFixed(2)}% | ` +
      `${r.wins}W/${r.losses}L (${r.taxaAcerto.toFixed(1)}%) | ` +
      `Próxima entrada: R$${r.proximaEntrada.toFixed(2)} | ` +
      `Op ${r.opAtual}/${r.totalOps}`
    );
  }

  _pergunta(prompt) {
    return new Promise(resolve => {
      const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
      rl.question(prompt, ans => { rl.close(); resolve(ans); });
    });
  }
}

// Utilitário
const sleep = ms => new Promise(r => setTimeout(r, ms));


// ============================================================
// ENTRY POINT
// ============================================================

(async () => {
  console.log('='.repeat(60));
  console.log('  MASANIELLO BOT — IQ Option (Node.js)');
  console.log('='.repeat(60));
  console.log(`  Conta:   ${CONFIG.accountType}`);
  console.log(`  Banca:   R$${CONFIG.bancaInicial.toFixed(2)}`);
  console.log(`  Meta:    +R$${CONFIG.metaLucro.toFixed(2)}`);
  console.log(`  Ciclo:   ${CONFIG.totalOps} ops / ${CONFIG.minWins} acertos mín.`);
  console.log(`  Payout:  ${(CONFIG.payout * 100).toFixed(0)}%`);
  console.log('='.repeat(60));

  if (CONFIG.accountType === 'REAL') {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const resp = await new Promise(r => rl.question('\n⚠️  CONTA REAL ATIVA. Continuar? (sim/nao): ', r));
    rl.close();
    if (resp.trim().toLowerCase() !== 'sim') { console.log('Abortado.'); process.exit(0); }
  }

  const bot = new MasanielloBot(CONFIG);

  // Encerramento limpo via Ctrl+C
  process.on('SIGINT', () => { bot.parar(); });

  await bot.iniciar();
})();
