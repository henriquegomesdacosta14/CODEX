<?php
// API do app Três Encontros. Recebe JSON por POST com o campo "acao".

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

function acao_publico()
{
    $config = te_config();
    te_responder(array(
        'chaveAvisos' => te_chaves_vapid()['publica'],
        'linkCompra' => isset($config['link_compra']) ? (string)$config['link_compra'] : '',
        'linkProximoMes' => isset($config['link_proximo_mes']) ? (string)$config['link_proximo_mes'] : '',
    ));
}

/** Entrega os textos: completos para quem tem código válido, só os 3 primeiros dias para a degustação. */
function acao_conteudo($e)
{
    $arquivo = __DIR__ . '/conteudo/mes-01.json';
    $conteudo = json_decode((string)file_get_contents($arquivo), true);
    if (!is_array($conteudo)) {
        te_erro('Conteúdo indisponível no servidor.', 500);
    }
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $codigos = $codigo !== '' ? te_ler('codigos') : array();
    $valido = $codigo !== '' && isset($codigos[$codigo]) && empty($codigos[$codigo]['bloqueado']);
    if (!$valido) {
        $conteudo['dias'] = array_slice($conteudo['dias'], 0, 3);
        $conteudo['proximoMes'] = array();
    }
    $conteudo['completo'] = $valido;
    te_responder(array('conteudo' => $conteudo));
}

/** Dados que o app recebe sobre a jornada. */
function perfil_publico($codigo, $r)
{
    return array(
        'codigo' => $codigo,
        'nome' => isset($r['nome']) ? $r['nome'] : '',
        'inicio' => isset($r['inicio']) ? $r['inicio'] : '',
        'horarios' => isset($r['horarios']) ? $r['horarios'] : null,
        'concluidos' => isset($r['concluidos']) ? array_values($r['concluidos']) : array(),
        'notas' => isset($r['notas']) ? (object)$r['notas'] : new stdClass(),
    );
}

function acao_entrar($e)
{
    te_limitar('entrar', 15, 600);
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $hoje = isset($e['hoje']) ? (string)$e['hoje'] : '';
    if ($codigo === '') {
        te_erro('Código inválido. Ele tem o formato TE-XXXX-XXXX.');
    }
    if (!te_data_valida($hoje)) {
        te_erro('A data do celular parece errada. Confira a data e tente de novo.');
    }
    $resultado = te_atualizar('codigos', function (&$codigos) use ($codigo, $hoje) {
        if (!isset($codigos[$codigo])) {
            return array('erro' => 'Não encontramos esse código. Confira as letras e os números.');
        }
        $r = &$codigos[$codigo];
        if (!empty($r['bloqueado'])) {
            return array('erro' => 'Este código foi desativado. Fale com quem enviou o seu acesso.');
        }
        if (empty($r['inicio'])) {
            $r['inicio'] = $hoje;
            $r['ativadoEm'] = date('c');
        }
        $r['ultimoAcesso'] = date('c');
        return array('perfil' => perfil_publico($codigo, $r));
    });
    if (isset($resultado['erro'])) {
        te_erro($resultado['erro'], 404);
    }
    te_responder($resultado);
}

function acao_salvar($e)
{
    te_limitar('salvar', 240, 600);
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    if ($codigo === '') {
        te_erro('Código inválido.');
    }
    $mudancas = array();
    if (isset($e['nome'])) {
        $mudancas['nome'] = mb_substr(trim(strip_tags((string)$e['nome'])), 0, 40);
    }
    if (isset($e['horarios']) && is_array($e['horarios'])) {
        $h = array();
        foreach (TE_MOMENTOS as $m) {
            if (!isset($e['horarios'][$m]) || !te_horario_valido($e['horarios'][$m])) {
                te_erro('Horário inválido.');
            }
            $h[$m] = $e['horarios'][$m];
        }
        $mudancas['horarios'] = $h;
    }
    if (isset($e['concluidos']) && is_array($e['concluidos'])) {
        $lista = array();
        foreach ($e['concluidos'] as $item) {
            if (is_string($item) && preg_match('/^([1-9]|[12]\d|30)-(manha|almoco|noite)$/', $item)) {
                $lista[$item] = true;
            }
        }
        $mudancas['concluidos'] = array_keys($lista);
    }
    $notas = null;
    if (isset($e['notas']) && is_array($e['notas'])) {
        $notas = array();
        foreach ($e['notas'] as $chave => $texto) {
            if (preg_match('/^([1-9]|[12]\d|30)-(manha|almoco|noite)$/', (string)$chave)) {
                $notas[$chave] = mb_substr((string)$texto, 0, 4000);
            }
        }
    }
    $ok = te_atualizar('codigos', function (&$codigos) use ($codigo, $mudancas, $notas) {
        if (!isset($codigos[$codigo]) || !empty($codigos[$codigo]['bloqueado'])) {
            return false;
        }
        $r = &$codigos[$codigo];
        foreach ($mudancas as $k => $v) {
            $r[$k] = $v;
        }
        if ($notas !== null) {
            $atuais = isset($r['notas']) ? $r['notas'] : array();
            foreach ($notas as $k => $v) {
                if ($v === '') {
                    unset($atuais[$k]);
                } else {
                    $atuais[$k] = $v;
                }
            }
            $r['notas'] = $atuais;
        }
        $r['atualizadoEm'] = date('c');
        return true;
    });
    if (!$ok) {
        te_erro('Código não encontrado.', 404);
    }
    te_responder();
}

function acao_inscrever_avisos($e)
{
    te_limitar('avisos', 30, 600);
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $endpoint = isset($e['endpoint']) ? (string)$e['endpoint'] : '';
    $fuso = isset($e['fuso']) ? (string)$e['fuso'] : 'America/Sao_Paulo';
    if ($codigo === '' || !preg_match('#^https://[^\s]+$#', $endpoint) || strlen($endpoint) > 1000) {
        te_erro('Inscrição de avisos inválida.');
    }
    if (!in_array($fuso, timezone_identifiers_list(), true)) {
        $fuso = 'America/Sao_Paulo';
    }
    $codigos = te_ler('codigos');
    if (!isset($codigos[$codigo])) {
        te_erro('Código não encontrado.', 404);
    }
    te_atualizar('avisos', function (&$avisos) use ($codigo, $endpoint, $fuso) {
        $id = hash('sha256', $endpoint);
        $atual = isset($avisos[$id]) ? $avisos[$id] : array('enviados' => array(), 'criadoEm' => date('c'));
        $atual['endpoint'] = $endpoint;
        $atual['codigo'] = $codigo;
        $atual['fuso'] = $fuso;
        $avisos[$id] = $atual;
    });
    te_responder();
}

function acao_cancelar_avisos($e)
{
    $endpoint = isset($e['endpoint']) ? (string)$e['endpoint'] : '';
    te_atualizar('avisos', function (&$avisos) use ($endpoint) {
        unset($avisos[hash('sha256', $endpoint)]);
    });
    te_responder();
}

/* ---------- Administração ---------- */

function exigir_admin($e)
{
    te_limitar('admin', 10, 600);
    $config = te_config();
    $senha = isset($config['admin_password']) ? (string)$config['admin_password'] : '';
    $enviada = isset($e['senha']) ? (string)$e['senha'] : '';
    if ($senha === '' || $senha === 'troque-esta-senha') {
        te_erro('Defina a senha do administrador em config.php antes de usar esta área.', 403);
    }
    if (!hash_equals($senha, $enviada)) {
        te_erro('Senha incorreta.', 403);
    }
}

function acao_admin_gerar($e)
{
    exigir_admin($e);
    $quantidade = max(1, min(200, (int)(isset($e['quantidade']) ? $e['quantidade'] : 1)));
    $obs = mb_substr(trim(strip_tags(isset($e['observacao']) ? (string)$e['observacao'] : '')), 0, 80);
    $novos = te_atualizar('codigos', function (&$codigos) use ($quantidade, $obs) {
        $novos = array();
        while (count($novos) < $quantidade) {
            $c = te_novo_codigo();
            if (isset($codigos[$c])) {
                continue;
            }
            $codigos[$c] = array('criadoEm' => date('c'), 'observacao' => $obs);
            $novos[] = $c;
        }
        return $novos;
    });
    te_responder(array('codigos' => $novos));
}

function acao_admin_listar($e)
{
    exigir_admin($e);
    $hoje = date('Y-m-d');
    $lista = array();
    foreach (te_ler('codigos') as $codigo => $r) {
        $dia = !empty($r['inicio']) ? te_dia_da_jornada($r['inicio'], $hoje) : 0;
        $lista[] = array(
            'codigo' => $codigo,
            'observacao' => isset($r['observacao']) ? $r['observacao'] : '',
            'nome' => isset($r['nome']) ? $r['nome'] : '',
            'criadoEm' => isset($r['criadoEm']) ? $r['criadoEm'] : '',
            'inicio' => isset($r['inicio']) ? $r['inicio'] : '',
            'dia' => $dia,
            'concluidos' => isset($r['concluidos']) ? count($r['concluidos']) : 0,
            'ultimoAcesso' => isset($r['ultimoAcesso']) ? $r['ultimoAcesso'] : '',
            'bloqueado' => !empty($r['bloqueado']),
        );
    }
    usort($lista, function ($a, $b) {
        return strcmp($b['criadoEm'], $a['criadoEm']);
    });
    $avisos = te_ler('avisos');
    te_responder(array('codigos' => $lista, 'celularesComAviso' => count($avisos)));
}

function acao_admin_bloquear($e)
{
    exigir_admin($e);
    $codigo = te_normalizar_codigo(isset($e['codigo']) ? $e['codigo'] : '');
    $bloquear = !empty($e['bloquear']);
    $ok = te_atualizar('codigos', function (&$codigos) use ($codigo, $bloquear) {
        if (!isset($codigos[$codigo])) {
            return false;
        }
        $codigos[$codigo]['bloqueado'] = $bloquear;
        return true;
    });
    if (!$ok) {
        te_erro('Código não encontrado.', 404);
    }
    te_responder();
}
