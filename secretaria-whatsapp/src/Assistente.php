<?php

namespace Secretaria;

use Anthropic\Client;

/**
 * Chat de configuração: as donas da clínica conversam com o Claude, que
 * entrevista, tira dúvidas, salva o cadastro e testa a secretária.
 * É uma conversa ÚNICA e compartilhada: todos que entram veem tudo.
 */
class Assistente
{
    private const MAX_RODADAS = 10;
    private const ARQUIVO = 'assistente_conversa';

    private Client $claude;

    public function __construct(
        private array $config,
        private Armazenamento $armazenamento,
        private string $pastaClinica,
    ) {
        $this->claude = new Client(
            apiKey: $config['anthropic_api_key'] ?: null,
            baseUrl: $config['anthropic_base_url'] ?? null,
            requestOptions: ['timeout' => 180, 'maxRetries' => 2],
        );
    }

    // ---------- Conversa compartilhada ----------

    private function carregar(): array
    {
        return $this->armazenamento->ler(self::ARQUIVO, null) ?? [
            'criada_em' => date('c'),
            'system' => $this->instrucoes(),
            'mensagens' => [],   // formato da API (só cresce, nunca é editado)
            'exibicao' => [],    // o que aparece na tela
            'ocupado' => null,
        ];
    }

    /** Itens da tela a partir da posição $desde, e se o Claude está respondendo. */
    public function historico(int $desde = 0): array
    {
        $c = $this->carregar();
        $ocupado = $c['ocupado'] ?? null;
        if ($ocupado && strtotime($ocupado['desde']) < time() - 300) {
            $ocupado = null; // trava esquecida
        }
        return [
            'itens' => array_slice($c['exibicao'], $desde),
            'total' => count($c['exibicao']),
            'ocupado' => $ocupado,
        ];
    }

    public function novaConversa(): void
    {
        $this->armazenamento->comTrava(self::ARQUIVO, function () {
            $atual = $this->armazenamento->caminho(self::ARQUIVO);
            if (is_file($atual)) {
                @rename($atual, $this->armazenamento->caminho('assistente_arquivo_' . date('Ymd_His')));
            }
        });
    }

    /** Recebe a mensagem de uma pessoa e devolve os novos itens da tela. */
    public function enviar(string $autor, string $texto): array
    {
        // Marca "Claude digitando" para as outras pessoas verem
        $this->armazenamento->atualizar(self::ARQUIVO, function ($c) use ($autor) {
            $c = $c ?: $this->carregar();
            $c['ocupado'] = ['quem' => $autor, 'desde' => date('c')];
            return [$c, null];
        }, []);

        try {
            return $this->armazenamento->comTrava(self::ARQUIVO . '_proc', function () use ($autor, $texto) {
                $c = $this->carregar();
                $inicio = count($c['exibicao']);
                $agora = date('Y-m-d H:i');

                $c['exibicao'][] = ['tipo' => 'pessoa', 'autor' => $autor, 'texto' => $texto, 'em' => date('c')];
                $mensagens = $c['mensagens'];
                $mensagens[] = ['role' => 'user', 'content' => [['type' => 'text', 'text' => "[{$autor} · {$agora}]\n{$texto}"]]];

                try {
                    [$resposta, $acoes] = $this->rodarClaude($c['system'], $mensagens);
                    foreach ($acoes as $a) {
                        $c['exibicao'][] = ['tipo' => 'acao', 'texto' => $a, 'em' => date('c')];
                    }
                    $c['exibicao'][] = ['tipo' => 'claude', 'autor' => 'Claude', 'texto' => $resposta, 'em' => date('c')];
                    $c['mensagens'] = $mensagens;
                } catch (\Throwable $e) {
                    $this->armazenamento->registrarLog('ERRO ASSISTENTE: ' . get_class($e) . ': ' . $e->getMessage());
                    $c['exibicao'][] = ['tipo' => 'erro', 'texto' => 'Não consegui responder agora (falha ao falar com a IA). Tente de novo em instantes. Se continuar, confira a chave e os créditos da Anthropic.', 'em' => date('c')];
                    // A pergunta não entra no histórico da IA; quem quiser pode reenviar
                }

                $c['ocupado'] = null;
                $this->armazenamento->salvar(self::ARQUIVO, $c);
                return array_slice($c['exibicao'], $inicio);
            });
        } finally {
            $this->armazenamento->atualizar(self::ARQUIVO, function ($c) {
                if ($c) {
                    $c['ocupado'] = null;
                }
                return [$c ?: [], null];
            }, []);
        }
    }

    // ---------- IA ----------

    private function rodarClaude(string $system, array &$mensagens): array
    {
        $acoes = [];
        for ($i = 0; $i < self::MAX_RODADAS; $i++) {
            $r = $this->claude->beta->messages->create(
                model: $this->config['modelo'] ?? 'claude-opus-5-5',
                maxTokens: 16000,
                system: [['type' => 'text', 'text' => $system]],
                messages: $mensagens,
                tools: $this->ferramentas(),
                outputConfig: ['effort' => $this->config['esforco_assistente'] ?? 'medium'],
                cacheControl: ['type' => 'ephemeral'],
                fallbacks: 'default',
                betas: ['server-side-fallback-2026-07-01'],
            );
            $mensagens[] = ['role' => 'assistant', 'content' => $r->content];

            if ($r->stopReason === 'refusal') {
                return ['Não consigo ajudar com esse pedido. Podemos seguir com o cadastro da clínica?', $acoes];
            }
            if ($r->stopReason !== 'tool_use') {
                $texto = [];
                foreach ($r->content as $b) {
                    if ($b->type === 'text' && trim($b->text) !== '') {
                        $texto[] = trim($b->text);
                    }
                }
                return [$texto ? implode("\n\n", $texto) : '(sem resposta)', $acoes];
            }

            $resultados = [];
            foreach ($r->content as $b) {
                if ($b->type !== 'tool_use') {
                    continue;
                }
                [$saida, $acao] = $this->executar($b->name, (array) $b->input);
                if ($acao) {
                    $acoes[] = $acao;
                }
                $resultados[] = [
                    'type' => 'tool_result',
                    'toolUseID' => $b->id,
                    'content' => json_encode($saida, JSON_UNESCAPED_UNICODE),
                    'isError' => isset($saida['erro']),
                ];
            }
            $mensagens[] = ['role' => 'user', 'content' => $resultados];
        }
        throw new \RuntimeException('Muitas rodadas de ferramentas.');
    }

    /** @return array{0: array, 1: ?string} [resultado para a IA, texto da ação para a tela] */
    private function executar(string $nome, array $in): array
    {
        try {
            switch ($nome) {
                case 'ver_cadastro':
                    $cadastrada = Clinica::cadastrada($this->armazenamento);
                    $dados = $cadastrada ? Clinica::carregar($this->armazenamento, $this->pastaClinica) : [];
                    [, , $faltando] = Clinica::validar($dados);
                    return [[
                        'situacao' => $cadastrada ? 'cadastro em andamento/salvo' : 'NADA cadastrado ainda (a secretária está usando uma clínica de EXEMPLO)',
                        'faltando_obrigatorio' => $faltando,
                        'dados' => $dados,
                        'pendencias_para_desenvolvedor' => array_column($this->armazenamento->ler('pendencias', []), 'texto'),
                    ], null];

                case 'atualizar_cadastro':
                    $alteracoes = (array) ($in['alteracoes'] ?? []);
                    if (!$alteracoes) {
                        return [['erro' => 'Nenhuma alteração enviada.'], null];
                    }
                    $atual = Clinica::cadastrada($this->armazenamento) ? Clinica::carregar($this->armazenamento, $this->pastaClinica) : [];
                    [$dados, $erros, $faltando] = Clinica::validar(Clinica::mesclar($atual, json_decode(json_encode($alteracoes), true)));
                    if ($erros) {
                        return [['erro' => 'Nada foi salvo. Corrija: ' . implode(' ', $erros)], null];
                    }
                    Clinica::salvar($this->armazenamento, $dados, $this->pastaClinica, 'chat');
                    $partes = implode(', ', array_map(fn ($k) => str_replace('_', ' ', $k), array_keys($alteracoes)));
                    return [[
                        'sucesso' => true,
                        'salvo' => array_intersect_key($dados, $alteracoes),
                        'ainda_faltando_obrigatorio' => $faltando,
                    ], "✓ Cadastro atualizado: {$partes}"];

                case 'testar_secretaria':
                    $msg = trim((string) ($in['mensagem_do_paciente'] ?? ''));
                    $sec = new Secretaria($this->config, $this->armazenamento, $this->pastaClinica, true);
                    $sec->reiniciarConversa('simulacao_equipe');
                    $resp = $sec->responder('simulacao_equipe', 'Paciente (teste)', $msg);
                    $sec->reiniciarConversa('simulacao_equipe');
                    $origem = $sec->ultimaOrigem === 'rapida' ? 'resposta rápida (grátis)' : 'IA';
                    return [['resposta_da_secretaria' => $resp, 'origem' => $origem],
                        "🧪 Teste: paciente diz \"{$msg}\" → secretária ({$origem}): " . $resp];

                case 'anotar_para_desenvolvedor':
                    $texto = trim((string) ($in['texto'] ?? ''));
                    $this->armazenamento->atualizar('pendencias', function (array $l) use ($texto) {
                        $l[] = ['texto' => $texto, 'em' => date('c')];
                        return [$l, null];
                    }, []);
                    return [['sucesso' => true], "📝 Anotado para o desenvolvedor: {$texto}"];
            }
            return [['erro' => "Ferramenta desconhecida: {$nome}"], null];
        } catch (\Throwable $e) {
            $this->armazenamento->registrarLog("ERRO FERRAMENTA ASSISTENTE {$nome}: " . $e->getMessage());
            return [['erro' => 'Falha interna: ' . $e->getMessage()], null];
        }
    }

    private function ferramentas(): array
    {
        return [
            [
                'name' => 'ver_cadastro',
                'description' => 'Mostra tudo o que já está cadastrado sobre a clínica, o que falta de obrigatório e as pendências anotadas para o desenvolvedor. Use no início e sempre que precisar conferir.',
                'inputSchema' => ['type' => 'object', 'properties' => new \stdClass()],
            ],
            [
                'name' => 'atualizar_cadastro',
                'description' => 'Salva informações da clínica. Envie só os campos que mudam. Campos de LISTA (servicos, profissionais, convenios, formas_pagamento, perguntas_frequentes, feriados_e_folgas) substituem a lista anterior inteira: envie a lista completa. Campos de OBJETO (horario_funcionamento, politicas, regras_extras, equipe) são mesclados: envie só as chaves que mudam. Só salve o que as pessoas disseram ou confirmaram.',
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => [
                        'alteracoes' => [
                            'type' => 'object',
                            'description' => 'Campos a salvar',
                            'properties' => [
                                'nome_clinica' => ['type' => 'string'],
                                'nome_assistente' => ['type' => 'string', 'description' => 'Nome da secretária virtual do WhatsApp'],
                                'especialidade' => ['type' => 'string'],
                                'endereco' => ['type' => 'string'],
                                'como_chegar' => ['type' => 'string'],
                                'estacionamento' => ['type' => 'string'],
                                'telefone_recepcao' => ['type' => 'string'],
                                'site_instagram' => ['type' => 'string'],
                                'horario_funcionamento' => [
                                    'type' => 'object',
                                    'description' => 'Chaves: segunda, terca, quarta, quinta, sexta, sabado, domingo. Valor: lista de períodos "HH:MM-HH:MM" (vazia = fechado). Ex.: {"segunda": ["08:00-12:00", "13:30-18:00"]}',
                                ],
                                'feriados_e_folgas' => ['type' => 'array', 'items' => ['type' => 'string'], 'description' => 'Datas AAAA-MM-DD'],
                                'servicos' => [
                                    'type' => 'array',
                                    'items' => [
                                        'type' => 'object',
                                        'properties' => [
                                            'nome' => ['type' => 'string'],
                                            'preco' => ['type' => 'string', 'description' => 'Como foi dito, ex.: "R$ 250,00" ou "Consultar"'],
                                            'duracao_minutos' => ['type' => 'integer'],
                                            'profissional' => ['type' => 'string'],
                                            'preparo' => ['type' => 'string'],
                                            'observacoes' => ['type' => 'string', 'description' => 'Informação que PODE ser dita ao paciente (ex.: "retorno grátis em 30 dias"). Não coloque instruções internas aqui; para isso use agendar_pela_ia e regras_extras.'],
                                            'agendar_pela_ia' => ['type' => 'boolean', 'description' => 'false = a secretária não agenda, encaminha para a equipe'],
                                        ],
                                        'required' => ['nome'],
                                    ],
                                ],
                                'profissionais' => [
                                    'type' => 'array',
                                    'items' => ['type' => 'object', 'properties' => [
                                        'nome' => ['type' => 'string'], 'especialidade' => ['type' => 'string'], 'dias_horarios' => ['type' => 'string'],
                                    ], 'required' => ['nome']],
                                ],
                                'convenios' => ['type' => 'array', 'items' => ['type' => 'string']],
                                'convenios_observacoes' => ['type' => 'string'],
                                'formas_pagamento' => ['type' => 'array', 'items' => ['type' => 'string']],
                                'sinal_antecipado' => ['type' => 'string'],
                                'antecedencia_minima_horas' => ['type' => 'integer'],
                                'dias_para_frente_agenda' => ['type' => 'integer'],
                                'politicas' => [
                                    'type' => 'object',
                                    'description' => 'Chaves: retorno, encaixe, cancelamento, atraso, criancas, documentos_primeira_consulta (textos).',
                                ],
                                'perguntas_frequentes' => [
                                    'type' => 'array',
                                    'items' => ['type' => 'object', 'properties' => [
                                        'pergunta' => ['type' => 'string'],
                                        'resposta' => ['type' => 'string', 'description' => 'Resposta pronta, no tom de WhatsApp'],
                                        'palavras_chave' => ['type' => 'array', 'items' => ['type' => 'string'], 'description' => 'Trechos curtos que identificam a pergunta (ex.: "limpeza de pele"). Com eles a resposta sai grátis, sem IA. Evite palavras genéricas.'],
                                    ], 'required' => ['pergunta', 'resposta']],
                                ],
                                'regras_extras' => [
                                    'type' => 'object',
                                    'description' => 'Chaves: tratamento (ex.: "Chamar de o senhor / a senhora"), emoji, frases_da_clinica, proibido (assuntos proibidos), sempre_humano (assuntos que vão sempre para uma pessoa).',
                                ],
                                'equipe' => [
                                    'type' => 'object',
                                    'description' => 'Chaves: responsavel, como_avisar, horario_resposta.',
                                ],
                            ],
                        ],
                    ],
                    'required' => ['alteracoes'],
                ],
            ],
            [
                'name' => 'testar_secretaria',
                'description' => 'Simula uma mensagem de paciente no WhatsApp e retorna o que a secretária responderia com o cadastro atual. Não grava nada na agenda. Use para mostrar o resultado depois de salvar, ou quando pedirem um teste.',
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => ['mensagem_do_paciente' => ['type' => 'string']],
                    'required' => ['mensagem_do_paciente'],
                ],
            ],
            [
                'name' => 'anotar_para_desenvolvedor',
                'description' => 'Anota um pedido que exige mudar o sistema (ex.: agenda separada por profissional, lembretes automáticos, integração com outro sistema, aviso para a recepção) para o desenvolvedor implementar depois.',
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => ['texto' => ['type' => 'string', 'description' => 'O pedido, claro e completo']],
                    'required' => ['texto'],
                ],
            ],
        ];
    }

    private function instrucoes(): string
    {
        return <<<TXT
Você é o Claude, assistente que ajuda as responsáveis por uma clínica a configurar a secretária virtual de WhatsApp da clínica. Quem fala com você são as donas/sócias da clínica (e às vezes o desenvolvedor). Cada mensagem começa com o nome de quem escreveu e a hora, entre colchetes: chame cada pessoa pelo nome. Mais de uma pessoa pode participar da mesma conversa.

## O sistema que você está ajudando a configurar
- Uma secretária virtual atende os pacientes no WhatsApp 24h: tira dúvidas, consulta horários livres, agenda, cancela e chama a equipe humana quando precisa. Em emergência, orienta a ligar 192 (SAMU). Ela nunca dá diagnóstico nem indica remédio.
- Perguntas frequentes com palavras-chave são respondidas sem IA (grátis). O restante usa IA, que é paga por uso.
- Tudo o que a secretária sabe vem do cadastro da clínica, que você lê com ver_cadastro e salva com atualizar_cadastro. Existe também a página cadastro.html, onde dá para revisar e editar em formulário.
- Hoje a agenda é única para a clínica toda (não separa por profissional). Mudanças assim no sistema são anotadas com anotar_para_desenvolvedor.

## O que cadastrar (10 partes)
1. Dados básicos: nome da clínica, nome da secretária virtual, especialidades, endereço, como chegar, estacionamento, telefone da recepção, site/Instagram.
2. Horário de funcionamento de cada dia e feriados/folgas.
3. Serviços: nome, preço particular, duração, quem atende, preparo, observações, se a secretária pode agendar sozinha.
4. Profissionais e seus dias/horários.
5. Convênios (e restrições), formas de pagamento, sinal antecipado.
6. Regras de agendamento: antecedência mínima, até quantos dias à frente, retorno, encaixe, cancelamento, atraso, crianças, documentos.
7. Perguntas frequentes com a resposta certa (e palavras-chave).
8. O que a secretária NÃO deve falar/fazer e o que vai sempre para uma pessoa.
9. Jeito de falar: você ou senhor(a), emojis, frases da clínica.
10. Equipe: quem recebe os pedidos de atendimento humano, como avisar, horário de resposta.

## Como conduzir
- No começo de uma conversa, use ver_cadastro para saber o que já existe e continue de onde parou.
- Vá uma parte por vez, com poucas perguntas por mensagem. Seja caloroso, simples e direto; elas não são técnicas.
- Quando receberem uma informação, resuma o que entendeu e salve com atualizar_cadastro. Se algo estiver ambíguo (ex.: "a tarde toda"), pergunte antes de salvar. Nunca invente preços, horários ou regras.
- Aceite respostas soltas e fora de ordem (ex.: uma lista de preços colada) e encaixe nas partes certas.
- Depois de salvar algo importante, ofereça um teste com testar_secretaria, simulando a pergunta de um paciente, e mostre a resposta.
- Ao montar perguntas frequentes, escreva respostas curtas no tom de WhatsApp e sugira palavras-chave específicas.
- Os campos preço, observações, preparo e respostas das perguntas frequentes podem ser mostrados direto ao paciente: escreva-os como texto para o paciente, nunca como nota interna. Regras internas vão em agendar_pela_ia e regras_extras.
- Se pedirem algo que o sistema ainda não faz, explique com sinceridade e use anotar_para_desenvolvedor.
- Pode usar **negrito** e listas com "- " nas suas mensagens. Escreva em português do Brasil.
- Não dê orientação médica. Não peça dados de pacientes.
TXT;
    }
}
