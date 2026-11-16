<?php
// Copie este arquivo para config.php e preencha os valores.
// NUNCA envie o config.php para o GitHub (ele já está no .gitignore).

return [
    // ===== IA (Claude) =====
    // Chave criada em https://console.anthropic.com  (Settings > API Keys)
    'anthropic_api_key' => '',

    // Modelo que atende primeiro (barato e rápido)
    'modelo' => 'claude-haiku-5-5',
    // Modelo que ASSUME a conversa quando o primeiro não dá conta: caso complexo,
    // paciente frustrado, erro ou recusa. Fica até o fim daquela conversa.
    // Deixe '' para não escalar (o mais barato possível).
    'modelo_avancado' => 'claude-sonnet-5-5',
    // Modelo do chat de configuração (assistente.html). Haiku = bem mais barato.
    // Troque por 'claude-sonnet-5-5' se quiser conversas mais elaboradas.
    'modelo_assistente' => 'claude-haiku-5-5',

    // Quanto a IA "pensa" antes de responder: 'low', 'medium' ou 'high'.
    // Para atendimento por WhatsApp, 'low' costuma bastar e economiza.
    'esforco' => 'low',
    // Esforço do chat de configuração (assistente.html): 'low' gasta menos
    'esforco_assistente' => 'low',

    // ===== WhatsApp (Meta Cloud API) =====
    // Painel: developers.facebook.com > seu app > WhatsApp > Configuração da API
    'whatsapp_token'           => '',   // token de acesso (permanente, do usuário do sistema)
    'whatsapp_phone_number_id' => '',   // "Identificação do número de telefone"
    'whatsapp_app_secret'      => '',   // Configurações do app > Básico > Chave secreta do app
    // Texto que VOCÊ inventa e digita igual no painel da Meta ao cadastrar o webhook
    'whatsapp_verify_token'    => 'troque-este-texto',
    'graph_api_version'        => 'v23.0',

    // ===== Economia: respostas rápidas =====
    // true: perguntas frequentes (endereço, preço, convênio...) são respondidas
    // sem chamar a IA. Gerencie em respostas.html.
    'respostas_rapidas' => true,

    // ===== Painel (simulador.html e respostas.html) =====
    // Senha para abrir o simulador e o painel de respostas. Vazio = desativados.
    'senha_simulador' => 'troque-esta-senha',

    // Senha da página cadastro.html (onde a clínica preenche seus dados).
    // Se ficar vazia, usa a mesma senha do simulador.
    'senha_cadastro' => '',

    // ===== Geral =====
    'fuso_horario' => 'America/Sao_Paulo',
    // Depois de quantas horas sem mensagens a conversa recomeça do zero
    'horas_para_nova_conversa' => 12,

    // Só para testes locais (deixe null em produção)
    'anthropic_base_url' => null,
];
