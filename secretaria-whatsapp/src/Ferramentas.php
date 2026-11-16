<?php

namespace Secretaria;

/**
 * Ações que a IA pode executar. A IA decide quando usar cada uma;
 * quem executa de verdade é o nosso código (classe Agenda / Secretaria).
 */
class Ferramentas
{
    public static function definicoes(array $servicos): array
    {
        $nomesServicos = array_values(array_column($servicos, 'nome'));

        return [
            [
                'name' => 'consultar_horarios_livres',
                'description' => 'Consulta os horários livres da agenda da clínica em uma data. Use sempre antes de oferecer horários ao paciente.',
                'strict' => true,
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => [
                        'data' => ['type' => 'string', 'description' => 'Data no formato AAAA-MM-DD'],
                        'servico' => ['type' => 'string', 'enum' => $nomesServicos, 'description' => 'Serviço desejado (define a duração)'],
                    ],
                    'required' => ['data', 'servico'],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'agendar_consulta',
                'description' => 'Marca uma consulta. Só use depois que o paciente confirmar serviço, data, hora e nome.',
                'strict' => true,
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => [
                        'nome_paciente' => ['type' => 'string', 'description' => 'Nome completo do paciente'],
                        'data' => ['type' => 'string', 'description' => 'AAAA-MM-DD'],
                        'hora' => ['type' => 'string', 'description' => 'HH:MM (24h), um dos horários livres'],
                        'servico' => ['type' => 'string', 'enum' => $nomesServicos],
                        'observacoes' => ['type' => 'string', 'description' => 'Observações administrativas (ex.: convênio). Pode ser vazio.'],
                    ],
                    'required' => ['nome_paciente', 'data', 'hora', 'servico', 'observacoes'],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'listar_meus_agendamentos',
                'description' => 'Lista os próximos agendamentos feitos por este número de WhatsApp.',
                'strict' => true,
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => new \stdClass(),
                    'required' => [],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'cancelar_agendamento',
                'description' => 'Cancela um agendamento deste número pelo código. Só use após o paciente confirmar o cancelamento.',
                'strict' => true,
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => [
                        'codigo' => ['type' => 'string', 'description' => 'Código do agendamento (6 caracteres)'],
                    ],
                    'required' => ['codigo'],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'chamar_atendente_humano',
                'description' => 'Avisa a equipe da clínica para assumir a conversa: pedido do paciente, reclamação, dúvida sem resposta nas informações da clínica, ou emergência.',
                'strict' => true,
                'inputSchema' => [
                    'type' => 'object',
                    'properties' => [
                        'motivo' => ['type' => 'string', 'description' => 'Resumo curto do motivo'],
                        'urgente' => ['type' => 'boolean', 'description' => 'true se for possível emergência'],
                    ],
                    'required' => ['motivo', 'urgente'],
                    'additionalProperties' => false,
                ],
            ],
        ];
    }
}
