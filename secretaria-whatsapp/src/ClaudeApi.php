<?php

namespace Secretaria;

/**
 * Cliente mínimo da API de mensagens da Anthropic (POST /v1/messages),
 * só com cURL: não precisa de Composer nem de bibliotecas.
 */
class ClaudeApi
{
    private const VERSAO_API = '2026-10-21';
    private const STATUS_COM_RETENTATIVA = [408, 409, 429, 500, 502, 503, 504, 529];

    /** Forma de enviar a chave que funcionou: 'bearer' ou 'x-api-key'. */
    private static string $estiloAuth = 'bearer';

    public function __construct(
        private string $chave,
        private ?string $urlBase = null,
        private int $timeout = 90,
        private int $maxRetentativas = 2,
    ) {
    }

    /**
     * Envia uma requisição de mensagem e devolve a resposta como array.
     * @param array $corpo   Corpo da requisição, já em snake_case (model, max_tokens, messages...)
     * @param list<string> $betas Recursos beta a ativar
     */
    public function mensagem(array $corpo, array $betas = []): array
    {
        if ($this->chave === '') {
            throw new ClaudeApiException('Chave da Anthropic não configurada (anthropic_api_key no config.php).', 0, 'sem_chave');
        }
        $corpo['messages'] = self::prepararHistorico($corpo['messages'] ?? []);
        $json = json_encode($corpo, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
        if ($json === false) {
            throw new ClaudeApiException('Não foi possível montar a requisição: ' . json_last_error_msg());
        }

        $url = rtrim($this->urlBase ?: 'https://api.anthropic.com', '/') . '/v1/messages';
        $tentativa = 0;
        $trocouAuth = false;

        while (true) {
            [$status, $resposta, $erroCurl, $espera] = $this->enviar($url, $json, $betas);

            if ($status >= 200 && $status < 300) {
                $dados = json_decode($resposta, true);
                if (!is_array($dados)) {
                    throw new ClaudeApiException('Resposta inválida da API.', $status);
                }
                return self::limparResposta($dados);
            }

            // 401 com "Bearer": tenta uma vez com x-api-key (e lembra do que funcionou)
            if ($status === 401 && !$trocouAuth) {
                $trocouAuth = true;
                self::$estiloAuth = self::$estiloAuth === 'bearer' ? 'x-api-key' : 'bearer';
                continue;
            }

            $retentar = $status === 0 || in_array($status, self::STATUS_COM_RETENTATIVA, true);
            if ($retentar && $tentativa < $this->maxRetentativas) {
                $tentativa++;
                usleep((int) (min(8.0, $espera ?? (0.5 * (2 ** ($tentativa - 1)))) * 1_000_000));
                continue;
            }

            $erro = json_decode($resposta, true)['error'] ?? [];
            $tipo = (string) ($erro['type'] ?? '');
            $msg = (string) ($erro['message'] ?? ($erroCurl !== '' ? $erroCurl : substr($resposta, 0, 300)));
            throw new ClaudeApiException("API {$status}" . ($tipo !== '' ? " ({$tipo})" : '') . ": {$msg}", $status, $tipo);
        }
    }

    /** @return array{0:int,1:string,2:string,3:?float} [status, corpo, erro do cURL, espera pedida pelo servidor] */
    private function enviar(string $url, string $json, array $betas): array
    {
        $cabecalhos = [
            'Content-Type: application/json',
            'Accept: application/json',
            'anthropic-version: ' . self::VERSAO_API,
            self::$estiloAuth === 'bearer' ? 'Authorization: Bearer ' . $this->chave : 'x-api-key: ' . $this->chave,
        ];
        if ($betas) {
            $cabecalhos[] = 'anthropic-beta: ' . implode(',', $betas);
        }

        $espera = null;
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $json,
            CURLOPT_HTTPHEADER => $cabecalhos,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 15,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_HEADERFUNCTION => function ($ch, $linha) use (&$espera) {
                if (stripos($linha, 'retry-after:') === 0 && is_numeric(trim(substr($linha, 12)))) {
                    $espera = (float) trim(substr($linha, 12));
                }
                return strlen($linha);
            },
        ]);
        $corpo = curl_exec($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $erro = curl_error($ch);
        curl_close($ch);

        return [$status, is_string($corpo) ? $corpo : '', $erro, $espera];
    }

    /** Remove campos nulos dos blocos de conteúdo (a API aceita o histórico sem eles). */
    private static function limparResposta(array $r): array
    {
        foreach ($r['content'] ?? [] as $i => $bloco) {
            if (is_array($bloco)) {
                $r['content'][$i] = array_filter($bloco, fn ($v) => $v !== null);
            }
        }
        return $r;
    }

    /** Garante que `input` vazio de ferramentas vá como objeto {} (e não como lista []). */
    private static function prepararHistorico(array $mensagens): array
    {
        foreach ($mensagens as $i => $m) {
            if (!is_array($m['content'] ?? null)) {
                continue;
            }
            foreach ($m['content'] as $j => $bloco) {
                if (is_array($bloco) && ($bloco['type'] ?? '') === 'tool_use' && ($bloco['input'] ?? null) === []) {
                    $mensagens[$i]['content'][$j]['input'] = new \stdClass();
                }
            }
        }
        return $mensagens;
    }
}
