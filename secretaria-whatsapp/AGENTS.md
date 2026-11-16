# AGENTS.md — Secretária virtual da clínica (WhatsApp + Claude)

Instruções para assistentes de código (Codex, Claude Code etc.) que trabalhem nesta pasta.

## O que é

Sistema em **PHP 8.3, sem Composer e sem bibliotecas**, que atende pacientes de uma clínica pelo WhatsApp (Meta Cloud API) usando a API da Anthropic. Roda em hospedagem compartilhada (Hostinger) e é publicado por Git deploy da branch `main`. Quem usa não é programador: o texto que o paciente e a equipe leem deve ser simples e em **português do Brasil**.

Leia primeiro: `LEIAME.md`, `INSTALACAO.md`, `src/Secretaria.php`.

## Como funciona

1. `webhook.php` recebe a mensagem da Meta (confere assinatura, responde 200 na hora e processa depois).
2. `src/RespostasRapidas.php`: se a pergunta é conhecida (endereço, preço, convênio, horário, saudação), responde **sem IA** (custo zero). Pedidos de ação (agendar, cancelar, dor, urgência) sempre vão para a IA.
3. `src/Secretaria.php`: chama o **Haiku** (`modelo`); o **Sonnet** (`modelo_avancado`) assume a conversa se o Haiku pedir ajuda (ferramenta `pedir_ajuda_especialista`), falhar, recusar, vier vazio ou o paciente demonstrar frustração. O Sonnet fica até o fim daquela conversa.
4. A IA usa ferramentas (`src/Ferramentas.php`): horários livres, agendar, listar, cancelar, chamar humano. Quem executa é `src/Agenda.php` e `Secretaria.php`.
5. `src/ClaudeApi.php`: cliente HTTP mínimo (cURL) da API de mensagens.

Dados em `dados/*.json` (ignorados pelo git): `clinica`, `agendamentos`, `conversa_<telefone>`, `respostas_rapidas`, `regras_aprendidas`, `perguntas_frequentes`, `estatisticas`, `transferencias`, `log.txt`.

## Páginas (cada uma tem seu `.php` de API)

- `simulador.html` + `simulador.php`: testar a secretária, ensinar resposta/regra, roteiro de testes.
- `cadastro.html` + `cadastro.php`: formulário dos dados da clínica.
- `assistente.html` + `assistente.php` + `src/Assistente.php`: chat de configuração com o Claude (conversa compartilhada).
- `respostas.html` + `respostas.php`: respostas rápidas, perguntas aprendidas, regras, estatísticas.
- `verificar.php`: confere a instalação. Deve ser apagado depois de instalar.

## Regras para mudar o código

- **Sem dependências externas.** Nada de Composer, SDK ou bibliotecas. Só PHP padrão e cURL. Mantenha compatível com hospedagem compartilhada.
- **Segredos nunca entram no repositório.** Chaves e senhas ficam só em `config.php` (ignorado pelo git). Não coloque chaves em exemplos, logs, testes ou comentários.
- **Custo é prioridade.** O padrão é Haiku, com Sonnet só quando necessário. Não troque o padrão por um modelo mais caro. Respostas conhecidas devem sair sem IA sempre que possível.
- **Histórico de conversa só cresce.** Em `Secretaria.php` e `Assistente.php` o `system`, as `tools` e as mensagens anteriores não podem ser editados no meio da conversa (isso invalida os blocos de raciocínio da API). Mudanças valem para conversas novas. Devolva os blocos de resposta da IA exatamente como vieram.
- **JSON para a API:** objetos vazios devem ir como `{}` (use `new \stdClass()`), nunca `[]`. `ClaudeApi` já corrige o `input` vazio de ferramentas no histórico.
- **Segurança:** a pasta `dados/` é bloqueada por `.htaccess` e não pode ficar acessível. Mantenha a verificação de assinatura do webhook, as senhas das APIs (`hash_equals`) e o escape de HTML nas páginas.
- **Não responda duas vezes à mesma mensagem** (a Meta reenvia): mantenha `WhatsApp::jaProcessada`.
- **Saúde:** a secretária nunca dá diagnóstico nem indica remédio, e em emergência manda ligar 192 e chama a equipe. Não enfraqueça essas regras (`clinica/instrucoes.md`).
- Textos visíveis ao paciente, mensagens de erro e documentação: português do Brasil, frases simples.

## Como testar sem gastar créditos

```bash
cp config.example.php config.php        # preencha chave de teste e senhas
php -S 127.0.0.1:8080                   # abre simulador.html, cadastro.html, verificar.php
php terminal.php                        # conversa pelo terminal
```

Para não chamar a API de verdade, aponte `'anthropic_base_url'` no `config.php` para um servidor local falso que devolva o formato de `POST /v1/messages` (content com blocos `text`/`tool_use`, `stop_reason`). Cada teste real custa centavos, mas evite loops.

Antes de enviar: `php -l` em todos os `.php`; teste o fluxo agendar → confirmar; teste uma resposta rápida, um escalonamento e o erro de chave ausente. Apague `config.php` e `dados/*.json` de teste antes de commitar (já estão no `.gitignore`).

## Git

- **Trabalhe em uma branch separada.** A Hostinger publica a `main`: só mescle depois de testar.
- Mensagens de commit curtas e no imperativo, explicando o motivo.
- Não commite `config.php`, `dados/` com conteúdo real, nem arquivos de pacientes.
