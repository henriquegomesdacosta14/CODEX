<?php
// Banco de dados do app.
// Na Hostinger, use MySQL (configurado em config.php, chave "banco"): aguenta dezenas de milhares de pessoas.
// Sem configuração, usa um arquivo SQLite na pasta de dados: bom para testar e para os primeiros mil usuários.

require_once __DIR__ . '/base.php';

const TE_VERSAO_BANCO = 1;

function te_banco()
{
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }
    $config = te_config();
    try {
        if (!empty($config['banco']['dsn'])) {
            $b = $config['banco'];
            $pdo = new PDO($b['dsn'], isset($b['usuario']) ? $b['usuario'] : null, isset($b['senha']) ? $b['senha'] : null, array(
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ));
            $pdo->exec("SET time_zone = '+00:00'");
        } else {
            $pdo = new PDO('sqlite:' . te_pasta_dados() . '/tres-encontros.sqlite', null, null, array(
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            ));
            $pdo->exec('PRAGMA journal_mode = WAL');
            $pdo->exec('PRAGMA busy_timeout = 5000');
            $pdo->exec('PRAGMA synchronous = NORMAL');
        }
    } catch (PDOException $e) {
        error_log('Três Encontros: falha ao conectar no banco: ' . $e->getMessage());
        te_erro('O servidor está sem acesso ao banco de dados. Tente de novo em alguns minutos.', 503);
    }
    te_criar_tabelas($pdo);
    return $pdo;
}

function te_mysql()
{
    return te_banco()->getAttribute(PDO::ATTR_DRIVER_NAME) === 'mysql';
}

/** Cria as tabelas uma única vez (a versão fica gravada num arquivo da pasta de dados). */
function te_criar_tabelas($pdo)
{
    $marca = te_pasta_dados() . '/banco-versao-' . $pdo->getAttribute(PDO::ATTR_DRIVER_NAME) . '.txt';
    if (file_exists($marca) && (int)file_get_contents($marca) >= TE_VERSAO_BANCO) {
        return;
    }
    if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'mysql') {
        $f = ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';
        $sql = array(
            "CREATE TABLE IF NOT EXISTS te_codigos (
                codigo VARCHAR(14) NOT NULL PRIMARY KEY,
                observacao VARCHAR(80) NOT NULL DEFAULT '',
                criado_em DATETIME NOT NULL,
                bloqueado TINYINT NOT NULL DEFAULT 0,
                inicio DATE NULL,
                ativado_em DATETIME NULL,
                ultimo_acesso DATETIME NULL,
                atualizado_em DATETIME NULL,
                nome VARCHAR(40) NOT NULL DEFAULT '',
                horarios VARCHAR(20) NULL,
                INDEX idx_criado (criado_em),
                INDEX idx_inicio (inicio)
            )$f",
            "CREATE TABLE IF NOT EXISTS te_concluidos (
                codigo VARCHAR(14) NOT NULL,
                chave VARCHAR(10) NOT NULL,
                PRIMARY KEY (codigo, chave)
            )$f",
            "CREATE TABLE IF NOT EXISTS te_notas (
                codigo VARCHAR(14) NOT NULL,
                chave VARCHAR(10) NOT NULL,
                texto TEXT NOT NULL,
                PRIMARY KEY (codigo, chave)
            )$f",
            "CREATE TABLE IF NOT EXISTS te_avisos (
                id CHAR(64) NOT NULL PRIMARY KEY,
                codigo VARCHAR(14) NOT NULL,
                endpoint TEXT NOT NULL,
                fuso VARCHAR(64) NOT NULL,
                criado_em DATETIME NOT NULL,
                enviado_manha DATE NULL,
                enviado_almoco DATE NULL,
                enviado_noite DATE NULL,
                INDEX idx_codigo (codigo)
            )$f",
            "CREATE TABLE IF NOT EXISTS te_tentativas (
                chave CHAR(64) NOT NULL,
                momento INT NOT NULL,
                INDEX idx_chave (chave, momento),
                INDEX idx_momento (momento)
            )$f",
        );
    } else {
        $sql = array(
            "CREATE TABLE IF NOT EXISTS te_codigos (
                codigo TEXT NOT NULL PRIMARY KEY, observacao TEXT NOT NULL DEFAULT '', criado_em TEXT NOT NULL,
                bloqueado INTEGER NOT NULL DEFAULT 0, inicio TEXT, ativado_em TEXT, ultimo_acesso TEXT, atualizado_em TEXT,
                nome TEXT NOT NULL DEFAULT '', horarios TEXT)",
            'CREATE INDEX IF NOT EXISTS idx_criado ON te_codigos (criado_em)',
            'CREATE INDEX IF NOT EXISTS idx_inicio ON te_codigos (inicio)',
            'CREATE TABLE IF NOT EXISTS te_concluidos (codigo TEXT NOT NULL, chave TEXT NOT NULL, PRIMARY KEY (codigo, chave))',
            'CREATE TABLE IF NOT EXISTS te_notas (codigo TEXT NOT NULL, chave TEXT NOT NULL, texto TEXT NOT NULL, PRIMARY KEY (codigo, chave))',
            'CREATE TABLE IF NOT EXISTS te_avisos (id TEXT NOT NULL PRIMARY KEY, codigo TEXT NOT NULL, endpoint TEXT NOT NULL, fuso TEXT NOT NULL,
                criado_em TEXT NOT NULL, enviado_manha TEXT, enviado_almoco TEXT, enviado_noite TEXT)',
            'CREATE INDEX IF NOT EXISTS idx_avisos_codigo ON te_avisos (codigo)',
            'CREATE TABLE IF NOT EXISTS te_tentativas (chave TEXT NOT NULL, momento INTEGER NOT NULL)',
            'CREATE INDEX IF NOT EXISTS idx_tent ON te_tentativas (chave, momento)',
        );
    }
    foreach ($sql as $comando) {
        $pdo->exec($comando);
    }
    @file_put_contents($marca, (string)TE_VERSAO_BANCO);
}

/** Data e hora atuais em UTC no formato do banco. */
function te_agora_utc()
{
    return gmdate('Y-m-d H:i:s');
}

/** Executa um comando preparado e devolve o statement. */
function te_sql($sql, $params = array())
{
    $st = te_banco()->prepare($sql);
    $st->execute($params);
    return $st;
}

/** Insere ignorando duplicados (funciona em MySQL e SQLite). */
function te_inserir_ignorando($tabela, $colunas, $linhas)
{
    if (!$linhas) {
        return;
    }
    $grupo = '(' . implode(',', array_fill(0, count($colunas), '?')) . ')';
    $verbo = te_mysql() ? 'INSERT IGNORE INTO' : 'INSERT OR IGNORE INTO';
    foreach (array_chunk($linhas, 200) as $lote) {
        $params = array();
        foreach ($lote as $l) {
            foreach ($l as $v) {
                $params[] = $v;
            }
        }
        te_sql("$verbo $tabela (" . implode(',', $colunas) . ') VALUES ' . implode(',', array_fill(0, count($lote), $grupo)), $params);
    }
}

/** Insere ou atualiza pela chave primária. */
function te_gravar($tabela, $dados, $chaves)
{
    $colunas = array_keys($dados);
    $marcas = implode(',', array_fill(0, count($colunas), '?'));
    $atualizar = array_values(array_diff($colunas, $chaves));
    if (te_mysql()) {
        $set = implode(',', array_map(function ($c) { return "$c = VALUES($c)"; }, $atualizar));
        $sql = "INSERT INTO $tabela (" . implode(',', $colunas) . ") VALUES ($marcas) ON DUPLICATE KEY UPDATE $set";
    } else {
        $set = implode(',', array_map(function ($c) { return "$c = excluded.$c"; }, $atualizar));
        $sql = "INSERT INTO $tabela (" . implode(',', $colunas) . ") VALUES ($marcas) ON CONFLICT(" . implode(',', $chaves) . ") DO UPDATE SET $set";
    }
    te_sql($sql, array_values($dados));
}

/**
 * Conta tentativas por IP para dificultar adivinhar códigos.
 * $registrar = false só consulta; true grava uma tentativa.
 */
function te_tentativas($acao, $janelaSegundos, $registrar)
{
    $chave = hash('sha256', $acao . '|' . te_ip());
    $agora = time();
    if ($registrar) {
        te_sql('INSERT INTO te_tentativas (chave, momento) VALUES (?, ?)', array($chave, $agora));
        if (random_int(1, 50) === 1) {
            te_sql('DELETE FROM te_tentativas WHERE momento < ?', array($agora - 86400));
        }
        return 0;
    }
    return (int)te_sql('SELECT COUNT(*) FROM te_tentativas WHERE chave = ? AND momento > ?', array($chave, $agora - $janelaSegundos))->fetchColumn();
}
