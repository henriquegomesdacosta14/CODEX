<?php
// Envia os avisos dos encontros. Rode a cada 5 minutos pelo agendador (cron) da Hostinger:
//   /usr/bin/php /home/SEU_USUARIO/public_html/tres-encontros/avisos-cron.php
// Também aceita chamada pela web com ?chave=... (defina "chave_cron" na config.php).
//
// Os avisos saem em paralelo (vários de cada vez), então milhares de celulares recebem em poucos minutos.

require_once __DIR__ . '/lib/banco.php';
require_once __DIR__ . '/lib/avisos.php';

$viaTerminal = PHP_SAPI === 'cli';
if (!$viaTerminal) {
    header('Content-Type: text/plain; charset=utf-8');
    $config = te_config();
    $chave = isset($config['chave_cron']) ? (string)$config['chave_cron'] : '';
    if ($chave === '' || !hash_equals($chave, isset($_GET['chave']) ? (string)$_GET['chave'] : '')) {
        http_response_code(403);
        exit("Acesso negado.\n");
    }
}

const TE_JANELA_MINUTOS = 45;   // um encontro só é lembrado até 45 minutos depois do horário escolhido
const TE_PARALELO = 100;        // quantos avisos saem ao mesmo tempo

set_time_limit(0);
ignore_user_abort(true);

// Impede duas rodadas ao mesmo tempo (se uma demorar mais de 5 minutos).
$trava = fopen(te_pasta_dados() . '/avisos-cron.lock', 'c');
if (!$trava || !flock($trava, LOCK_EX | LOCK_NB)) {
    echo date('Y-m-d H:i') . ": rodada anterior ainda em andamento.\n";
    exit;
}

$inicioRodada = microtime(true);
$config = te_config();
$contato = !empty($config['contato_avisos']) ? (string)$config['contato_avisos'] : 'mailto:contato@exemplo.com';
$chaves = te_chaves_vapid();
$agoraUtc = new DateTime('now', new DateTimeZone('UTC'));
$fusos = array();

// 1) Monta a fila: só quem está nos 30 dias da jornada (com folga de um dia por causa dos fusos).
$desde = gmdate('Y-m-d', strtotime('-31 days'));
$st = te_sql(
    'SELECT a.id, a.endpoint, a.fuso, a.enviado_manha, a.enviado_almoco, a.enviado_noite, c.inicio, c.horarios
     FROM te_avisos a JOIN te_codigos c ON c.codigo = a.codigo
     WHERE c.bloqueado = 0 AND c.inicio IS NOT NULL AND c.inicio >= ? AND c.horarios IS NOT NULL',
    array($desde)
);
$fila = array();
while ($a = $st->fetch()) {
    if (!isset($fusos[$a['fuso']])) {
        $local = clone $agoraUtc;
        $local->setTimezone(new DateTimeZone($a['fuso']));
        $fusos[$a['fuso']] = array($local->format('Y-m-d'), (int)$local->format('G') * 60 + (int)$local->format('i'));
    }
    list($hoje, $minutosAgora) = $fusos[$a['fuso']];
    $dia = te_dia_da_jornada($a['inicio'], $hoje);
    if ($dia < 1 || $dia > TE_TOTAL_DIAS) {
        continue;
    }
    $horarios = explode(',', $a['horarios']);
    foreach (TE_MOMENTOS as $i => $m) {
        list($h, $min) = array_map('intval', explode(':', $horarios[$i]));
        $atraso = $minutosAgora - ($h * 60 + $min);
        if ($atraso >= 0 && $atraso <= TE_JANELA_MINUTOS && $a['enviado_' . $m] !== $hoje) {
            $fila[] = array('id' => $a['id'], 'endpoint' => $a['endpoint'], 'momento' => $m, 'data' => $hoje);
            break; // no máximo um aviso por celular a cada rodada
        }
    }
}

// 2) Envia em paralelo. A assinatura vale 12 horas, então é feita uma vez por serviço (Google, Apple, Mozilla).
$jwtPorServico = array();
$entregues = array();
$expirados = array();
$falhas = 0;
$multi = curl_multi_init();
$ativos = array();
$proximo = 0;

$adicionar = function () use (&$proximo, &$fila, &$ativos, $multi, &$jwtPorServico, $chaves, $contato) {
    $item = $fila[$proximo++];
    $u = parse_url($item['endpoint']);
    $servico = $u['scheme'] . '://' . $u['host'] . (isset($u['port']) ? ':' . $u['port'] : '');
    if (!isset($jwtPorServico[$servico])) {
        $jwtPorServico[$servico] = te_jwt_vapid($item['endpoint'], $chaves, $contato);
    }
    $ch = curl_init($item['endpoint']);
    curl_setopt_array($ch, array(
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => '',
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 20,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_HTTPHEADER => array(
            'TTL: 3600',
            'Urgency: normal',
            'Content-Length: 0',
            'Authorization: vapid t=' . $jwtPorServico[$servico] . ', k=' . $chaves['publica'],
        ),
    ));
    curl_multi_add_handle($multi, $ch);
    $ativos[(int)$ch] = $item;
};

while ($proximo < count($fila) && count($ativos) < TE_PARALELO) {
    $adicionar();
}
do {
    curl_multi_exec($multi, $rodando);
    curl_multi_select($multi, 1.0);
    while ($info = curl_multi_info_read($multi)) {
        $ch = $info['handle'];
        $item = $ativos[(int)$ch];
        $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        if ($status >= 200 && $status < 300) {
            $entregues[] = $item;
        } elseif ($status === 404 || $status === 410) {
            $expirados[] = $item['id'];
        } else {
            $falhas++; // tenta de novo na próxima rodada, dentro da janela
        }
        unset($ativos[(int)$ch]);
        curl_multi_remove_handle($multi, $ch);
        curl_close($ch);
        if ($proximo < count($fila)) {
            $adicionar();
        }
    }
} while ($ativos);
curl_multi_close($multi);

// 3) Registra o que foi entregue e remove celulares que cancelaram os avisos.
$pdo = te_banco();
$pdo->beginTransaction();
foreach ($entregues as $item) {
    te_sql('UPDATE te_avisos SET enviado_' . $item['momento'] . ' = ? WHERE id = ?', array($item['data'], $item['id']));
}
foreach (array_chunk($expirados, 500) as $lote) {
    te_sql('DELETE FROM te_avisos WHERE id IN (' . implode(',', array_fill(0, count($lote), '?')) . ')', $lote);
}
$pdo->commit();

flock($trava, LOCK_UN);
printf("%s: %d na fila, %d entregues, %d removidos, %d falhas, %.1f s.\n",
    date('Y-m-d H:i'), count($fila), count($entregues), count($expirados), $falhas, microtime(true) - $inicioRodada);
