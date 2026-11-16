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
        $servico = $nomesServicos
            ? ['type' => 'string', 'enum' => $nomesServicos, 'description' => 'Serviço desejado (define a duração)']
            : ['type' => 'string', 'description' => 'Serviço desejado'];

        return [
            [
                'name' => 'consultar_horarios_livres',
                'description' => 'Consulta os horários livres da agenda da clínica em uma data. Use sempre antes de oferecer horários ao paciente.',
                'strict' => true,
                'input_schema' => [
                    'type' => 'object',
                    'properties' => [
                        'data' => ['type' => 'string', 'description' => 'Data no formato AAAA-MM-DD'],
                        'servico' => $servico,
                    ],
                    'required' => ['data', 'servico'],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'agendar_consulta',
                'description' => 'Marca uma consulta. Só use depois que o paciente confirmar serviço, data, hora e nome.',
                'strict' => true,
                'input_schema' => [
                    'type' => 'object',
                    'properties' => [
                        'nome_paciente' => ['type' => 'string', 'description' => 'Nome completo do paciente'],
                        'data' => ['type' => 'string', 'description' => 'AAAA-MM-DD'],
                        'hora' => ['type' => 'string', 'description' => 'HH:MM (24h), um dos horários livres'],
                        'servico' => $servico,
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
                'input_schema' => [
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
                'input_schema' => [
                    'type' => 'object',
                    'properties' => [
                        'codigo' => ['type' => 'string', 'description' => 'Código do agendamento (6 caracteres)'],
                    ],
                    'required' => ['codigo'],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'pedir_ajuda_especialista',
                'description' => 'Passa ESTA conversa para um atendimento mais avançado, que responde no seu lugar. Use quando o caso for complexo, ambíguo ou delicado: reclamação, paciente confuso ou irritado, vários pedidos misturados, ou quando você não tiver certeza de como agir. Não use para perguntas simples nem para agendamentos comuns. Não escreva nada antes de usar.',
                'strict' => true,
                'input_schema' => [
                    'type' => 'object',
                    'properties' => ['motivo' => ['type' => 'string', 'description' => 'Por que precisa de ajuda']],
                    'required' => ['motivo'],
                    'additionalProperties' => false,
                ],
            ],
            [
                'name' => 'chamar_atendente_humano',
                'description' => 'Avisa a equipe da clínica para assumir a conversa: pedido do paciente, reclamação, dúvida sem resposta nas informações da clínica, ou emergência.',
                'strict' => true,
                'input_schema' => [
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
