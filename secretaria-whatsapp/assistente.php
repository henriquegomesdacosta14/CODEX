<?php
/**
 * API do chat de configuração (assistente.html).
 * Protegido pela 'senha_cadastro' (ou 'senha_simulador') do config.php.
 */

require __DIR__ . '/inicializar.php';

header('Content-Type: application/json; charset=utf-8');

function responderJson(array $dados, int $status = 200): never
{
    http_response_code($status);
    echo json_encode($dados, JSON_UNESCAPED_UNICODE);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    responderJson(['erro' => 'Use POST'], 405);
}
$senhaConfig = (string) (($config['senha_cadastro'] ?? '') ?: ($config['senha_simulador'] ?? ''));
if ($senhaConfig === '') {
    responderJson(['erro' => 'Defina senha_cadastro no config.php'], 403);
}
$entrada = json_decode(file_get_contents('php://input') ?: '', true) ?? [];
if (!hash_equals($senhaConfig, (string) ($entrada['senha'] ?? ''))) {
    usleep(500000);
    responderJson(['erro' => 'Senha incorreta'], 401);
}

$assistente = new Secretaria\Assistente($config, $armazenamento, __DIR__ . '/clinica');

switch ($entrada['acao'] ?? '') {
    case 'historico':
        responderJson($assistente->historico(max(0, (int) ($entrada['desde'] ?? 0))));

    case 'enviar':
        $autor = mb_substr(trim((string) ($entrada['autor'] ?? '')), 0, 40);
        $texto = mb_substr(trim((string) ($entrada['texto'] ?? '')), 0, 8000);
        if ($autor === '' || $texto === '') {
            responderJson(['erro' => 'Informe seu nome e a mensagem.'], 400);
        }
        ignore_user_abort(true);
        set_time_limit(600);
        $assistente->enviar($autor, $texto);
        responderJson($assistente->historico(max(0, (int) ($entrada['desde'] ?? 0))));

    case 'nova_conversa':
        $assistente->novaConversa();
        responderJson(['ok' => true]);

    case 'pendencias':
        responderJson(['pendencias' => $armazenamento->ler('pendencias', [])]);

    default:
        responderJson(['erro' => 'Ação desconhecida'], 400);
}
