<?php
// Carrega configuração, bibliotecas e as classes do protótipo.

if (!is_file(__DIR__ . '/vendor/autoload.php')) {
    http_response_code(500);
    exit("Faltam as bibliotecas. Rode 'composer install' dentro da pasta secretaria-whatsapp.\n");
}
if (!is_file(__DIR__ . '/config.php')) {
    http_response_code(500);
    exit("Falta o config.php. Copie config.example.php para config.php e preencha.\n");
}

require __DIR__ . '/vendor/autoload.php';

$config = require __DIR__ . '/config.php';
date_default_timezone_set($config['fuso_horario'] ?? 'America/Sao_Paulo');

$armazenamento = new Secretaria\Armazenamento(__DIR__ . '/dados');

function criarSecretaria(array $config, Secretaria\Armazenamento $armazenamento): Secretaria\Secretaria
{
    return new Secretaria\Secretaria($config, $armazenamento, __DIR__ . '/clinica');
}
