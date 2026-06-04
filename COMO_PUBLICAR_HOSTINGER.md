# Como publicar na Hostinger

Esta versao nao usa banco MySQL.

Ela salva os codigos, progresso e anotacoes em um arquivo JSON dentro da propria Hostinger.

## Deploy pela Hostinger

Este repositorio deve ser implantado diretamente em `public_html`.

No hPanel da Hostinger, use:

```text
Repositorio: https://github.com/henriquegomesdacosta14/CODEX.git
Branch: main
Diretorio raiz: public_html
```

Depois do deploy, confirme que estes itens ficaram dentro de `public_html`:

```text
index.html
admin.html
api.php
data
```

A pasta `data` precisa ir junto. Ela tem um arquivo `.htaccess` para bloquear acesso direto aos dados.

## Criar config.php na Hostinger

Por seguranca, `config.php` nao fica no GitHub.

Crie manualmente em `public_html/config.php`:

```php
<?php

return [
    'admin_password' => 'troque-esta-senha',
];
```

Troque `troque-esta-senha` pela senha real do ADM.

## Links

Pagina do casal:

```text
https://educaonine.shop
```

Pagina ADM:

```text
https://educaonine.shop/admin.html
```

Senha ADM configurada no servidor:

```text
definida em public_html/config.php
```

## Se der erro

Envie tambem o arquivo:

```text
diagnostico.php
```

Abra:

```text
https://educaonine.shop/diagnostico.php
```

Ele vai dizer se o PHP consegue gravar na pasta `data`.

Depois do teste, apague `diagnostico.php` da hospedagem.
