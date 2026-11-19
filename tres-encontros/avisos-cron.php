<?php
// Envia os avisos dos encontros liberados. Rode a cada 5 minutos pelo agendador (cron) da Hostinger:
//   /usr/bin/php /home/SEU_USUARIO/public_html/tres-encontros/avisos-cron.php
// Também aceita chamada pela web com ?chave=... (defina "chave_cron" na config.php).

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

const TE_JANELA_MINUTOS = 45; // um encontro só é avisado até 45 minutos depois do horário

$config = te_config();
$contato = !empty($config['contato_avisos']) ? (string)$config['contato_avisos'] : 'mailto:contato@exemplo.com';
$chaves = te_chaves_vapid();
$codigos = te_ler('codigos');
$agoraUtc = new DateTime('now', new DateTimeZone('UTC'));

// 1) Decide o que enviar, sem segurar a trava durante a rede.
$fila = array();
foreach (te_ler('avisos') as $id => $a) {
    $r = isset($codigos[$a['codigo']]) ? $codigos[$a['codigo']] : null;
    if (!$r || !empty($r['bloqueado']) || empty($r['inicio']) || empty($r['horarios'])) {
        continue;
    }
    $local = clone $agoraUtc;
    $local->setTimezone(new DateTimeZone($a['fuso']));
    $hoje = $local->format('Y-m-d');
    $dia = te_dia_da_jornada($r['inicio'], $hoje);
    if ($dia < 1 || $dia > TE_TOTAL_DIAS) {
        continue;
    }
    $minutosAgora = (int)$local->format('G') * 60 + (int)$local->format('i');
    foreach (TE_MOMENTOS as $m) {
        list($h, $min) = array_map('intval', explode(':', $r['horarios'][$m]));
        $atraso = $minutosAgora - ($h * 60 + $min);
        $marca = $hoje . '|' . $m;
        if ($atraso >= 0 && $atraso <= TE_JANELA_MINUTOS && empty($a['enviados'][$marca])) {
            $fila[] = array('id' => $id, 'endpoint' => $a['endpoint'], 'marca' => $marca);
            break; // no máximo um aviso por celular a cada rodada
        }
    }
}

// 2) Envia.
$resultado = array();
foreach ($fila as $item) {
    $resultado[$item['id']] = array('status' => te_enviar_aviso($item['endpoint'], $chaves, $contato), 'marca' => $item['marca']);
}

// 3) Registra o que foi entregue e remove celulares que cancelaram os avisos.
$entregues = 0;
te_atualizar('avisos', function (&$avisos) use ($resultado, &$entregues) {
    $limite = date('Y-m-d', strtotime('-3 days'));
    foreach ($resultado as $id => $r) {
        if (!isset($avisos[$id])) {
            continue;
        }
        if ($r['status'] === 404 || $r['status'] === 410) {
            unset($avisos[$id]);
            continue;
        }
        if ($r['status'] >= 200 && $r['status'] < 300) {
            $avisos[$id]['enviados'][$r['marca']] = time();
            $entregues++;
        }
        foreach ($avisos[$id]['enviados'] as $marca => $t) {
            if (substr($marca, 0, 10) < $limite) {
                unset($avisos[$id]['enviados'][$marca]);
            }
        }
    }
});

echo date('Y-m-d H:i') . ': ' . count($fila) . ' avisos na fila, ' . $entregues . " entregues.\n";
