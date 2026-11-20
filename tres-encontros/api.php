<?php
// API do app Três Encontros. Recebe JSON por POST com o campo "acao".

require_once __DIR__ . '/lib/banco.php';
require_once __DIR__ . '/lib/avisos.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    te_erro('Use POST.', 405);
}

$entrada = json_decode((string)file_get_contents('php://input'), true);
if (!is_array($entrada)) {
    te_erro('Pedido inválido.');
}
$acao = isset($entrada['acao']) ? (string)$entrada['acao'] : '';

try {
    switch ($acao) {
        case 'publico':
            acao_publico();
        case 'conteudo':
            acao_conteudo($entrada);
        case 'entrar':
            acao_entrar($entrada);
        case 'salvar':
            acao_salvar($entrada);
        case 'inscrever_avisos':
            acao_inscrever_avisos($entrada);
        case 'cancelar_avisos':
            acao_cancelar_avisos($entrada);
        case 'admin_entrar':
            exigir_admin($entrada);
            te_responder();
        case 'admin_gerar':
            acao_admin_gerar($entrada);
        case 'admin_listar':
            acao_admin_listar($entrada);
        case 'admin_bloquear':
            acao_admin_bloquear($entrada);
        default:
            te_erro('Ação desconhecida.');
    }
} catch (PDOException $e) {
    error_log('Três Encontros: erro no banco: ' . $e->getMessage());
    te_erro('O servidor está ocupado. Tente de novo em instantes.', 503);
}

function acao_publico()
{
    $config = te_config();
    te_responder(array(
        'chaveAvisos' => te_chaves_vapid()['publica'],
        'linkCompra' => isset($config['link_compra']) ? (string)$config['link_compra'] : '',
        'linkProximoMes' => isset($config['link_proximo_mes']) ? (string)$config['link_proximo_mes'] : '',
    ));
}

/** Busca um código ativo; devolve a linha ou null. */
function codigo_valido($codigo)
{
    if ($codigo === '') {
        return null;
    }
    $r = te_sql('SELECT * FROM te_codigos WHERE codigo = ?', array($codigo))->fetch();
    return ($r && !(int)$r['bloqueado']) ? $r : null;
}

/** Entrega os textos: completos para quem tem código válido, só os 3 primeiros dias para a degustação. */
function acao_conteudo($e)
{
    $conteudo = json_decode((string)file_get_contents(__DIR__ . '/conteudo/mes-01.json'), true);
    if (!is_array($conteudo)) {
        te_erro('Conteúdo indisponível no servidor.', 500);
    }
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $valido = $codigo !== '' && codigo_valido($codigo) !== null;
    if (!$valido) {
        $conteudo['dias'] = array_slice($conteudo['dias'], 0, 3);
        $conteudo['proximoMes'] = array();
    }
    $conteudo['completo'] = $valido;
    te_responder(array('conteudo' => $conteudo));
}

function perfil_publico($r)
{
    $concluidos = te_sql('SELECT chave FROM te_concluidos WHERE codigo = ?', array($r['codigo']))->fetchAll(PDO::FETCH_COLUMN);
    $notas = array();
    foreach (te_sql('SELECT chave, texto FROM te_notas WHERE codigo = ?', array($r['codigo'])) as $n) {
        $notas[$n['chave']] = $n['texto'];
    }
    $horarios = null;
    if (!empty($r['horarios'])) {
        $p = explode(',', $r['horarios']);
        $horarios = array('manha' => $p[0], 'almoco' => $p[1], 'noite' => $p[2]);
    }
    return array(
        'codigo' => $r['codigo'],
        'nome' => (string)$r['nome'],
        'inicio' => (string)$r['inicio'],
        'horarios' => $horarios,
        'concluidos' => $concluidos,
        'notas' => (object)$notas,
    );
}

function acao_entrar($e)
{
    // Bloqueia quem erra muitos códigos seguidos (tentativa de adivinhar).
    if (te_tentativas('entrar', 600, false) >= 20) {
        te_erro('Muitas tentativas com código errado. Espere alguns minutos e tente de novo.', 429);
    }
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $hoje = isset($e['hoje']) ? (string)$e['hoje'] : '';
    if ($codigo === '') {
        te_erro('Código inválido. Ele tem o formato TE-XXXX-XXXX.');
    }
    if (!te_data_valida($hoje)) {
        te_erro('A data do celular parece errada. Confira a data e tente de novo.');
    }
    $r = te_sql('SELECT * FROM te_codigos WHERE codigo = ?', array($codigo))->fetch();
    if (!$r) {
        te_tentativas('entrar', 600, true);
        te_erro('Não encontramos esse código. Confira as letras e os números.', 404);
    }
    if ((int)$r['bloqueado']) {
        te_erro('Este código foi desativado. Fale com quem enviou o seu acesso.', 403);
    }
    $agora = te_agora_utc();
    if (empty($r['inicio'])) {
        // Só o primeiro acesso define o início (a condição evita corrida entre dois celulares).
        te_sql('UPDATE te_codigos SET inicio = ?, ativado_em = ? WHERE codigo = ? AND inicio IS NULL', array($hoje, $agora, $codigo));
    }
    te_sql('UPDATE te_codigos SET ultimo_acesso = ? WHERE codigo = ?', array($agora, $codigo));
    $r = te_sql('SELECT * FROM te_codigos WHERE codigo = ?', array($codigo))->fetch();
    te_responder(array('perfil' => perfil_publico($r)));
}

function acao_salvar($e)
{
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    if ($codigo === '' || codigo_valido($codigo) === null) {
        te_erro('Código não encontrado.', 404);
    }
    $sets = array();
    $params = array();
    if (isset($e['nome'])) {
        $sets[] = 'nome = ?';
        $params[] = mb_substr(trim(strip_tags((string)$e['nome'])), 0, 40);
    }
    if (isset($e['horarios']) && is_array($e['horarios'])) {
        $h = array();
        foreach (TE_MOMENTOS as $m) {
            if (!isset($e['horarios'][$m]) || !te_horario_valido($e['horarios'][$m])) {
                te_erro('Horário inválido.');
            }
            $h[] = $e['horarios'][$m];
        }
        $sets[] = 'horarios = ?';
        $params[] = implode(',', $h);
    }
    $padrao = '/^([1-9]|[12]\d|30)-(manha|almoco|noite)$/';
    $pdo = te_banco();
    $pdo->beginTransaction();
    $sets[] = 'atualizado_em = ?';
    $params[] = te_agora_utc();
    $params[] = $codigo;
    te_sql('UPDATE te_codigos SET ' . implode(', ', $sets) . ' WHERE codigo = ?', $params);

    if (isset($e['concluidos']) && is_array($e['concluidos'])) {
        $linhas = array();
        foreach (array_slice($e['concluidos'], 0, 90) as $item) {
            if (is_string($item) && preg_match($padrao, $item)) {
                $linhas[$item] = array($codigo, $item);
            }
        }
        te_inserir_ignorando('te_concluidos', array('codigo', 'chave'), array_values($linhas));
    }
    if (isset($e['notas']) && is_array($e['notas'])) {
        foreach (array_slice($e['notas'], 0, 90, true) as $chave => $texto) {
            if (!preg_match($padrao, (string)$chave)) {
                continue;
            }
            $texto = mb_substr((string)$texto, 0, 4000);
            if ($texto === '') {
                te_sql('DELETE FROM te_notas WHERE codigo = ? AND chave = ?', array($codigo, $chave));
            } else {
                te_gravar('te_notas', array('codigo' => $codigo, 'chave' => (string)$chave, 'texto' => $texto), array('codigo', 'chave'));
            }
        }
    }
    $pdo->commit();
    te_responder();
}

function acao_inscrever_avisos($e)
{
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $endpoint = isset($e['endpoint']) ? (string)$e['endpoint'] : '';
    $fuso = isset($e['fuso']) ? (string)$e['fuso'] : 'America/Sao_Paulo';
    if ($codigo === '' || !preg_match('#^https://\S+$#', $endpoint) || strlen($endpoint) > 1000) {
        te_erro('Inscrição de avisos inválida.');
    }
    if (!in_array($fuso, timezone_identifiers_list(), true)) {
        $fuso = 'America/Sao_Paulo';
    }
    if (codigo_valido($codigo) === null) {
        te_erro('Código não encontrado.', 404);
    }
    te_gravar('te_avisos', array(
        'id' => hash('sha256', $endpoint),
        'codigo' => $codigo,
        'endpoint' => $endpoint,
        'fuso' => $fuso,
        'criado_em' => te_agora_utc(),
    ), array('id'));
    te_responder();
}

function acao_cancelar_avisos($e)
{
    $endpoint = isset($e['endpoint']) ? (string)$e['endpoint'] : '';
    te_sql('DELETE FROM te_avisos WHERE id = ?', array(hash('sha256', $endpoint)));
    te_responder();
}

/* ---------- Administração ---------- */

function exigir_admin($e)
{
    if (te_tentativas('admin', 600, false) >= 10) {
        te_erro('Muitas tentativas de senha. Espere alguns minutos.', 429);
    }
    $config = te_config();
    $senha = isset($config['admin_password']) ? (string)$config['admin_password'] : '';
    $enviada = isset($e['senha']) ? (string)$e['senha'] : '';
    if ($senha === '' || $senha === 'troque-esta-senha') {
        te_erro('Defina a senha do administrador em config.php antes de usar esta área.', 403);
    }
    if (!hash_equals($senha, $enviada)) {
        te_tentativas('admin', 600, true);
        te_erro('Senha incorreta.', 403);
    }
}

function acao_admin_gerar($e)
{
    exigir_admin($e);
    $quantidade = max(1, min(500, (int)(isset($e['quantidade']) ? $e['quantidade'] : 1)));
    $obs = mb_substr(trim(strip_tags(isset($e['observacao']) ? (string)$e['observacao'] : '')), 0, 80);
    $novos = array();
    $agora = te_agora_utc();
    while (count($novos) < $quantidade) {
        $c = te_novo_codigo();
        $st = te_sql((te_mysql() ? 'INSERT IGNORE' : 'INSERT OR IGNORE') . ' INTO te_codigos (codigo, observacao, criado_em) VALUES (?, ?, ?)', array($c, $obs, $agora));
        if ($st->rowCount() === 1) {
            $novos[] = $c;
        }
    }
    te_responder(array('codigos' => $novos));
}

function acao_admin_listar($e)
{
    exigir_admin($e);
    $hoje = date('Y-m-d');
    $limite30 = date('Y-m-d', strtotime('-29 days'));
    $resumo = array(
        'total' => (int)te_sql('SELECT COUNT(*) FROM te_codigos')->fetchColumn(),
        'naoUsados' => (int)te_sql('SELECT COUNT(*) FROM te_codigos WHERE inicio IS NULL')->fetchColumn(),
        'emJornada' => (int)te_sql('SELECT COUNT(*) FROM te_codigos WHERE inicio >= ? AND inicio <= ?', array($limite30, $hoje))->fetchColumn(),
        'concluidos' => (int)te_sql('SELECT COUNT(*) FROM te_codigos WHERE inicio < ?', array($limite30))->fetchColumn(),
        'celularesComAviso' => (int)te_sql('SELECT COUNT(*) FROM te_avisos')->fetchColumn(),
    );
    $busca = trim(isset($e['busca']) ? (string)$e['busca'] : '');
    $sql = 'SELECT c.codigo, c.observacao, c.nome, c.criado_em, c.inicio, c.ultimo_acesso, c.bloqueado,
            (SELECT COUNT(*) FROM te_concluidos k WHERE k.codigo = c.codigo) AS concluidos
            FROM te_codigos c';
    $params = array();
    if ($busca !== '') {
        $sql .= ' WHERE c.codigo LIKE ? OR c.observacao LIKE ? OR c.nome LIKE ?';
        $like = '%' . str_replace(array('%', '_'), '', $busca) . '%';
        $params = array($like, $like, $like);
    }
    $sql .= ' ORDER BY c.criado_em DESC LIMIT 200';
    $lista = array();
    foreach (te_sql($sql, $params) as $r) {
        $lista[] = array(
            'codigo' => $r['codigo'],
            'observacao' => $r['observacao'],
            'nome' => $r['nome'],
            'criadoEm' => $r['criado_em'] ? gmdate('c', strtotime($r['criado_em'] . ' UTC')) : '',
            'inicio' => (string)$r['inicio'],
            'dia' => $r['inicio'] ? te_dia_da_jornada($r['inicio'], $hoje) : 0,
            'concluidos' => (int)$r['concluidos'],
            'ultimoAcesso' => $r['ultimo_acesso'] ? gmdate('c', strtotime($r['ultimo_acesso'] . ' UTC')) : '',
            'bloqueado' => (bool)(int)$r['bloqueado'],
        );
    }
    te_responder(array('codigos' => $lista, 'resumo' => $resumo));
}

function acao_admin_bloquear($e)
{
    exigir_admin($e);
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $st = te_sql('UPDATE te_codigos SET bloqueado = ? WHERE codigo = ?', array(!empty($e['bloquear']) ? 1 : 0, $codigo));
    if ($st->rowCount() === 0 && !te_sql('SELECT 1 FROM te_codigos WHERE codigo = ?', array($codigo))->fetch()) {
        te_erro('Código não encontrado.', 404);
    }
    te_responder();
}
