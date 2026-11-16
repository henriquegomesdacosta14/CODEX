<?php
/**
 * Conversa com a secretária pelo terminal (para testar no computador):
 *   php terminal.php
 * Comandos: /nova (recomeça a conversa)  /sair
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require __DIR__ . '/inicializar.php';

$telefone = $argv[1] ?? '5500000000001';
$secretaria = criarSecretaria($config, $armazenamento);

echo "Secretária virtual - teste no terminal (telefone {$telefone})\n";
echo "Digite como se fosse o paciente. /nova recomeça, /sair encerra.\n\n";

while (true) {
    $linha = readline('Você: ');
    if ($linha === false || trim($linha) === '/sair') {
        break;
    }
    $linha = trim($linha);
    if ($linha === '') {
        continue;
    }
    if ($linha === '/nova') {
        $secretaria->reiniciarConversa($telefone);
        echo "(conversa reiniciada)\n\n";
        continue;
    }
    $inicio = microtime(true);
    $resposta = $secretaria->responder($telefone, 'Teste Terminal', $linha);
    printf("Secretária (%.1fs): %s\n\n", microtime(true) - $inicio, $resposta);
}
