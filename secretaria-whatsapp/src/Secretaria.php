<?php

namespace Secretaria;

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

    private ClaudeApi $claude;
    private Agenda $agenda;
    private \DateTimeZone $fuso;
    private array $clinica;
    private RespostasRapidas $rapidas;

    /** De onde veio a última resposta: 'rapida' (grátis), 'ia' ou 'erro'. */
    public string $ultimaOrigem = '';

    public function __construct(
        private array $config,
        private Armazenamento $armazenamento,
        private string $pastaClinica,
        private bool $simulacao = false, // true: teste da equipe, não grava agenda nem estatísticas
    ) {
        $this->fuso = new \DateTimeZone($config['fuso_horario'] ?? 'America/Sao_Paulo');
        $this->clinica = Clinica::carregar($armazenamento, $pastaClinica);
        $this->agenda = new Agenda($armazenamento, $this->clinica, $this->fuso, $simulacao);
        $this->rapidas = new RespostasRapidas($armazenamento, $this->clinica, $pastaClinica . '/respostas_rapidas.json');

        $this->claude = new ClaudeApi((string) ($config['anthropic_api_key'] ?? ''), $config['anthropic_base_url'] ?? null, 90);
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

            // 1) Pergunta conhecida? Responde sem chamar a IA (custo zero)
            $rapida = ($this->config['respostas_rapidas'] ?? true) ? $this->rapidas->procurar($texto) : null;
            if ($rapida) {
                $resposta = $rapida['resposta'];
                // Entra no histórico para a IA saber o que já foi dito, caso seja chamada depois
                $mensagens[] = ['role' => 'assistant', 'content' => [['type' => 'text', 'text' => $resposta]]];
                $this->ultimaOrigem = 'rapida';
                $this->simulacao || $this->rapidas->contar('rapida');
                $this->armazenamento->registrarLog("RESPOSTA RAPIDA ({$telefone}) [{$rapida['id']}]");
            } else {
                // 2) Não achou: chama a IA (Haiku primeiro; o Sonnet assume se ele não der conta)
                try {
                    $resposta = $this->responderComEscalonamento($conversa, $mensagens, $telefone, $texto);
                } catch (\Throwable $e) {
                    // Não salva nada desta rodada: o histórico continua como estava
                    $this->ultimaOrigem = 'erro';
                    $this->armazenamento->registrarLog("ERRO IA ({$telefone}): " . get_class($e) . ': ' . $e->getMessage());
                    return sprintf(self::MENSAGEM_ERRO, $this->clinica['telefone_recepcao'] ?? '');
                }
                $this->ultimaOrigem = ($conversa['modo_avancado'] ?? false) ? 'ia_avancada' : 'ia';
                if (!$this->simulacao) {
                    $this->rapidas->contar('ia');
                    if ($this->ultimaOrigem === 'ia_avancada') {
                        $this->rapidas->contar('ia_avancada');
                    }
                    $this->rapidas->anotarPergunta($texto, $resposta);
                }
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

    /** Sinais de que o paciente está frustrado ou o caso é delicado: vai direto para o modelo avançado. */
    private const SINAIS_FRUSTRACAO = [
        'nao entendeu', 'nao entende', 'nao esta entendendo', 'ja falei', 'ja disse', 'ja expliquei', 'de novo isso',
        'robo', 'reclamacao', 'reclamar', 'absurdo', 'pessimo', 'horrivel', 'ridiculo', 'nao resolve', 'nao ajudou',
        'falar com alguem', 'falar com uma pessoa', 'falar com humano', 'processo', 'procon',
    ];

    /**
     * Usa o modelo básico (Haiku). Se ele pedir ajuda, falhar ou o paciente
     * estiver frustrado, o modelo avançado (Sonnet) assume e fica até o fim
     * desta conversa.
     * @return string Texto da resposta
     */
    private function responderComEscalonamento(array &$conversa, array &$mensagens, string $telefone, string $texto): string
    {
        $basico = $this->config['modelo'] ?? 'claude-haiku-5-5';
        $avancado = $this->config['modelo_avancado'] ?? '';
        $podeEscalar = $avancado !== '' && $avancado !== $basico;

        $usarAvancado = $podeEscalar && (($conversa['modo_avancado'] ?? false) || $this->temSinalDeFrustracao($texto));

        if (!$usarAvancado) {
            $antes = $mensagens;
            try {
                return $this->conversarComIA($conversa['system'], $mensagens, $telefone, $basico, $podeEscalar);
            } catch (\Throwable $e) {
                if (!$podeEscalar) {
                    throw $e;
                }
                // Desfaz só a tentativa desta mensagem e passa para o modelo avançado
                $mensagens = $antes;
                $this->armazenamento->registrarLog("ESCALONOU ({$telefone}) para {$avancado}: " . $e->getMessage());
            }
        } else {
            $this->armazenamento->registrarLog("MODELO AVANCADO ({$telefone}): " . (($conversa['modo_avancado'] ?? false) ? 'conversa já escalonada' : 'sinal de frustração'));
        }

        $conversa['modo_avancado'] = true;
        return $this->conversarComIA($conversa['system'], $mensagens, $telefone, $avancado, false);
    }

    private function temSinalDeFrustracao(string $texto): bool
    {
        $t = ' ' . RespostasRapidas::normalizar($texto) . ' ';
        foreach (self::SINAIS_FRUSTRACAO as $s) {
            if (str_contains($t, ' ' . $s)) {
                return true;
            }
        }
        return false;
    }

    private function conversarComIA(string $system, array &$mensagens, string $telefone, string $modelo, bool $podeEscalar): string
    {
        for ($rodada = 0; $rodada < self::MAX_RODADAS_FERRAMENTAS; $rodada++) {
            $resposta = $this->chamarClaude($system, $mensagens, $modelo);

            // Guarda a resposta da IA exatamente como veio (inclui blocos de raciocínio)
            $mensagens[] = ['role' => 'assistant', 'content' => $resposta['content']];

            if (($resposta['stop_reason'] ?? '') === 'refusal') {
                $this->armazenamento->registrarLog("RECUSA ({$telefone}, {$modelo}): " . json_encode($resposta['stop_details'] ?? null));
                if ($podeEscalar) {
                    throw new Escalonamento('recusa do modelo básico');
                }
                return 'Desculpe, não consigo ajudar com isso por aqui. Vou pedir para alguém da nossa equipe falar com você. 🙏';
            }

            if (($resposta['stop_reason'] ?? '') !== 'tool_use') {
                $texto = $this->extrairTexto($resposta['content']);
                if ($texto === '' && $podeEscalar) {
                    throw new Escalonamento('resposta vazia');
                }
                return $texto !== '' ? $texto : 'Desculpe, pode repetir, por favor?';
            }

            foreach ($resposta['content'] as $bloco) {
                if (($bloco['type'] ?? '') === 'tool_use' && $bloco['name'] === 'pedir_ajuda_especialista' && $podeEscalar) {
                    throw new Escalonamento('o modelo básico pediu ajuda: ' . (string) (($bloco['input'] ?? [])['motivo'] ?? ''));
                }
            }

            // A IA pediu para usar ferramentas: executa todas e devolve os resultados juntos
            $resultados = [];
            foreach ($resposta['content'] as $bloco) {
                if (($bloco['type'] ?? '') !== 'tool_use') {
                    continue;
                }
                $entrada = (array) ($bloco['input'] ?? []);
                $saida = $bloco['name'] === 'pedir_ajuda_especialista'
                    ? ['resultado' => 'Você já é o atendimento avançado. Resolva com cuidado ou use chamar_atendente_humano.']
                    : $this->executarFerramenta($bloco['name'], $entrada, $telefone);
                $this->armazenamento->registrarLog("FERRAMENTA ({$telefone}) {$bloco['name']} " . json_encode($entrada, JSON_UNESCAPED_UNICODE) . ' => ' . json_encode($saida, JSON_UNESCAPED_UNICODE));
                $resultados[] = [
                    'type' => 'tool_result',
                    'tool_use_id' => $bloco['id'],
                    'content' => json_encode($saida, JSON_UNESCAPED_UNICODE),
                    'is_error' => isset($saida['erro']),
                ];
            }
            $mensagens[] = ['role' => 'user', 'content' => $resultados];
        }

        throw new \RuntimeException('A IA usou ferramentas demais em uma única resposta.');
    }

    private function chamarClaude(string $system, array $mensagens, string $modelo): array
    {
        return $this->claude->mensagem([
            'model' => $modelo,
            'max_tokens' => 8000,
            'system' => [['type' => 'text', 'text' => $system]],
            'messages' => $mensagens,
            'tools' => Ferramentas::definicoes($this->agenda->servicos()),
            'output_config' => ['effort' => $this->config['esforco'] ?? 'low'],
            // Guarda em cache o início da conversa: as próximas mensagens ficam mais baratas
            'cache_control' => ['type' => 'ephemeral'],
            // Se a IA principal recusar por política, a API tenta automaticamente outro modelo
            'fallbacks' => 'default',
        ], ['server-side-fallback-2026-07-01']);
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
        if ($this->simulacao) {
            return ['sucesso' => true, 'mensagem' => 'SIMULAÇÃO: a equipe seria avisada.', 'telefone_recepcao' => $this->clinica['telefone_recepcao'] ?? null];
        }
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

        // Regras escritas pela clínica no cadastro (cadastro.html)
        $extras = $this->clinica['regras_extras'] ?? [];
        $equipe = $this->clinica['equipe'] ?? [];
        $linhas = array_filter([
            !empty($extras['tratamento']) ? "- Forma de tratar o paciente: {$extras['tratamento']}" : '',
            !empty($extras['emoji']) ? "- Uso de emoji: {$extras['emoji']}" : '',
            !empty($extras['frases_da_clinica']) ? "- Frases/saudações que a clínica usa: {$extras['frases_da_clinica']}" : '',
            !empty($extras['proibido']) ? "- NÃO fale sobre / NÃO faça: {$extras['proibido']}" : '',
            !empty($extras['sempre_humano']) ? "- Estes assuntos vão SEMPRE para um atendente humano (use chamar_atendente_humano): {$extras['sempre_humano']}" : '',
            !empty($equipe['horario_resposta']) ? "- A equipe humana responde: {$equipe['horario_resposta']}. Informe isso ao transferir." : '',
        ]);
        $naoAgendar = array_column(array_filter($this->clinica['servicos'] ?? [], fn ($s) => !($s['agendar_pela_ia'] ?? true)), 'nome');
        if ($naoAgendar) {
            $linhas[] = '- NÃO agende estes serviços; explique que precisam de avaliação e chame chamar_atendente_humano: ' . implode(', ', $naoAgendar);
        }
        if ($linhas) {
            $texto .= "\n\n## Regras específicas desta clínica (têm prioridade sobre o estilo padrão)\n" . implode("\n", $linhas) . "\n";
        }

        $texto .= (new Regras($this->armazenamento))->paraInstrucoes();

        $info = $this->clinica;
        unset($info['regras_extras'], $info['equipe']);
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
            if (($bloco['type'] ?? '') === 'text' && trim((string) ($bloco['text'] ?? '')) !== '') {
                $partes[] = trim($bloco['text']);
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
