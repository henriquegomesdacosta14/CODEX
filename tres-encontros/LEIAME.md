# Três Encontros

Devocional de 30 dias em forma de app de celular. São três encontros por dia, liberados nos horários que cada pessoa escolhe:

- **Manhã:** Bom dia com o Espírito Santo
- **Almoço:** Boa tarde com Jesus
- **Noite:** Boa noite com Deus Pai

Os dias 1 a 10 apresentam o Espírito Santo, os dias 11 a 20 apresentam Jesus e os dias 21 a 30 apresentam o Pai. Cada encontro tem versículo, reflexão, uma pergunta com espaço para anotar e uma prática.

É um aplicativo web (PWA): a pessoa abre o link, adiciona à tela inicial e passa a usar como um app, com ícone, tela cheia, funcionamento sem internet e avisos no celular.

## O que tem na pasta

| Arquivo | Para que serve |
| --- | --- |
| `index.html`, `app.css`, `app.js` | O app |
| `sw.js`, `manifest.webmanifest`, `icones/` | Instalação no celular, modo offline e avisos |
| `conteudo/mes-01/*.md` | Os textos dos 30 dias (edite aqui) |
| `conteudo/mes-01.json` | Os textos convertidos que o app lê |
| `api.php`, `lib/` | Servidor: códigos de acesso, progresso e avisos |
| `avisos-cron.php` | Envia os avisos nos horários (rodar a cada 5 minutos) |
| `admin.html` | Área para gerar códigos e acompanhar as pessoas |
| `config.example.php` | Modelo de configuração |

## Instalar na Hostinger

A pasta vai junto com o resto do repositório para `public_html`, então o app fica em `https://seudominio/tres-encontros/`.

1. **Configuração.** No Gerenciador de Arquivos, copie `public_html/tres-encontros/config.example.php` para `config.php` na mesma pasta e preencha:
   - `link_compra`: o link da página de venda (Hotmart, Kiwify ou outra).
   - `contato_avisos`: `mailto:` seguido do seu e-mail.
   - Se não colocar `admin_password`, vale a mesma senha do site principal.
2. **Dados.** O app grava tudo em uma pasta `tres-encontros-dados`, ao lado de `public_html` (fora do alcance da internet). Ela é criada sozinha no primeiro uso.
3. **Avisos no celular.** No hPanel, abra **Avançado → Tarefas Cron** e crie uma tarefa com o comando abaixo, a cada 5 minutos (`*/5 * * * *`). Troque `SEU_USUARIO` pelo seu usuário da Hostinger:

   ```
   /usr/bin/php /home/SEU_USUARIO/public_html/tres-encontros/avisos-cron.php
   ```

4. **Teste.** Abra `https://seudominio/tres-encontros/admin.html`, entre com a senha, gere um código e use esse código no app pelo celular.

## Vender e entregar

1. A pessoa compra pelo seu link de venda.
2. Em `admin.html`, você gera um código, escrevendo o nome da pessoa na observação, e toca em **Copiar mensagem**.
3. Cole a mensagem no WhatsApp da pessoa. Ela já leva o link do app, o código e o passo a passo.

Cada código vale para uma jornada. A data de início é o dia em que a pessoa entra pela primeira vez. O progresso e as anotações ficam guardados no código, então dá para trocar de celular. Se precisar, você pode bloquear um código na área administrativa.

**Degustação:** na tela inicial, o botão “Experimentar 3 dias grátis” libera os dias 1 a 3 sem código, só naquele celular. Ao final, a pessoa vê o botão de compra.

## Avisos no iPhone e no Android

- **Android (Chrome):** os avisos funcionam direto. O app oferece o botão “Instalar app”.
- **iPhone (iOS 16.4 ou mais novo):** é preciso primeiro adicionar o app à tela de início (Safari → Compartilhar → Adicionar à Tela de Início) e só então ativar os avisos dentro do app. O próprio app explica isso.

## Mudar os textos

1. Edite os arquivos em `conteudo/mes-01/`. Cada dia segue este formato:

   ```
   # Dia 5 — Ele ora comigo

   ## Manhã · Romanos 8:26-27

   Parágrafo da reflexão.

   Outro parágrafo.

   ? Pergunta para refletir
   ! Prática do dia, atitude ou oração
   ```

2. Rode `python3 ferramentas/gerar_conteudo.py mes-01`. O script confere se os 30 dias têm os três encontros completos e gera `conteudo/mes-01.json`.
3. Em `sw.js`, aumente a versão (`te-v1` → `te-v2`) para os celulares baixarem o texto novo.

Use aspas curvas (“ ”) dentro dos textos; o script avisa se encontrar aspas retas.

## Próximo mês

O fim do dia 30 mostra a prévia do próximo mês (`conteudo/mes-01/99-proximo-mes.md`, hoje “O Pai Nosso”) e um botão de compra (`link_proximo_mes` ou, se estiver vazio, `link_compra`). Também aparece a opção, livre e sem obrigação, de presentear alguém com um acesso.

## Ver o app sem servidor

Abra `https://seudominio/tres-encontros/#apresentacao`. Aparece uma barra para simular qualquer dia e horário, sem gravar nada no servidor. Ela serve para apresentar o app ou conferir os textos.
