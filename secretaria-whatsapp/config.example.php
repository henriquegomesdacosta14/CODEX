<?php
// Copie este arquivo para config.php e preencha os valores.
// NUNCA envie o config.php para o GitHub (ele já está no .gitignore).

return [
    // ===== IA (Claude) =====
    // Chave criada em https://console.anthropic.com  (Settings > API Keys)
    'anthropic_api_key' => '',

    // Modelo da IA. Opções:
    //   'claude-opus-5-5'   -> mais inteligente (padrão)
    //   'claude-sonnet-5-5' -> intermediário, mais barato
    //   'claude-haiku-5-5'  -> mais barato de todos
    'modelo' => 'claude-opus-5-5',

    // Quanto a IA "pensa" antes de responder: 'low', 'medium' ou 'high'.
    // Para atendimento por WhatsApp, 'low' costuma bastar e economiza.
    'esforco' => 'low',

    // ===== WhatsApp (Meta Cloud API) =====
    // Painel: developers.facebook.com > seu app > WhatsApp > Configuração da API
    'whatsapp_token'           => '',   // token de acesso (permanente, do usuário do sistema)
    'whatsapp_phone_number_id' => '',   // "Identificação do número de telefone"
    'whatsapp_app_secret'      => '',   // Configurações do app > Básico > Chave secreta do app
    // Texto que VOCÊ inventa e digita igual no painel da Meta ao cadastrar o webhook
    'whatsapp_verify_token'    => 'troque-este-texto',
    'graph_api_version'        => 'v23.0',

    // ===== Simulador (testar sem WhatsApp) =====
    // Senha para abrir simulador.html. Deixe vazio para desativar o simulador.
    'senha_simulador' => 'troque-esta-senha',

    // ===== Geral =====
    'fuso_horario' => 'America/Sao_Paulo',
    // Depois de quantas horas sem mensagens a conversa recomeça do zero
    'horas_para_nova_conversa' => 12,

    // Só para testes locais (deixe null em produção)
    'anthropic_base_url' => null,
];
