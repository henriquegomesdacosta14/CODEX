<?php

namespace Secretaria;

/**
 * Comunicação com a API oficial do WhatsApp (Meta Cloud API).
 */
class WhatsApp
{
    public function __construct(private array $config, private Armazenamento $armazenamento)
    {
    }

    /** Confere se a requisição veio mesmo da Meta (assinatura X-Hub-Signature-256). */
    public function assinaturaValida(string $corpo, ?string $assinatura): bool
    {
        $segredo = $this->config['whatsapp_app_secret'] ?? '';
        if ($segredo === '') {
            $this->armazenamento->registrarLog('AVISO: whatsapp_app_secret vazio, assinatura não verificada.');
            return true;
        }
        if (!$assinatura || !str_starts_with($assinatura, 'sha256=')) {
            return false;
        }
        $esperada = 'sha256=' . hash_hmac('sha256', $corpo, $segredo);
        return hash_equals($esperada, $assinatura);
    }

    /**
     * Extrai as mensagens recebidas do JSON que a Meta envia.
     * @return list<array{id:string, telefone:string, nome:string, tipo:string, texto:string}>
     */
    public function extrairMensagens(array $payload): array
    {
        $saida = [];
        foreach ($payload['entry'] ?? [] as $entrada) {
            foreach ($entrada['changes'] ?? [] as $mudanca) {
                $valor = $mudanca['value'] ?? [];
                $nomes = [];
                foreach ($valor['contacts'] ?? [] as $c) {
                    $nomes[$c['wa_id'] ?? ''] = $c['profile']['name'] ?? '';
                }
                foreach ($valor['messages'] ?? [] as $m) {
                    $tipo = $m['type'] ?? '';
                    $texto = match ($tipo) {
                        'text' => $m['text']['body'] ?? '',
                        'button' => $m['button']['text'] ?? '',
                        'interactive' => $m['interactive']['button_reply']['title']
                            ?? $m['interactive']['list_reply']['title'] ?? '',
                        default => '',
                    };
                    $saida[] = [
                        'id' => $m['id'] ?? '',
                        'telefone' => $m['from'] ?? '',
                        'nome' => $nomes[$m['from'] ?? ''] ?? '',
                        'tipo' => $tipo,
                        'texto' => $texto,
                    ];
                }
            }
        }
        return $saida;
    }

    /** Evita responder duas vezes a mesma mensagem (a Meta pode reenviar). */
    public function jaProcessada(string $idMensagem): bool
    {
        return $this->armazenamento->atualizar('mensagens_processadas', function (array $ids) use ($idMensagem) {
            if (in_array($idMensagem, $ids, true)) {
                return [$ids, true];
            }
            $ids[] = $idMensagem;
            return [array_slice($ids, -1000), false];
        }, []);
    }

    public function marcarComoLida(string $idMensagem): void
    {
        $this->chamarApi([
            'messaging_product' => 'whatsapp',
            'status' => 'read',
            'message_id' => $idMensagem,
        ]);
    }

    public function enviarTexto(string $telefone, string $texto): bool
    {
        // O WhatsApp aceita até 4096 caracteres por mensagem
        foreach (mb_str_split($texto, 4000) as $parte) {
            $ok = $this->chamarApi([
                'messaging_product' => 'whatsapp',
                'recipient_type' => 'individual',
                'to' => $telefone,
                'type' => 'text',
                'text' => ['preview_url' => false, 'body' => $parte],
            ]);
            if (!$ok) {
                return false;
            }
        }
        return true;
    }

    private function chamarApi(array $corpo): bool
    {
        $versao = $this->config['graph_api_version'] ?? 'v23.0';
        $url = "https://graph.facebook.com/{$versao}/" . rawurlencode($this->config['whatsapp_phone_number_id'] ?? '') . '/messages';

        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 20,
            CURLOPT_HTTPHEADER => [
                'Authorization: Bearer ' . ($this->config['whatsapp_token'] ?? ''),
                'Content-Type: application/json',
            ],
            CURLOPT_POSTFIELDS => json_encode($corpo, JSON_UNESCAPED_UNICODE),
        ]);
        $resposta = curl_exec($ch);
        $status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $erro = curl_error($ch);
        curl_close($ch);

        if ($status < 200 || $status >= 300) {
            $this->armazenamento->registrarLog("ERRO WhatsApp HTTP {$status}: {$erro} " . substr((string) $resposta, 0, 500));
            return false;
        }
        return true;
    }
}
