<?php
/**
 * Endereço que você cadastra no painel da Meta como "URL de callback":
 *   https://SEU-DOMINIO/secretaria-whatsapp/webhook.php
 *
 * GET  -> verificação do webhook (a Meta chama uma vez ao cadastrar)
 * POST -> chegada de mensagens dos pacientes
 */

require __DIR__ . '/inicializar.php';

$whatsapp = new Secretaria\WhatsApp($config, $armazenamento);

// ---------- 1. Verificação do webhook ----------
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $modo = $_GET['hub_mode'] ?? '';
    $token = $_GET['hub_verify_token'] ?? '';
    $desafio = $_GET['hub_challenge'] ?? '';

    if ($modo === 'subscribe' && hash_equals((string) $config['whatsapp_verify_token'], (string) $token)) {
        header('Content-Type: text/plain');
        echo $desafio;
    } else {
        http_response_code(403);
        echo 'Token de verificação inválido';
    }
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    exit;
}

// ---------- 2. Mensagem recebida ----------
$corpo = file_get_contents('php://input') ?: '';

if (!$whatsapp->assinaturaValida($corpo, $_SERVER['HTTP_X_HUB_SIGNATURE_256'] ?? null)) {
    http_response_code(401);
    $armazenamento->registrarLog('Webhook com assinatura inválida recusado.');
    exit;
}

// Responde 200 para a Meta IMEDIATAMENTE (senão ela reenvia a mensagem)
// e continua processando em segundo plano.
ignore_user_abort(true);
set_time_limit(300);
http_response_code(200);
header('Content-Type: text/plain');
header('Content-Length: 2');
header('Connection: close');
echo 'OK';
if (function_exists('litespeed_finish_request')) {
    litespeed_finish_request();          // Hostinger (LiteSpeed)
} elseif (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request();            // PHP-FPM
} else {
    @ob_end_flush();
    flush();
}

$payload = json_decode($corpo, true);
if (!is_array($payload)) {
    exit;
}

$mensagens = $whatsapp->extrairMensagens($payload);
if (!$mensagens) {
    exit; // eram só avisos de status (entregue, lida...), nada a responder
}

$secretaria = criarSecretaria($config, $armazenamento);

foreach ($mensagens as $msg) {
    if ($msg['id'] === '' || $msg['telefone'] === '' || $whatsapp->jaProcessada($msg['id'])) {
        continue;
    }
    $whatsapp->marcarComoLida($msg['id']);

    if (trim($msg['texto']) === '') {
        $whatsapp->enviarTexto(
            $msg['telefone'],
            'Por enquanto só consigo ler mensagens de texto 🙂 Pode escrever o que precisa?'
        );
        continue;
    }

    $armazenamento->registrarLog("RECEBIDA de {$msg['telefone']}: {$msg['texto']}");
    $resposta = $secretaria->responder($msg['telefone'], $msg['nome'], $msg['texto']);
    $enviada = $whatsapp->enviarTexto($msg['telefone'], $resposta);
    $armazenamento->registrarLog(($enviada ? 'ENVIADA' : 'FALHA AO ENVIAR') . " para {$msg['telefone']}: {$resposta}");
}
