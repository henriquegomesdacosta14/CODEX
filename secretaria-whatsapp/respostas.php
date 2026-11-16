<?php
/**
 * API do painel de respostas rápidas (usada por respostas.html).
 * Protegido pela 'senha_simulador' do config.php.
 */

require __DIR__ . '/inicializar.php';

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
$senhaConfig = (string) ($config['senha_simulador'] ?? '');
if ($senhaConfig === '') {
    responderJson(['erro' => 'Painel desativado no config.php'], 403);
}
$entrada = json_decode(file_get_contents('php://input') ?: '', true) ?? [];
if (!hash_equals($senhaConfig, (string) ($entrada['senha'] ?? ''))) {
    usleep(500000);
    responderJson(['erro' => 'Senha incorreta'], 401);
}

$clinica = Secretaria\Clinica::carregar($armazenamento, __DIR__ . '/clinica');
$rapidas = new RespostasRapidas($armazenamento, $clinica, __DIR__ . '/clinica/respostas_rapidas.json');
$rapidas->todas(); // garante que o arquivo de respostas exista

switch ($entrada['acao'] ?? '') {
    case 'listar':
        $perguntas = [];
        foreach ($armazenamento->ler('perguntas_frequentes', []) as $chave => $p) {
            if (!($p['ignorada'] ?? false)) {
                $perguntas[] = ['chave' => $chave] + $p;
            }
        }
        usort($perguntas, fn ($a, $b) => [$b['vezes'], $b['ultima_vez']] <=> [$a['vezes'], $a['ultima_vez']]);
        responderJson([
            'respostas' => $rapidas->todas(),
            'perguntas' => array_slice($perguntas, 0, 100),
            'estatisticas' => $armazenamento->ler('estatisticas', []),
        ]);

    case 'salvar':
        $r = $entrada['resposta'] ?? [];
        $gatilhos = array_values(array_unique(array_filter(array_map(
            fn ($g) => RespostasRapidas::normalizar((string) $g),
            (array) ($r['gatilhos'] ?? [])
        ))));
        $texto = trim((string) ($r['resposta'] ?? ''));
        if (!$gatilhos || $texto === '') {
            responderJson(['erro' => 'Informe pelo menos um gatilho e o texto da resposta.'], 400);
        }
        $item = [
            'id' => preg_replace('/[^a-z0-9_]/', '', (string) ($r['id'] ?? '')) ?: 'r_' . bin2hex(random_bytes(4)),
            'modo' => ($r['modo'] ?? '') === 'exato' ? 'exato' : 'contem',
            'gatilhos' => $gatilhos,
            'resposta' => $texto,
            'ativo' => (bool) ($r['ativo'] ?? true),
        ];
        $armazenamento->atualizar('respostas_rapidas', function (array $lista) use ($item) {
            foreach ($lista as $i => $x) {
                if ($x['id'] === $item['id']) {
                    $lista[$i] = $item;
                    return [$lista, null];
                }
            }
            $lista[] = $item;
            return [$lista, null];
        }, []);
        // Se veio de uma pergunta aprendida, tira ela da lista de pendentes
        if (!empty($entrada['chave_pergunta'])) {
            $chave = (string) $entrada['chave_pergunta'];
            $armazenamento->atualizar('perguntas_frequentes', function (array $lista) use ($chave) {
                if (isset($lista[$chave])) {
                    $lista[$chave]['ignorada'] = true;
                    $lista[$chave]['aprovada'] = true;
                }
                return [$lista, null];
            }, []);
        }
        responderJson(['ok' => true, 'resposta' => $item]);

    case 'excluir':
        $id = (string) ($entrada['id'] ?? '');
        $armazenamento->atualizar('respostas_rapidas', fn (array $lista) => [
            array_values(array_filter($lista, fn ($x) => $x['id'] !== $id)), null,
        ], []);
        responderJson(['ok' => true]);

    case 'ignorar_pergunta':
        $chave = (string) ($entrada['chave'] ?? '');
        $armazenamento->atualizar('perguntas_frequentes', function (array $lista) use ($chave) {
            if (isset($lista[$chave])) {
                $lista[$chave]['ignorada'] = true;
            }
            return [$lista, null];
        }, []);
        responderJson(['ok' => true]);

    case 'testar':
        $achou = $rapidas->procurar((string) ($entrada['mensagem'] ?? ''));
        responderJson(['achou' => $achou]);

    default:
        responderJson(['erro' => 'Ação desconhecida'], 400);
}
