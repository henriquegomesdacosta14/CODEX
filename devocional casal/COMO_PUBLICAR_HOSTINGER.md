# Como publicar na Hostinger

Esta versao nao usa banco MySQL.

Ela salva os codigos, progresso e anotacoes em um arquivo JSON dentro da propria Hostinger.

## Enviar para public_html

Envie estes itens para `public_html`:

```text
index.html
admin.html
api.php
config.php
data
```

A pasta `data` precisa ir junto. Ela tem um arquivo `.htaccess` para bloquear acesso direto aos dados.

## Links

Pagina do casal:

```text
https://educaonine.shop
```

Pagina ADM:

```text
https://educaonine.shop/admin.html
```

Senha ADM configurada:

```text
Devo135
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
