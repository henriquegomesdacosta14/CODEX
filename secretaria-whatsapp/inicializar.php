<?php
// Carrega a configuração e as classes do protótipo (sem Composer, sem bibliotecas).

if (!is_file(__DIR__ . '/config.php')) {
    http_response_code(500);
    exit("Falta o config.php. Copie config.example.php para config.php e preencha. Abra verificar.php para ver o que falta.\n");
}

// Carrega Secretaria\NomeDaClasse a partir de src/NomeDaClasse.php
spl_autoload_register(function (string $classe): void {
    if (str_starts_with($classe, 'Secretaria\\')) {
        $arquivo = __DIR__ . '/src/' . substr($classe, 11) . '.php';
        if (is_file($arquivo)) {
            require $arquivo;
        }
    }
});

$config = require __DIR__ . '/config.php';
date_default_timezone_set($config['fuso_horario'] ?? 'America/Sao_Paulo');

$armazenamento = new Secretaria\Armazenamento(__DIR__ . '/dados');

function criarSecretaria(array $config, Secretaria\Armazenamento $armazenamento): Secretaria\Secretaria
{
    return new Secretaria\Secretaria($config, $armazenamento, __DIR__ . '/clinica');
}
