<?php
// Funções compartilhadas pela API, pelo envio de avisos e pela área administrativa.

date_default_timezone_set('America/Sao_Paulo');

const TE_TOTAL_DIAS = 30;
const TE_MOMENTOS = array('manha', 'almoco', 'noite');
const TE_ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // sem 0/O e 1/I para não confundir

function te_config()
{
    static $config = null;
    if ($config !== null) {
        return $config;
    }
    $config = array();
    // A pasta usa a senha do site principal, se existir, e pode ter a própria config.php.
    foreach (array(__DIR__ . '/../../config.php', __DIR__ . '/../config.php') as $arquivo) {
        if (file_exists($arquivo)) {
            $lido = require $arquivo;
            if (is_array($lido)) {
                $config = array_merge($config, $lido);
            }
        }
    }
    return $config;
}

function te_pasta_dados()
{
    $config = te_config();
    $pasta = !empty($config['pasta_dados']) ? $config['pasta_dados'] : __DIR__ . '/../../../tres-encontros-dados';
    if (!is_dir($pasta) && !@mkdir($pasta, 0755, true)) {
        te_erro('Não foi possível criar a pasta de dados no servidor.', 500);
    }
    return $pasta;
}

function te_responder($dados = array(), $status = 200)
{
    http_response_code($status);
    echo json_encode(array_merge(array('ok' => $status < 400), $dados), JSON_UNESCAPED_UNICODE);
    exit;
}

function te_erro($mensagem, $status = 400)
{
    te_responder(array('erro' => $mensagem), $status);
}

/** Lê um arquivo JSON da pasta de dados. */
function te_ler($nome)
{
    $arquivo = te_pasta_dados() . '/' . $nome . '.json';
    if (!file_exists($arquivo)) {
        return array();
    }
    $dados = json_decode((string)file_get_contents($arquivo), true);
    return is_array($dados) ? $dados : array();
}

/** Abre o arquivo com trava, entrega os dados ao callback e grava o resultado. */
function te_atualizar($nome, $callback)
{
    $arquivo = te_pasta_dados() . '/' . $nome . '.json';
    $h = fopen($arquivo, 'c+');
    if (!$h || !flock($h, LOCK_EX)) {
        te_erro('Não foi possível abrir os dados no servidor.', 500);
    }
    $dados = json_decode((string)stream_get_contents($h), true);
    if (!is_array($dados)) {
        $dados = array();
    }
    $resultado = $callback($dados);
    rewind($h);
    ftruncate($h, 0);
    fwrite($h, json_encode($dados, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    fflush($h);
    flock($h, LOCK_UN);
    fclose($h);
    return $resultado;
}

function te_normalizar_codigo($codigo)
{
    $limpo = strtoupper(preg_replace('/[^A-Za-z0-9]/', '', (string)$codigo));
    if (strpos($limpo, 'TE') === 0 && strlen($limpo) === 10) {
        return 'TE-' . substr($limpo, 2, 4) . '-' . substr($limpo, 6, 4);
    }
    return '';
}

function te_novo_codigo()
{
    $parte = function () {
        $s = '';
        for ($i = 0; $i < 4; $i++) {
            $s .= TE_ALFABETO[random_int(0, strlen(TE_ALFABETO) - 1)];
        }
        return $s;
    };
    return 'TE-' . $parte() . '-' . $parte();
}

function te_horario_valido($h)
{
    return is_string($h) && preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', $h);
}

function te_data_valida($d)
{
    if (!is_string($d) || !preg_match('/^\d{4}-\d{2}-\d{2}$/', $d)) {
        return false;
    }
    list($a, $m, $dia) = array_map('intval', explode('-', $d));
    return checkdate($m, $dia, $a);
}

/** Dia da jornada (1 a 30) numa data local, a partir da data de início. */
function te_dia_da_jornada($inicio, $hoje)
{
    $a = new DateTime($inicio);
    $b = new DateTime($hoje);
    return (int)$a->diff($b)->format('%r%a') + 1;
}

function te_ip()
{
    return isset($_SERVER['REMOTE_ADDR']) ? (string)$_SERVER['REMOTE_ADDR'] : 'desconhecido';
}

/** Limita tentativas por IP para dificultar adivinhar códigos. */
function te_limitar($acao, $maximo, $janelaSegundos)
{
    $chave = $acao . '|' . hash('sha256', te_ip());
    $agora = time();
    $bloqueado = te_atualizar('tentativas', function (&$dados) use ($chave, $agora, $maximo, $janelaSegundos) {
        foreach ($dados as $k => $lista) {
            $dados[$k] = array_values(array_filter((array)$lista, function ($t) use ($agora, $janelaSegundos) {
                return $t > $agora - $janelaSegundos;
            }));
            if (!$dados[$k]) {
                unset($dados[$k]);
            }
        }
        $lista = isset($dados[$chave]) ? $dados[$chave] : array();
        if (count($lista) >= $maximo) {
            return true;
        }
        $lista[] = $agora;
        $dados[$chave] = $lista;
        return false;
    });
    if ($bloqueado) {
        te_erro('Muitas tentativas seguidas. Espere alguns minutos e tente de novo.', 429);
    }
}
