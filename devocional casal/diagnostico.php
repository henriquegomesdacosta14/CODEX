<?php
header('Content-Type: text/plain; charset=utf-8');

$dataDir = __DIR__ . '/data';
$testFile = $dataDir . '/teste.txt';

echo "Diagnostico do Devocional\n";
echo "=========================\n\n";
echo "PHP: " . PHP_VERSION . "\n";
echo "Pasta atual: " . __DIR__ . "\n\n";

if (!file_exists(__DIR__ . '/config.php')) {
    echo "ERRO: config.php nao encontrado.\n";
} else {
    echo "OK: config.php encontrado.\n";
}

if (!file_exists(__DIR__ . '/api.php')) {
    echo "ERRO: api.php nao encontrado.\n";
} else {
    echo "OK: api.php encontrado.\n";
}

if (!is_dir($dataDir)) {
    echo "Pasta data nao existe. Tentando criar...\n";
    if (mkdir($dataDir, 0755, true)) {
        echo "OK: pasta data criada.\n";
    } else {
        echo "ERRO: nao foi possivel criar a pasta data.\n";
        exit;
    }
} else {
    echo "OK: pasta data encontrada.\n";
}

if (file_put_contents($testFile, 'ok ' . date('c')) === false) {
    echo "ERRO: nao foi possivel gravar dentro da pasta data.\n";
    exit;
}

echo "OK: gravacao na pasta data funcionou.\n";
@unlink($testFile);
echo "\nDepois do teste, apague diagnostico.php da hospedagem.\n";
