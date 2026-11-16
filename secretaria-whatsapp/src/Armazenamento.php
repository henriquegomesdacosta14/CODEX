<?php

namespace Secretaria;

/**
 * Guarda dados em arquivos JSON dentro da pasta "dados" (sem banco de dados).
 * Usa trava de arquivo (flock) para evitar que duas mensagens ao mesmo tempo
 * corrompam o arquivo.
 */
class Armazenamento
{
    public function __construct(private string $pasta)
    {
        if (!is_dir($this->pasta) && !mkdir($this->pasta, 0755, true) && !is_dir($this->pasta)) {
            throw new \RuntimeException("Não foi possível criar a pasta de dados: {$this->pasta}");
        }
    }

    public function caminho(string $nome): string
    {
        // Só letras, números, traço e sublinhado no nome do arquivo
        $seguro = preg_replace('/[^A-Za-z0-9_\-]/', '_', $nome);
        return $this->pasta . '/' . $seguro . '.json';
    }

    public function ler(string $nome, mixed $padrao = []): mixed
    {
        $arquivo = $this->caminho($nome);
        if (!is_file($arquivo)) {
            return $padrao;
        }
        $conteudo = file_get_contents($arquivo);
        $dados = json_decode($conteudo === false ? '' : $conteudo, true);
        return $dados ?? $padrao;
    }

    public function salvar(string $nome, mixed $dados): void
    {
        $arquivo = $this->caminho($nome);
        $json = json_encode($dados, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if (file_put_contents($arquivo, $json, LOCK_EX) === false) {
            throw new \RuntimeException("Não foi possível gravar {$arquivo}");
        }
    }

    /**
     * Lê, altera e salva um arquivo com trava exclusiva do começo ao fim.
     * A função $alterar recebe os dados atuais e devolve [novosDados, retorno].
     */
    public function atualizar(string $nome, callable $alterar, mixed $padrao = []): mixed
    {
        $arquivo = $this->caminho($nome);
        $h = fopen($arquivo, 'c+');
        if ($h === false) {
            throw new \RuntimeException("Não foi possível abrir {$arquivo}");
        }
        try {
            flock($h, LOCK_EX);
            $conteudo = stream_get_contents($h);
            $dados = json_decode($conteudo === false || $conteudo === '' ? 'null' : $conteudo, true) ?? $padrao;
            [$novos, $retorno] = $alterar($dados);
            ftruncate($h, 0);
            rewind($h);
            fwrite($h, json_encode($novos, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
            fflush($h);
            return $retorno;
        } finally {
            flock($h, LOCK_UN);
            fclose($h);
        }
    }

    /** Trava exclusiva por nome, para processar uma conversa de cada vez. */
    public function comTrava(string $nome, callable $funcao): mixed
    {
        $h = fopen($this->pasta . '/' . preg_replace('/[^A-Za-z0-9_\-]/', '_', $nome) . '.lock', 'c');
        if ($h === false) {
            return $funcao();
        }
        try {
            flock($h, LOCK_EX);
            return $funcao();
        } finally {
            flock($h, LOCK_UN);
            fclose($h);
        }
    }

    public function registrarLog(string $mensagem): void
    {
        $linha = '[' . date('Y-m-d H:i:s') . '] ' . $mensagem . PHP_EOL;
        @file_put_contents($this->pasta . '/log.txt', $linha, FILE_APPEND | LOCK_EX);
    }
}
