<?php
// Copie este arquivo para config.php (na mesma pasta) e preencha.
// config.php não vai para o GitHub. Se não existir, a senha do site principal (public_html/config.php) é usada.

return [
    // Senha da página admin.html. Se ficar vazia, vale a admin_password do site principal.
    // 'admin_password' => 'troque-esta-senha',

    // Link da página de compra (Hotmart, Kiwify, Mercado Pago...). Aparece na degustação e no presente.
    'link_compra' => '',

    // Link para comprar o próximo mês. Se ficar vazio, usa o link_compra.
    'link_proximo_mes' => '',

    // E-mail de contato exigido pelos serviços de aviso (Google, Apple, Mozilla).
    'contato_avisos' => 'mailto:seu-email@exemplo.com',

    // Opcional: chave para rodar os avisos pela web (avisos-cron.php?chave=...). Use uma frase longa.
    'chave_cron' => '',
];
