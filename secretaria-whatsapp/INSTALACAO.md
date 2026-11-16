# Instalação em 5 passos (sem programar)

Tempo: cerca de 10 minutos. Você precisa de: a Hostinger com a publicação pelo GitHub já ligada, e uma **chave nova** da IA (console.anthropic.com → API Keys). Não mande a chave para ninguém.

## Passo 1. Publicar

No hPanel da Hostinger: **Git → Implantar**. Quando terminar, a pasta `secretaria-whatsapp` aparece dentro de `public_html`.

Não precisa instalar mais nada: o sistema não usa Composer nem bibliotecas.

## Passo 2. Criar o config.php

1. hPanel → **Arquivos → Gerenciador de Arquivos** → `public_html` → `secretaria-whatsapp`.
2. Copie o arquivo `config.example.php` com o nome **`config.php`**. (Se não achar “Copiar”, crie um arquivo novo chamado `config.php` e cole dentro o conteúdo do `config.example.php`.)
3. Abra o `config.php` para editar e mude só estas três linhas:

```php
'anthropic_api_key' => 'COLE-AQUI-A-CHAVE-NOVA',
'senha_simulador'   => 'uma-senha-sua',
'senha_cadastro'    => 'senha-para-sua-esposa',
```

Deixe o resto como está. Os dados do WhatsApp ficam para depois.

## Passo 3. Verificar

Abra no navegador: `https://SEU-DOMINIO/secretaria-whatsapp/verificar.php`

- Tudo com ✓ = pronto. Item com ✗ = a própria página diz como resolver.
- Digite a senha do simulador e clique em **Testar** para confirmar que a chave e os créditos funcionam (custa menos de 1 centavo).

## Passo 4. Preencher e ensinar

1. **Dados da clínica:** `https://SEU-DOMINIO/secretaria-whatsapp/cadastro.html` (senha: `senha_cadastro`). Ou mande as respostas do documento Word para quem está configurando.
2. **Simulador:** `https://SEU-DOMINIO/secretaria-whatsapp/simulador.html` (senha: `senha_simulador`).
   - Use o **Roteiro de testes** à direita: toque em cada frase e veja a resposta.
   - Se uma resposta não ficar boa, toque em **✏️ Ensinar resposta certa**. Escolha “Responder sempre assim, de graça” para perguntas que têm sempre a mesma resposta, ou “Só ensinar a regra para a IA” para o resto.
   - Para regras gerais (“sempre pergunte se é a primeira consulta”), use **Ensinar uma regra nova**.
   - Depois de ensinar, toque em **Nova conversa** e teste de novo.
3. **Acompanhar o aprendizado:** `https://SEU-DOMINIO/secretaria-whatsapp/respostas.html`.

## Passo 5. Fechar

- **Apague o arquivo `verificar.php`** da hospedagem.
- Quando for ligar o WhatsApp, siga a “Etapa B” do `LEIAME.md`.

## Se algo der errado

- Mensagem “Falta o config.php”: refaça o passo 2.
- A secretária responde “estou com uma instabilidade”: abra `verificar.php` e use **Testar**. Na pasta `dados`, o arquivo `log.txt` mostra o motivo.
- Página em branco ou erro 500: abra `verificar.php`. Se nem ele abrir, a versão do PHP da hospedagem é menor que 8.3.
