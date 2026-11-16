<?php

namespace Secretaria;

/**
 * Dados da clínica. O cadastro feito pela página cadastro.html fica em
 * dados/clinica.json; enquanto ele não existir, vale o exemplo de
 * clinica/clinica.json.
 */
class Clinica
{
    public static function carregar(Armazenamento $armazenamento, string $pastaClinica): array
    {
        $cadastrada = $armazenamento->ler('clinica', null);
        if (is_array($cadastrada) && $cadastrada) {
            return $cadastrada;
        }
        return json_decode((string) file_get_contents($pastaClinica . '/clinica.json'), true)
            ?? throw new \RuntimeException('clinica/clinica.json inválido');
    }

    public static function cadastrada(Armazenamento $armazenamento): bool
    {
        return is_array($armazenamento->ler('clinica', null));
    }

    /** Limpa e valida o que veio do formulário. Retorna [dados, erros]. */
    public static function validar(array $e): array
    {
        $erros = [];
        $txt = fn ($v, $max = 500) => mb_substr(trim((string) ($v ?? '')), 0, $max);
        $lista = function ($v, $max = 60) use ($txt) {
            $itens = is_array($v) ? $v : preg_split('/[\n,;]+/', (string) $v);
            return array_values(array_filter(array_map(fn ($i) => $txt($i, 200), $itens), 'strlen'));
        };
        $hora = fn ($h) => preg_match('/^([01]\d|2[0-3]):[0-5]\d$/', (string) $h) ? (string) $h : null;

        $d = [
            'nome_clinica' => $txt($e['nome_clinica'] ?? '', 120),
            'nome_assistente' => $txt($e['nome_assistente'] ?? '', 40) ?: 'Ana',
            'especialidade' => $txt($e['especialidade'] ?? '', 300),
            'endereco' => $txt($e['endereco'] ?? '', 300),
            'como_chegar' => $txt($e['como_chegar'] ?? '', 500),
            'estacionamento' => $txt($e['estacionamento'] ?? '', 300),
            'telefone_recepcao' => $txt($e['telefone_recepcao'] ?? '', 40),
            'site_instagram' => $txt($e['site_instagram'] ?? '', 200),
        ];
        if ($d['nome_clinica'] === '') {
            $erros[] = 'Informe o nome da clínica.';
        }

        // Horários: cada dia com até 2 períodos HH:MM-HH:MM
        $d['horario_funcionamento'] = [];
        foreach (['segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo'] as $dia) {
            $periodos = [];
            foreach ((array) ($e['horario_funcionamento'][$dia] ?? []) as $p) {
                [$ini, $fim] = array_pad(explode('-', (string) $p), 2, '');
                $ini = $hora(trim($ini));
                $fim = $hora(trim($fim));
                if ($ini && $fim && $ini < $fim) {
                    $periodos[] = "{$ini}-{$fim}";
                } elseif (trim((string) $p) !== '') {
                    $erros[] = "Horário inválido em {$dia}: {$p}";
                }
            }
            $d['horario_funcionamento'][$dia] = $periodos;
        }
        $d['feriados_e_folgas'] = array_values(array_filter(
            $lista($e['feriados_e_folgas'] ?? []),
            fn ($x) => (bool) preg_match('/^\d{4}-\d{2}-\d{2}$/', $x)
        ));

        // Serviços
        $d['servicos'] = [];
        foreach ((array) ($e['servicos'] ?? []) as $s) {
            $nome = $txt($s['nome'] ?? '', 120);
            if ($nome === '') {
                continue;
            }
            $dur = (int) ($s['duracao_minutos'] ?? 30);
            $d['servicos'][] = [
                'nome' => $nome,
                'preco' => $txt($s['preco'] ?? '', 60) ?: 'Consultar',
                'duracao_minutos' => max(10, min(480, $dur ?: 30)),
                'profissional' => $txt($s['profissional'] ?? '', 120),
                'preparo' => $txt($s['preparo'] ?? '', 500),
                'observacoes' => $txt($s['observacoes'] ?? '', 500),
                'agendar_pela_ia' => (bool) ($s['agendar_pela_ia'] ?? true),
            ];
        }
        if (!$d['servicos']) {
            $erros[] = 'Cadastre pelo menos um serviço.';
        }
        $duracoes = array_column($d['servicos'], 'duracao_minutos');
        $d['duracao_padrao_minutos'] = $duracoes ? min($duracoes) : 30;

        $d['profissionais'] = [];
        foreach ((array) ($e['profissionais'] ?? []) as $p) {
            if ($txt($p['nome'] ?? '') !== '') {
                $d['profissionais'][] = [
                    'nome' => $txt($p['nome'], 120),
                    'especialidade' => $txt($p['especialidade'] ?? '', 120),
                    'dias_horarios' => $txt($p['dias_horarios'] ?? '', 300),
                ];
            }
        }

        $d['convenios'] = $lista($e['convenios'] ?? []);
        $d['convenios_observacoes'] = $txt($e['convenios_observacoes'] ?? '', 800);
        $d['formas_pagamento'] = $lista($e['formas_pagamento'] ?? []);
        $d['sinal_antecipado'] = $txt($e['sinal_antecipado'] ?? '', 300);

        $d['antecedencia_minima_horas'] = max(0, min(168, (int) ($e['antecedencia_minima_horas'] ?? 2)));
        $d['dias_para_frente_agenda'] = max(1, min(365, (int) ($e['dias_para_frente_agenda'] ?? 60)));
        $d['politicas'] = [];
        foreach (['retorno', 'encaixe', 'cancelamento', 'atraso', 'criancas', 'documentos_primeira_consulta'] as $k) {
            $d['politicas'][$k] = $txt($e['politicas'][$k] ?? '', 600);
        }

        $d['perguntas_frequentes'] = [];
        foreach ((array) ($e['perguntas_frequentes'] ?? []) as $f) {
            $p = $txt($f['pergunta'] ?? '', 300);
            $r = $txt($f['resposta'] ?? '', 1000);
            if ($p !== '' && $r !== '') {
                $d['perguntas_frequentes'][] = ['pergunta' => $p, 'resposta' => $r, 'palavras_chave' => $lista($f['palavras_chave'] ?? [])];
            }
        }

        $d['regras_extras'] = [];
        foreach (['tratamento', 'emoji', 'frases_da_clinica', 'proibido', 'sempre_humano'] as $k) {
            $d['regras_extras'][$k] = $txt($e['regras_extras'][$k] ?? '', 1000);
        }
        $d['equipe'] = [];
        foreach (['responsavel', 'como_avisar', 'horario_resposta'] as $k) {
            $d['equipe'][$k] = $txt($e['equipe'][$k] ?? '', 300);
        }

        return [$d, $erros];
    }
}
