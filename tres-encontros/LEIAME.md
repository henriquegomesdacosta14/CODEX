# Três Encontros

Devocional de 30 dias em forma de app de celular. São três encontros por dia. Os três abrem à meia-noite, e o celular lembra a pessoa nos horários que ela escolheu:

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
| `api.php`, `lib/` | Servidor: códigos de acesso, progresso, anotações e avisos (banco MySQL) |
| `avisos-cron.php` | Envia os avisos nos horários (rodar a cada 5 minutos) |
| `admin.html` | Área para gerar códigos e acompanhar as pessoas |
| `config.example.php` | Modelo de configuração |

## Instalar na Hostinger

A pasta vai junto com o resto do repositório para `public_html`, então o app fica em `https://seudominio/tres-encontros/`.

1. **Banco de dados.** No hPanel, abra **Bancos de Dados → Gerenciamento** e crie um banco MySQL com usuário e senha. Anote o nome do banco, o usuário e a senha. As tabelas são criadas sozinhas no primeiro acesso.
2. **Configuração.** No Gerenciador de Arquivos, copie `public_html/tres-encontros/config.example.php` para `config.php` na mesma pasta e preencha:
   - `banco`: os dados do MySQL do passo anterior (tire as barras `//` da frente dessas linhas).
   - `link_compra`: o link da página de venda (Hotmart, Kiwify ou outra).
   - `contato_avisos`: `mailto:` seguido do seu e-mail.
   - Se não colocar `admin_password`, vale a mesma senha do site principal.
3. **Pasta de dados.** As chaves dos avisos ficam numa pasta `tres-encontros-dados`, ao lado de `public_html`, fora do alcance da internet. Ela é criada sozinha. Sem o MySQL configurado, o app guarda tudo ali num arquivo SQLite, o que serve para testar e para os primeiros mil usuários.
4. **Avisos no celular.** No hPanel, abra **Avançado → Tarefas Cron** e crie uma tarefa com o comando abaixo, a cada 5 minutos (`*/5 * * * *`). Troque `SEU_USUARIO` pelo seu usuário da Hostinger:

   ```
   /usr/bin/php /home/SEU_USUARIO/public_html/tres-encontros/avisos-cron.php
   ```

5. **Teste.** Abra `https://seudominio/tres-encontros/admin.html`, entre com a senha, gere um código e use esse código no app pelo celular.

## Vender e entregar

1. A pessoa compra pelo seu link de venda.
2. Em `admin.html`, você gera um código, escrevendo o nome da pessoa na observação, e toca em **Copiar mensagem**.
3. Cole a mensagem no WhatsApp da pessoa. Ela já leva o link do app, o código e o passo a passo.

Cada código vale para uma jornada. A data de início é o dia em que a pessoa entra pela primeira vez. O progresso e as anotações ficam guardados no código, então dá para trocar de celular. Se precisar, você pode bloquear um código na área administrativa.

**Degustação:** na tela inicial, o botão “Experimentar 3 dias grátis” libera os dias 1 a 3 sem código, só naquele celular. Ao final, a pessoa vê o botão de compra.

## Quantas pessoas o app aguenta

Teste feito num servidor de 4 núcleos com MySQL, 100 mil códigos, 2,7 milhões de encontros concluídos e 300 mil anotações:

| Situação | Resultado |
| --- | --- |
| 300 pessoas usando ao mesmo tempo | cerca de 1.650 pedidos por segundo, sem falhas, resposta em 0,2 s (mediana) |
| Avisos | 30 mil avisos enviados em 34 segundos (100 de cada vez), sem repetir nenhum |

Na prática, abrir o app e concluir um encontro gasta de 2 a 4 pedidos. Mesmo que 30 mil pessoas abram o app nos mesmos 15 minutos, são cerca de 130 pedidos por segundo, bem abaixo do que o teste mostrou.

O plano compartilhado da Hostinger tem menos capacidade do que o servidor do teste e limita quantos pedidos atende ao mesmo tempo. Recomendações:

- **Até alguns milhares de pessoas ativas:** plano atual com MySQL.
- **Dezenas de milhares:** plano Cloud da Hostinger ou um VPS, e Cloudflare (grátis) na frente do site.
- **Antes de um lançamento grande:** acompanhe o uso de CPU e de processos no hPanel nos primeiros dias.

## Avisos no iPhone e no Android

- **Android (Chrome):** os avisos funcionam direto. O app oferece o botão “Instalar app”.
- **iPhone (iOS 16.4 ou mais novo):** é preciso primeiro adicionar o app à tela de início (Safari → Compartilhar → Adicionar à Tela de Início) e só então ativar os avisos dentro do app. O próprio app explica isso.

## Mudar os textos

1. Edite os arquivos em `conteudo/mes-01/`. Cada dia segue o formato abaixo. A linha que começa com `>` é o versículo em destaque, e a referência do título é a passagem para ler na Bíblia:

   ```
   # Dia 5 — Ele ora comigo

   ## Manhã · Romanos 8:26-27

   > “Também o Espírito, semelhantemente, nos assiste em nossa fraqueza...” — Romanos 8:26

   Parágrafo da reflexão.

   Outro parágrafo.

   ? Pergunta para refletir
   ! Prática do dia, atitude ou oração
   ```

2. Rode `python3 ferramentas/gerar_conteudo.py mes-01`. O script confere se os 30 dias têm os três encontros completos e gera `conteudo/mes-01.json`.
3. Pronto: o app busca o texto atualizado sempre que é aberto com internet. Só quando mudar `app.js` ou `app.css` aumente a versão em `sw.js` (por exemplo, `te-v2` → `te-v3`).

Use aspas curvas (“ ”) dentro dos textos; o script avisa se encontrar aspas retas.

## Próximo mês

O fim do dia 30 mostra a prévia do próximo mês (`conteudo/mes-01/99-proximo-mes.md`, hoje “O Pai Nosso”) e um botão de compra (`link_proximo_mes` ou, se estiver vazio, `link_compra`). Também aparece a opção, livre e sem obrigação, de presentear alguém com um acesso.

## Ver o app sem servidor

Abra `https://seudominio/tres-encontros/#apresentacao`. Aparece uma barra para simular qualquer dia e horário, sem gravar nada no servidor. Ela serve para apresentar o app ou conferir os textos.
