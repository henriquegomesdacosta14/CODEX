<?php
/**
 * API da página cadastro.html: a clínica preenche seus dados e a
 * secretária passa a usá-los (nas conversas novas).
 */

require __DIR__ . '/inicializar.php';

use Secretaria\Clinica;

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
    responderJson(['erro' => 'Cadastro desativado: defina senha_cadastro no config.php'], 403);
}
$entrada = json_decode(file_get_contents('php://input') ?: '', true) ?? [];
if (!hash_equals($senhaConfig, (string) ($entrada['senha'] ?? ''))) {
    usleep(500000);
    responderJson(['erro' => 'Senha incorreta'], 401);
}

$pastaClinica = __DIR__ . '/clinica';

switch ($entrada['acao'] ?? '') {
    case 'carregar':
        responderJson([
            'clinica' => Clinica::carregar($armazenamento, $pastaClinica),
            'eh_exemplo' => !Clinica::cadastrada($armazenamento),
            'atualizado_em' => $armazenamento->ler('clinica_info', [])['atualizado_em'] ?? null,
        ]);

    case 'salvar':
        [$dados, $erros, $faltando] = Clinica::validar((array) ($entrada['clinica'] ?? []));
        if ($erros || $faltando) {
            responderJson(['erro' => implode(' ', array_merge($faltando, $erros))], 400);
        }
        Clinica::salvar($armazenamento, $dados, $pastaClinica, 'formulário');
        responderJson(['ok' => true, 'clinica' => $dados]);

    default:
        responderJson(['erro' => 'Ação desconhecida'], 400);
}
