<?php

namespace Secretaria;

use Anthropic\Client;
use Anthropic\Core\Exceptions\APIConnectionException;
use Anthropic\Core\Exceptions\APIStatusException;
use Anthropic\Core\Exceptions\RateLimitException;

/**
 * O "cérebro" da secretária: recebe a mensagem do paciente, conversa com a
 * IA (Claude), executa as ferramentas (agenda, transferir para humano) e
 * devolve o texto da resposta.
 *
 * O histórico de cada telefone fica em dados/conversa_<telefone>.json e é
 * sempre ACRESCENTADO (nunca editado), como a API exige para manter o
 * raciocínio da IA válido entre as mensagens.
 */
class Secretaria
{
    private const MAX_RODADAS_FERRAMENTAS = 8;
    private const MENSAGEM_ERRO = 'Desculpe, estou com uma instabilidade no momento 😕 Pode tentar de novo em alguns minutos? Se for urgente, ligue para a recepção: %s';

    private Client $claude;
    private Agenda $agenda;
    private \DateTimeZone $fuso;
    private array $clinica;

    public function __construct(private array $config, private Armazenamento $armazenamento, private string $pastaClinica)
    {
        $this->fuso = new \DateTimeZone($config['fuso_horario'] ?? 'America/Sao_Paulo');
        $this->clinica = json_decode((string) file_get_contents($pastaClinica . '/clinica.json'), true)
            ?? throw new \RuntimeException('clinica/clinica.json inválido');
        $this->agenda = new Agenda($armazenamento, $this->clinica, $this->fuso);

        $this->claude = new Client(
            apiKey: $config['anthropic_api_key'] ?: null,
            baseUrl: $config['anthropic_base_url'] ?? null,
            requestOptions: ['timeout' => 90, 'maxRetries' => 2],
        );
    }

    /**
     * Responde uma mensagem de texto do paciente.
     * @return string Texto a ser enviado de volta pelo WhatsApp
     */
    public function responder(string $telefone, string $nomeContato, string $texto): string
    {
        return $this->armazenamento->comTrava('conversa_' . $telefone, function () use ($telefone, $nomeContato, $texto) {
            $conversa = $this->carregarConversa($telefone, $nomeContato);
            $mensagens = $conversa['mensagens'];

            $agora = new \DateTimeImmutable('now', $this->fuso);
            $mensagens[] = [
                'role' => 'user',
                'content' => [[
                    'type' => 'text',
                    'text' => '[' . $this->dataPorExtenso($agora) . "]\n" . $texto,
                ]],
            ];

            try {
                $resposta = $this->conversarComIA($conversa['system'], $mensagens, $telefone);
            } catch (\Throwable $e) {
                // Não salva nada desta rodada: o histórico continua como estava
                $this->armazenamento->registrarLog("ERRO IA ({$telefone}): " . get_class($e) . ': ' . $e->getMessage());
                return sprintf(self::MENSAGEM_ERRO, $this->clinica['telefone_recepcao'] ?? '');
            }

            $conversa['mensagens'] = $mensagens;
            $conversa['atualizada_em'] = $agora->format('c');
            $this->armazenamento->salvar('conversa_' . $telefone, $conversa);

            return $resposta;
        });
    }

    /** Apaga a conversa de um telefone (usado pelo simulador). */
    public function reiniciarConversa(string $telefone): void
    {
        $this->arquivarConversa($telefone);
    }

    private function conversarComIA(string $system, array &$mensagens, string $telefone): string
    {
        for ($rodada = 0; $rodada < self::MAX_RODADAS_FERRAMENTAS; $rodada++) {
            $resposta = $this->chamarClaude($system, $mensagens);

            // Guarda a resposta da IA exatamente como veio (inclui blocos de raciocínio)
            $mensagens[] = ['role' => 'assistant', 'content' => $resposta->content];

            if ($resposta->stopReason === 'refusal') {
                $this->armazenamento->registrarLog("RECUSA ({$telefone}): " . json_encode($resposta->stopDetails));
                return 'Desculpe, não consigo ajudar com isso por aqui. Vou pedir para alguém da nossa equipe falar com você. 🙏';
            }

            if ($resposta->stopReason !== 'tool_use') {
                $texto = $this->extrairTexto($resposta->content);
                return $texto !== '' ? $texto : 'Desculpe, pode repetir, por favor?';
            }

            // A IA pediu para usar ferramentas: executa todas e devolve os resultados juntos
            $resultados = [];
            foreach ($resposta->content as $bloco) {
                if ($bloco->type !== 'tool_use') {
                    continue;
                }
                $saida = $this->executarFerramenta($bloco->name, (array) $bloco->input, $telefone);
                $this->armazenamento->registrarLog("FERRAMENTA ({$telefone}) {$bloco->name} " . json_encode($bloco->input, JSON_UNESCAPED_UNICODE) . ' => ' . json_encode($saida, JSON_UNESCAPED_UNICODE));
                $resultados[] = [
                    'type' => 'tool_result',
                    'toolUseID' => $bloco->id,
                    'content' => json_encode($saida, JSON_UNESCAPED_UNICODE),
                    'isError' => isset($saida['erro']),
                ];
            }
            $mensagens[] = ['role' => 'user', 'content' => $resultados];
        }

        throw new \RuntimeException('A IA usou ferramentas demais em uma única resposta.');
    }

    private function chamarClaude(string $system, array $mensagens): \Anthropic\Beta\Messages\BetaMessage
    {
        return $this->claude->beta->messages->create(
            model: $this->config['modelo'] ?? 'claude-opus-5-5',
            maxTokens: 8000,
            system: [['type' => 'text', 'text' => $system]],
            messages: $mensagens,
            tools: Ferramentas::definicoes($this->agenda->servicos()),
            outputConfig: ['effort' => $this->config['esforco'] ?? 'low'],
            // Guarda em cache o início da conversa: as próximas mensagens ficam mais baratas
            cacheControl: ['type' => 'ephemeral'],
            // Se a IA principal recusar por política, a API tenta automaticamente outro modelo
            fallbacks: 'default',
            betas: ['server-side-fallback-2026-07-01'],
        );
    }

    private function executarFerramenta(string $nome, array $entrada, string $telefone): array
    {
        try {
            return match ($nome) {
                'consultar_horarios_livres' => $this->agenda->horariosLivres(
                    (string) ($entrada['data'] ?? ''),
                    (string) ($entrada['servico'] ?? ''),
                ),
                'agendar_consulta' => $this->agenda->agendar(
                    $telefone,
                    (string) ($entrada['nome_paciente'] ?? ''),
                    (string) ($entrada['data'] ?? ''),
                    (string) ($entrada['hora'] ?? ''),
                    (string) ($entrada['servico'] ?? ''),
                    (string) ($entrada['observacoes'] ?? ''),
                ),
                'listar_meus_agendamentos' => $this->agenda->doTelefone($telefone),
                'cancelar_agendamento' => $this->agenda->cancelar($telefone, (string) ($entrada['codigo'] ?? '')),
                'chamar_atendente_humano' => $this->transferirParaHumano($telefone, (string) ($entrada['motivo'] ?? ''), (bool) ($entrada['urgente'] ?? false)),
                default => ['erro' => "Ferramenta desconhecida: {$nome}"],
            };
        } catch (\Throwable $e) {
            $this->armazenamento->registrarLog("ERRO FERRAMENTA {$nome}: " . $e->getMessage());
            return ['erro' => 'Falha interna ao executar a ação. Ofereça encaminhar para a recepção.'];
        }
    }

    private function transferirParaHumano(string $telefone, string $motivo, bool $urgente): array
    {
        $this->armazenamento->atualizar('transferencias', function (array $lista) use ($telefone, $motivo, $urgente) {
            $lista[] = [
                'telefone' => $telefone,
                'motivo' => $motivo,
                'urgente' => $urgente,
                'status' => 'pendente',
                'criado_em' => (new \DateTimeImmutable('now', $this->fuso))->format('c'),
            ];
            return [$lista, null];
        }, []);
        // Aqui você pode avisar a equipe: e-mail, mensagem de WhatsApp para a recepção etc.
        return [
            'sucesso' => true,
            'mensagem' => 'A equipe foi avisada e vai responder neste mesmo WhatsApp em horário comercial.',
            'telefone_recepcao' => $this->clinica['telefone_recepcao'] ?? null,
        ];
    }

    // ---------- Conversa (histórico) ----------

    private function carregarConversa(string $telefone, string $nomeContato): array
    {
        $conversa = $this->armazenamento->ler('conversa_' . $telefone, null);
        $horas = (float) ($this->config['horas_para_nova_conversa'] ?? 12);

        if ($conversa) {
            $ultima = new \DateTimeImmutable($conversa['atualizada_em']);
            $expirou = (time() - $ultima->getTimestamp()) > $horas * 3600;
            if (!$expirou) {
                return $conversa;
            }
            $this->arquivarConversa($telefone);
        }

        // Conversa nova: as instruções ficam "congeladas" até ela terminar.
        // (Se você editar instrucoes.md ou clinica.json, vale para as próximas conversas.)
        return [
            'telefone' => $telefone,
            'nome_contato' => $nomeContato,
            'iniciada_em' => (new \DateTimeImmutable('now', $this->fuso))->format('c'),
            'atualizada_em' => (new \DateTimeImmutable('now', $this->fuso))->format('c'),
            'system' => $this->montarInstrucoes($nomeContato),
            'mensagens' => [],
        ];
    }

    private function arquivarConversa(string $telefone): void
    {
        $atual = $this->armazenamento->caminho('conversa_' . $telefone);
        if (is_file($atual)) {
            @rename($atual, $this->armazenamento->caminho('arquivo_' . $telefone . '_' . date('Ymd_His')));
        }
    }

    private function montarInstrucoes(string $nomeContato): string
    {
        $texto = (string) file_get_contents($this->pastaClinica . '/instrucoes.md');
        $texto = strtr($texto, [
            '{{nome_assistente}}' => $this->clinica['nome_assistente'] ?? 'Assistente',
            '{{nome_clinica}}' => $this->clinica['nome_clinica'] ?? 'clínica',
        ]);

        $info = $this->clinica;
        $texto .= "\n\n## Informações da clínica (fonte oficial)\n```json\n"
            . json_encode($info, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)
            . "\n```\n";

        if ($nomeContato !== '') {
            $texto .= "\nO nome do contato no WhatsApp é \"{$nomeContato}\" (pode não ser o nome do paciente).\n";
        }
        $texto .= "\nCada mensagem do paciente começa com a data e hora em que foi enviada, entre colchetes. Use-a para entender \"hoje\", \"amanhã\", \"sábado\" etc. Datas nas ferramentas usam o formato AAAA-MM-DD.\n";

        return $texto;
    }

    // ---------- Utilidades ----------

    private function extrairTexto(array $conteudo): string
    {
        $partes = [];
        foreach ($conteudo as $bloco) {
            if ($bloco->type === 'text' && trim($bloco->text) !== '') {
                $partes[] = trim($bloco->text);
            }
        }
        return implode("\n\n", $partes);
    }

    private function dataPorExtenso(\DateTimeImmutable $d): string
    {
        $dias = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado'];
        return $d->format('Y-m-d H:i') . ' (' . $dias[(int) $d->format('w')] . ')';
    }
}
