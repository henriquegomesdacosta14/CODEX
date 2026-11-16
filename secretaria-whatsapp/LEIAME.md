# Secretária virtual com IA para WhatsApp (protótipo)

Atende pacientes 24 horas no WhatsApp: tira dúvidas, mostra horários livres, agenda, consulta e cancela consultas, e chama um atendente humano quando precisa.

```
Paciente (WhatsApp) → Meta Cloud API → webhook.php → IA (Claude) → resposta → paciente
                                              ↕
                                  agenda / histórico (pasta dados/)
```

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `clinica/clinica.json` | **Dados da clínica**: nome, endereço, horários, serviços, preços e convênios. Edite aqui. |
| `clinica/instrucoes.md` | **Personalidade e regras** da secretária. Edite aqui. |
| `config.php` | Chaves e senhas. Crie a partir de `config.example.php`. Nunca vai para o GitHub. |
| `webhook.php` | Endereço que a Meta chama quando chega uma mensagem. |
| `simulador.html` | Tela parecida com o WhatsApp para testar **sem** WhatsApp. |
| `respostas.html` | Painel de respostas rápidas (grátis) e do que o sistema aprendeu. |
| `clinica/respostas_rapidas.json` | Respostas rápidas iniciais. |
| `terminal.php` | Teste pelo terminal: `php terminal.php`. |
| `src/` | Código: IA (`Secretaria.php`), agenda (`Agenda.php`), ações da IA (`Ferramentas.php`) e WhatsApp (`WhatsApp.php`). |
| `dados/` | Criada automaticamente: conversas, agendamentos, pedidos de atendente e `log.txt`. Bloqueada para acesso pela internet. |

## O que precisa para rodar

1. **Hospedagem com PHP 8.3 ou mais novo e HTTPS.** A Hostinger serve (plano com acesso SSH, para o passo 3).
2. **Chave da API da Anthropic** (a IA): https://console.anthropic.com → coloque créditos → *API Keys* → *Create Key*. Defina um limite de gasto mensal em *Limits*.
3. **Composer**, para instalar as bibliotecas. Já vem na Hostinger via SSH.
4. **Conta de desenvolvedor da Meta** com um app de WhatsApp. Só é necessária na etapa B; para testar no simulador, não precisa.

## Etapa A: testar no simulador (só precisa da chave da IA)

1. Envie a pasta `secretaria-whatsapp` para a hospedagem (pelo deploy do GitHub ou pelo Gerenciador de Arquivos).
2. Pelo SSH da Hostinger, entre na pasta e instale as bibliotecas:
   ```bash
   cd public_html/secretaria-whatsapp
   composer install --no-dev
   ```
3. Copie `config.example.php` para `config.php` e preencha pelo menos:
   - `anthropic_api_key`
   - `senha_simulador` (escolha uma senha)
4. Abra `https://SEU-DOMINIO/secretaria-whatsapp/simulador.html`, digite a senha e converse como se fosse um paciente.
5. Ajuste `clinica/clinica.json` e `clinica/instrucoes.md` até gostar das respostas. As mudanças valem para **conversas novas** (use o botão *Nova conversa*).

## Etapa B: ligar no WhatsApp de verdade

1. Em https://developers.facebook.com, crie um app do tipo **Empresa** e adicione o produto **WhatsApp**.
2. Em *WhatsApp → Configuração da API*:
   - adicione e verifique o número da clínica. Ele **não pode** estar em uso no app WhatsApp comum (use um chip novo, ou migre o número);
   - copie a **Identificação do número de telefone** e coloque em `whatsapp_phone_number_id`.
3. Crie um **token permanente**: no Business Manager, em *Usuários do sistema*, crie um usuário admin, gere um token com as permissões `whatsapp_business_messaging` e `whatsapp_business_management`, e coloque em `whatsapp_token`.
4. Em *Configurações do app → Básico*, copie a **Chave secreta do app** e coloque em `whatsapp_app_secret`.
5. Em *WhatsApp → Configuração → Webhook*:
   - **URL de callback**: `https://SEU-DOMINIO/secretaria-whatsapp/webhook.php`
   - **Token de verificação**: o mesmo texto que você colocou em `whatsapp_verify_token`
   - clique em *Verificar e salvar* e depois **assine o campo `messages`**.
6. Mande um "Oi" para o número da clínica. A resposta deve chegar em alguns segundos.
7. Antes de abrir para o público: verifique a empresa no Business Manager e publique o app (modo *Ao vivo*).

## Problemas comuns

- **A resposta não chega.** Veja `dados/log.txt` pelo Gerenciador de Arquivos.
  - `ERRO IA`: problema com a chave ou os créditos da Anthropic.
  - `ERRO WhatsApp HTTP 401`: o token da Meta está errado ou vencido.
- **A Meta não verifica o webhook.** Confira se o `whatsapp_verify_token` é exatamente igual nos dois lugares e se o site abre com HTTPS.
- **"Faltam as bibliotecas".** Rode `composer install --no-dev` na pasta.

## Economia: respostas rápidas e aprendizado

Perguntas comuns são respondidas **sem chamar a IA**, ou seja, de graça: saudação, endereço, horário de funcionamento, preços, convênios, formas de pagamento e agradecimentos.

1. Chega uma mensagem. Se ela bater com uma resposta rápida, o sistema responde na hora, sem custo.
2. Se não bater, a IA responde. Isso sempre acontece com agendar, cancelar, dor, urgência ou pedido de atendente.
3. O sistema **anota as perguntas que a IA respondeu** e quantas vezes cada uma apareceu.
4. Em `https://SEU-DOMINIO/secretaria-whatsapp/respostas.html` (com a mesma senha do simulador) você vê:
   - quantas mensagens foram respondidas de graça no mês;
   - as perguntas mais frequentes, com a resposta que a IA deu. Um clique em **Aprovar** transforma a resposta em resposta rápida;
   - as respostas rápidas existentes, para editar, desativar ou criar novas, e um campo para testar uma mensagem.

As respostas usam campos como `{{endereco}}` e `{{servicos_precos}}`, que puxam os dados de `clinica/clinica.json`. Se você mudar um preço lá, as respostas rápidas acompanham. Para desligar tudo isso, use `'respostas_rapidas' => false` no `config.php`.

A aprovação é manual de propósito: uma resposta da IA pode conter algo que só vale naquele dia, como "temos horário amanhã às 10h".

## Custos e privacidade

- **IA**: paga por uso no console da Anthropic. Troque o `modelo` no `config.php` para equilibrar custo e qualidade: `claude-opus-5-5`, `claude-sonnet-5-5` ou `claude-haiku-5-5`.
- **WhatsApp**: responder quem chamou é gratuito por 24 horas. Mensagens iniciadas pela clínica (lembretes) usam templates pagos. Este protótipo ainda não envia lembretes.
- **LGPD**: as conversas ficam em `dados/`. Informe os pacientes sobre o atendimento automatizado e apague arquivos antigos periodicamente.

## Limitações do protótipo (próximos passos)

- A agenda é própria, em `dados/agendamentos.json`. O próximo passo é integrar com a agenda real (Google Agenda ou o sistema da clínica) em `src/Agenda.php`.
- Quando a IA chama um atendente, o pedido aparece no simulador, mas a IA continua respondendo. Falta um painel para a equipe assumir a conversa e um aviso para a recepção (e-mail ou WhatsApp).
- Só lê texto. Áudios e imagens recebem uma resposta pedindo texto.
- Lembretes automáticos de consulta exigem templates aprovados pela Meta.
