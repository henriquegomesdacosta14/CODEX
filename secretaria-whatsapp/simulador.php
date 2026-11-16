<?php
/**
 * API do simulador (usada por simulador.html). Permite testar a secretária
 * sem WhatsApp: você digita como se fosse o paciente.
 * Protegido pela 'senha_simulador' do config.php.
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

$senhaConfig = (string) ($config['senha_simulador'] ?? '');
if ($senhaConfig === '') {
    responderJson(['erro' => 'Simulador desativado no config.php'], 403);
}

$entrada = json_decode(file_get_contents('php://input') ?: '', true) ?? [];
if (!hash_equals($senhaConfig, (string) ($entrada['senha'] ?? ''))) {
    usleep(500000);
    responderJson(['erro' => 'Senha incorreta'], 401);
}

// Telefone de teste (só números). Use um diferente para simular outro paciente.
$telefone = preg_replace('/\D/', '', (string) ($entrada['telefone'] ?? '')) ?: '5500000000000';
$acao = $entrada['acao'] ?? 'mensagem';

switch ($acao) {
    case 'mensagem':
        $texto = trim((string) ($entrada['mensagem'] ?? ''));
        if ($texto === '') {
            responderJson(['erro' => 'Mensagem vazia'], 400);
        }
        $inicio = microtime(true);
        $resposta = criarSecretaria($config, $armazenamento)->responder($telefone, (string) ($entrada['nome'] ?? 'Paciente Teste'), $texto);
        responderJson(['resposta' => $resposta, 'segundos' => round(microtime(true) - $inicio, 1)]);

    case 'reiniciar':
        criarSecretaria($config, $armazenamento)->reiniciarConversa($telefone);
        responderJson(['ok' => true]);

    case 'painel':
        $agendamentos = $armazenamento->ler('agendamentos', []);
        usort($agendamentos, fn ($a, $b) => strcmp($a['data'] . $a['hora'], $b['data'] . $b['hora']));
        responderJson([
            'agendamentos' => $agendamentos,
            'transferencias' => array_reverse($armazenamento->ler('transferencias', [])),
        ]);

    default:
        responderJson(['erro' => 'Ação desconhecida'], 400);
}
