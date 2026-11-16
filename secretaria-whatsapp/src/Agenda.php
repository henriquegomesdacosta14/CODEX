<?php

namespace Secretaria;

/**
 * Agenda simples da clínica, guardada em dados/agendamentos.json.
 * Calcula horários livres a partir do horário de funcionamento (clinica.json).
 *
 * Em produção, esta classe é o ponto para integrar com o sistema/agenda real
 * da clínica (Google Agenda, software da clínica etc.).
 */
class Agenda
{
    private const DIAS = ['domingo', 'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado'];

    public function __construct(
        private Armazenamento $armazenamento,
        private array $clinica,
        private \DateTimeZone $fuso,
        private bool $simulacao = false, // true: testa sem gravar nada na agenda
    ) {
    }

    public function servicos(): array
    {
        return $this->clinica['servicos'] ?? [];
    }

    private function encontrarServico(string $nome): ?array
    {
        $busca = mb_strtolower(trim($nome));
        foreach ($this->servicos() as $s) {
            if (mb_strtolower($s['nome']) === $busca) {
                return $s;
            }
        }
        foreach ($this->servicos() as $s) {
            if (str_contains(mb_strtolower($s['nome']), $busca) || str_contains($busca, mb_strtolower($s['nome']))) {
                return $s;
            }
        }
        return null;
    }

    private function duracao(?array $servico): int
    {
        return (int) ($servico['duracao_minutos'] ?? $this->clinica['duracao_padrao_minutos'] ?? 30);
    }

    private function agendamentosAtivos(): array
    {
        return array_values(array_filter(
            $this->armazenamento->ler('agendamentos', []),
            fn ($a) => ($a['status'] ?? '') === 'confirmado'
        ));
    }

    private function data(string $data): ?\DateTimeImmutable
    {
        $d = \DateTimeImmutable::createFromFormat('!Y-m-d', $data, $this->fuso);
        return ($d && $d->format('Y-m-d') === $data) ? $d : null;
    }

    /** Lista horários livres em uma data para um serviço. */
    public function horariosLivres(string $data, string $servico = ''): array
    {
        $dia = $this->data($data);
        if (!$dia) {
            return ['erro' => 'Data inválida. Use o formato AAAA-MM-DD.'];
        }

        $agora = new \DateTimeImmutable('now', $this->fuso);
        $limite = $agora->modify('+' . (int) ($this->clinica['dias_para_frente_agenda'] ?? 60) . ' days');
        if ($dia > $limite) {
            return ['data' => $data, 'horarios_livres' => [], 'aviso' => 'A agenda ainda não está aberta para essa data.'];
        }
        if ($dia->format('Y-m-d') < $agora->format('Y-m-d')) {
            return ['data' => $data, 'horarios_livres' => [], 'aviso' => 'Essa data já passou.'];
        }
        if (in_array($data, $this->clinica['feriados_e_folgas'] ?? [], true)) {
            return ['data' => $data, 'horarios_livres' => [], 'aviso' => 'A clínica não abre nessa data (feriado/folga).'];
        }

        $nomeDia = self::DIAS[(int) $dia->format('w')];
        $periodos = $this->clinica['horario_funcionamento'][$nomeDia] ?? [];
        if (!$periodos) {
            return ['data' => $data, 'dia_semana' => $nomeDia, 'horarios_livres' => [], 'aviso' => 'A clínica não abre nesse dia da semana.'];
        }

        $servicoInfo = $servico !== '' ? $this->encontrarServico($servico) : null;
        $duracao = $this->duracao($servicoInfo);
        $passo = (int) ($this->clinica['duracao_padrao_minutos'] ?? 30);
        $minimo = $agora->modify('+' . (int) ($this->clinica['antecedencia_minima_horas'] ?? 0) . ' hours');

        // Intervalos ocupados nesse dia
        $ocupados = [];
        foreach ($this->agendamentosAtivos() as $a) {
            if ($a['data'] === $data) {
                $ini = $this->minutos($a['hora']);
                $ocupados[] = [$ini, $ini + (int) $a['duracao_minutos']];
            }
        }

        $livres = [];
        foreach ($periodos as $periodo) {
            [$abre, $fecha] = array_map([$this, 'minutos'], explode('-', $periodo));
            for ($ini = $abre; $ini + $duracao <= $fecha; $ini += $passo) {
                $fim = $ini + $duracao;
                $momento = $dia->setTime(intdiv($ini, 60), $ini % 60);
                if ($momento < $minimo) {
                    continue;
                }
                foreach ($ocupados as [$oIni, $oFim]) {
                    if ($ini < $oFim && $fim > $oIni) {
                        continue 2;
                    }
                }
                $livres[] = $momento->format('H:i');
            }
        }

        return [
            'data' => $data,
            'dia_semana' => $nomeDia,
            'servico' => $servicoInfo['nome'] ?? null,
            'duracao_minutos' => $duracao,
            'horarios_livres' => $livres,
        ];
    }

    public function agendar(string $telefone, string $nomePaciente, string $data, string $hora, string $servico, string $observacoes = ''): array
    {
        $servicoInfo = $this->encontrarServico($servico);
        if (!$servicoInfo) {
            $nomes = array_column($this->servicos(), 'nome');
            return ['erro' => 'Serviço não encontrado. Serviços disponíveis: ' . implode(', ', $nomes)];
        }
        if (!($servicoInfo['agendar_pela_ia'] ?? true)) {
            return ['erro' => 'Este serviço não pode ser agendado pela assistente. Encaminhe para a equipe.'];
        }
        if (!preg_match('/^\d{2}:\d{2}$/', $hora)) {
            return ['erro' => 'Hora inválida. Use o formato HH:MM.'];
        }
        if (trim($nomePaciente) === '') {
            return ['erro' => 'Informe o nome do paciente.'];
        }

        // Confere de novo, dentro da trava, se o horário continua livre
        return $this->armazenamento->atualizar('agendamentos', function (array $todos) use ($telefone, $nomePaciente, $data, $hora, $servicoInfo, $observacoes) {
            $livres = $this->horariosLivres($data, $servicoInfo['nome']);
            if (isset($livres['erro'])) {
                return [$todos, $livres];
            }
            if (!in_array($hora, $livres['horarios_livres'], true)) {
                return [$todos, [
                    'erro' => 'Esse horário não está mais disponível.',
                    'horarios_livres_nessa_data' => $livres['horarios_livres'],
                ]];
            }
            $codigo = strtoupper(substr(bin2hex(random_bytes(4)), 0, 6));
            $novo = [
                'codigo' => $codigo,
                'status' => 'confirmado',
                'telefone' => $telefone,
                'nome_paciente' => trim($nomePaciente),
                'servico' => $servicoInfo['nome'],
                'preco' => $servicoInfo['preco'] ?? null,
                'data' => $data,
                'hora' => $hora,
                'duracao_minutos' => $this->duracao($servicoInfo),
                'observacoes' => $observacoes,
                'criado_em' => (new \DateTimeImmutable('now', $this->fuso))->format('c'),
            ];
            if ($this->simulacao) {
                $novo['codigo'] = 'TESTE';
                return [$todos, ['sucesso' => true, 'agendamento' => $novo, 'aviso' => 'SIMULAÇÃO: nada foi gravado na agenda.']];
            }
            $todos[] = $novo;
            return [$todos, ['sucesso' => true, 'agendamento' => $novo]];
        }, []);
    }

    public function doTelefone(string $telefone): array
    {
        $hoje = (new \DateTimeImmutable('now', $this->fuso))->format('Y-m-d');
        $lista = array_filter(
            $this->agendamentosAtivos(),
            fn ($a) => $a['telefone'] === $telefone && $a['data'] >= $hoje
        );
        usort($lista, fn ($a, $b) => strcmp($a['data'] . $a['hora'], $b['data'] . $b['hora']));
        return ['agendamentos' => array_values($lista)];
    }

    public function cancelar(string $telefone, string $codigo): array
    {
        $codigo = strtoupper(trim($codigo));
        return $this->armazenamento->atualizar('agendamentos', function (array $todos) use ($telefone, $codigo) {
            foreach ($todos as $i => $a) {
                if ($a['codigo'] === $codigo && $a['status'] === 'confirmado') {
                    if ($a['telefone'] !== $telefone) {
                        return [$todos, ['erro' => 'Esse agendamento foi feito por outro número. Peça para falar com a recepção.']];
                    }
                    if ($this->simulacao) {
                        return [$todos, ['sucesso' => true, 'agendamento_cancelado' => $a, 'aviso' => 'SIMULAÇÃO: nada foi alterado.']];
                    }
                    $todos[$i]['status'] = 'cancelado';
                    $todos[$i]['cancelado_em'] = (new \DateTimeImmutable('now', $this->fuso))->format('c');
                    return [$todos, ['sucesso' => true, 'agendamento_cancelado' => $todos[$i]]];
                }
            }
            return [$todos, ['erro' => 'Agendamento não encontrado com esse código.']];
        }, []);
    }

    private function minutos(string $hhmm): int
    {
        [$h, $m] = array_map('intval', explode(':', trim($hhmm)));
        return $h * 60 + $m;
    }
}
