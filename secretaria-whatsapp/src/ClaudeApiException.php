<?php

namespace Secretaria;

/** Erro ao falar com a API da Anthropic. */
class ClaudeApiException extends \RuntimeException
{
    public function __construct(string $mensagem, public readonly int $status = 0, public readonly string $tipo = '')
    {
        parent::__construct($mensagem, $status);
    }
}
