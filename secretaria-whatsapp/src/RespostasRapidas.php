<?php

namespace Secretaria;

/**
 * Respostas prontas para perguntas frequentes: respondem sem chamar a IA
 * (custo zero). Também anota as perguntas que a IA respondeu, para você
 * aprovar as mais frequentes como novas respostas rápidas no painel.
 */
class RespostasRapidas
{
    /** Mensagens com estas palavras sempre vão para a IA (precisam de ação ou cuidado). */
    private const SEMPRE_IA = [
        'marcar', 'agendar', 'agenda', 'remarcar', 'desmarcar', 'cancelar', 'cancela', 'reagendar', 'horarios livres',
        'vaga', 'disponivel', 'disponibilidade', 'amanha', 'hoje', 'dia ', 'falar com', 'atendente', 'humano',
        'dor', 'urgente', 'urgencia', 'emergencia', 'sangr', 'febre', 'desmai', 'falta de ar', 'remedio', 'exame', 'resultado',
        'reclama', 'problema',
    ];
    private const MAX_PALAVRAS_CONTEM = 12;
    private const MIN_PALAVRAS_APRENDER = 3;
    private const MAX_PALAVRAS_APRENDER = 20;

    public function __construct(
        private Armazenamento $armazenamento,
        private array $clinica,
        private string $arquivoInicial,
    ) {
    }

    /** Normaliza: minúsculas, sem acentos, sem pontuação, espaços simples. */
    public static function normalizar(string $texto): string
    {
        $t = mb_strtolower(trim($texto));
        $t = strtr($t, [
            'á' => 'a', 'à' => 'a', 'â' => 'a', 'ã' => 'a', 'ä' => 'a', 'é' => 'e', 'ê' => 'e', 'è' => 'e', 'ë' => 'e',
            'í' => 'i', 'ì' => 'i', 'î' => 'i', 'ï' => 'i', 'ó' => 'o', 'ô' => 'o', 'õ' => 'o', 'ò' => 'o', 'ö' => 'o',
            'ú' => 'u', 'ù' => 'u', 'û' => 'u', 'ü' => 'u', 'ç' => 'c', 'ñ' => 'n',
        ]);
        $t = preg_replace('/[^a-z0-9 ]+/', ' ', $t);
        return trim(preg_replace('/\s+/', ' ', $t));
    }

    /** A mensagem (já normalizada) fala de algo que sempre precisa da IA? */
    private static function exigeIa(string $msg): bool
    {
        foreach (self::SEMPRE_IA as $p) {
            if (str_contains(' ' . $msg . ' ', ' ' . $p)) {
                return true;
            }
        }
        return false;
    }

    public function todas(): array
    {
        $dados = $this->armazenamento->ler('respostas_rapidas', null);
        if ($dados === null) {
            // Primeira vez: copia as respostas iniciais de clinica/respostas_rapidas.json
            $inicial = json_decode((string) @file_get_contents($this->arquivoInicial), true);
            $dados = $inicial['respostas'] ?? [];
            $this->armazenamento->salvar('respostas_rapidas', $dados);
        }
        return $dados;
    }

    /**
     * Procura uma resposta pronta para a mensagem.
     * @return array{id:string, resposta:string}|null
     */
    public function procurar(string $mensagem): ?array
    {
        $msg = self::normalizar($mensagem);
        if ($msg === '') {
            return null;
        }
        $palavras = count(explode(' ', $msg));

        $exigeIa = self::exigeIa($msg);

        foreach ($this->todas() as $r) {
            if (!($r['ativo'] ?? true)) {
                continue;
            }
            $modo = $r['modo'] ?? 'contem';
            foreach ($r['gatilhos'] ?? [] as $g) {
                $g = self::normalizar($g);
                if ($g === '') {
                    continue;
                }
                $bate = $modo === 'exato'
                    ? $msg === $g
                    : (!$exigeIa && $palavras <= self::MAX_PALAVRAS_CONTEM && str_contains(' ' . $msg . ' ', ' ' . $g . ' '));
                if ($bate) {
                    // Pergunta de preço que cita UM serviço: responde só sobre ele
                    if ($r['id'] === 'precos' && ($s = $this->servicoCitado($msg))) {
                        return ['id' => 'precos', 'resposta' => $this->respostaServico($s)];
                    }
                    return ['id' => (string) $r['id'], 'resposta' => $this->preencher((string) $r['resposta'])];
                }
            }
        }
        return null;
    }

    /** Se a mensagem cita exatamente um serviço (por uma palavra marcante do nome), retorna esse serviço. */
    private function servicoCitado(string $msg): ?array
    {
        $genericas = ['consulta', 'retorno', 'sessao', 'avaliacao', 'atendimento', 'exame', 'procedimento'];
        $achados = [];
        foreach ($this->clinica['servicos'] ?? [] as $s) {
            foreach (explode(' ', self::normalizar($s['nome'] ?? '')) as $p) {
                if (strlen($p) >= 5 && !in_array($p, $genericas, true) && str_contains(' ' . $msg . ' ', ' ' . $p)) {
                    $achados[$s['nome']] = $s;
                    break;
                }
            }
        }
        return count($achados) === 1 ? reset($achados) : null;
    }

    private function respostaServico(array $s): string
    {
        $dur = (int) ($s['duracao_minutos'] ?? 0);
        $durTxt = $dur >= 60 ? (intdiv($dur, 60) . 'h' . ($dur % 60 ? $dur % 60 : '')) : "{$dur} min";
        $t = "*{$s['nome']}*: *{$s['preco']}*" . ($dur ? " (duração: {$durTxt})" : '') . '.';
        if (!empty($s['observacoes'])) {
            $t .= "\n{$s['observacoes']}";
        }
        if (!empty($s['preparo'])) {
            $t .= "\nPreparo: {$s['preparo']}";
        }
        if (!empty($this->clinica['formas_pagamento'])) {
            $t .= "\n\nPagamento: " . implode(', ', $this->clinica['formas_pagamento']) . '.';
        }
        $t .= ($s['agendar_pela_ia'] ?? true) ? ' Quer agendar?' : "\n\nEsse serviço precisa de avaliação. Posso pedir para nossa equipe falar com você?";
        return $t;
    }

    /** Troca {{campo}} pelos dados atuais de clinica.json. */
    public function preencher(string $texto): string
    {
        $c = $this->clinica;
        $dias = ['segunda' => 'Segunda', 'terca' => 'Terça', 'quarta' => 'Quarta', 'quinta' => 'Quinta', 'sexta' => 'Sexta', 'sabado' => 'Sábado', 'domingo' => 'Domingo'];
        $horarios = [];
        foreach ($dias as $chave => $nome) {
            $p = $c['horario_funcionamento'][$chave] ?? [];
            $horarios[] = "• {$nome}: " . ($p ? str_replace('-', ' às ', implode(' e ', $p)) : 'fechado');
        }
        $servicos = array_map(fn ($s) => "• {$s['nome']}: *{$s['preco']}*", $c['servicos'] ?? []);

        $valores = [
            '{{nome_assistente}}' => $c['nome_assistente'] ?? '',
            '{{nome_clinica}}' => $c['nome_clinica'] ?? '',
            '{{endereco}}' => $c['endereco'] ?? '',
            '{{como_chegar}}' => $c['como_chegar'] ?? '',
            '{{telefone_recepcao}}' => $c['telefone_recepcao'] ?? '',
            '{{horarios}}' => implode("\n", $horarios),
            '{{servicos_precos}}' => implode("\n", $servicos),
            '{{convenios}}' => implode(', ', $c['convenios'] ?? []),
            '{{formas_pagamento}}' => implode(', ', $c['formas_pagamento'] ?? []),
        ];
        // Linhas que dependem de um dado ainda não cadastrado são removidas (ex.: "Pagamento: ." vazio)
        $linhas = [];
        foreach (explode("\n", $texto) as $linha) {
            preg_match_all('/\{\{[a-z_]+\}\}/', $linha, $m);
            $vazio = false;
            foreach ($m[0] as $campo) {
                if (isset($valores[$campo]) && trim($valores[$campo]) === '') {
                    $vazio = true;
                }
            }
            if (!$vazio) {
                $linhas[] = strtr($linha, $valores);
            }
        }
        return trim(implode("\n", $linhas));
    }

    /** Anota uma pergunta respondida pela IA (base para o aprendizado). */
    public function anotarPergunta(string $mensagem, string $respostaIa): void
    {
        $chave = self::normalizar($mensagem);
        $n = $chave === '' ? 0 : count(explode(' ', $chave));
        // Ignora frases curtas demais, longas demais e pedidos de ação (agendar, cancelar, urgência...)
        if ($n < self::MIN_PALAVRAS_APRENDER || $n > self::MAX_PALAVRAS_APRENDER || self::exigeIa($chave)) {
            return;
        }
        $this->armazenamento->atualizar('perguntas_frequentes', function (array $lista) use ($chave, $mensagem, $respostaIa) {
            if (isset($lista[$chave]) && ($lista[$chave]['ignorada'] ?? false)) {
                return [$lista, null];
            }
            $item = $lista[$chave] ?? ['pergunta' => $mensagem, 'vezes' => 0, 'primeira_vez' => date('c')];
            $item['vezes']++;
            $item['ultima_vez'] = date('c');
            $item['ultima_resposta_ia'] = $respostaIa;
            $lista[$chave] = $item;
            // Guarda no máximo 500 perguntas (descarta as menos frequentes)
            if (count($lista) > 500) {
                uasort($lista, fn ($a, $b) => $b['vezes'] <=> $a['vezes']);
                $lista = array_slice($lista, 0, 500, true);
            }
            return [$lista, null];
        }, []);
    }

    public function contar(string $origem): void
    {
        $this->armazenamento->atualizar('estatisticas', function (array $e) use ($origem) {
            $mes = date('Y-m');
            $e[$mes][$origem] = ($e[$mes][$origem] ?? 0) + 1;
            return [$e, null];
        }, []);
    }
}
