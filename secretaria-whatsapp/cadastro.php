<?php
/**
 * API da página cadastro.html: a clínica preenche seus dados e a
 * secretária passa a usá-los (nas conversas novas).
 */

require __DIR__ . '/inicializar.php';

use Secretaria\Clinica;
use Secretaria\RespostasRapidas;

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
        [$dados, $erros] = Clinica::validar((array) ($entrada['clinica'] ?? []));
        if ($erros) {
            responderJson(['erro' => implode(' ', $erros)], 400);
        }

        // Guarda a versão anterior (segurança)
        $anterior = $armazenamento->ler('clinica', null);
        if ($anterior) {
            $armazenamento->salvar('clinica_backup_' . date('Ymd_His'), $anterior);
        }
        $armazenamento->salvar('clinica', $dados);
        $armazenamento->salvar('clinica_info', ['atualizado_em' => date('c')]);

        // Perguntas frequentes com palavras-chave viram respostas rápidas (grátis)
        $rapidas = new RespostasRapidas($armazenamento, $dados, $pastaClinica . '/respostas_rapidas.json');
        $rapidas->todas();
        $armazenamento->atualizar('respostas_rapidas', function (array $lista) use ($dados) {
            $lista = array_values(array_filter($lista, fn ($r) => !str_starts_with((string) $r['id'], 'faq_')));
            foreach ($dados['perguntas_frequentes'] as $i => $f) {
                $gatilhos = array_values(array_filter(array_map([RespostasRapidas::class, 'normalizar'], $f['palavras_chave'])));
                if ($gatilhos) {
                    $lista[] = ['id' => 'faq_' . ($i + 1), 'modo' => 'contem', 'gatilhos' => $gatilhos, 'resposta' => $f['resposta'], 'ativo' => true];
                }
            }
            return [$lista, null];
        }, []);

        $armazenamento->registrarLog('Cadastro da clínica atualizado.');
        responderJson(['ok' => true, 'clinica' => $dados]);

    default:
        responderJson(['erro' => 'Ação desconhecida'], 400);
}
