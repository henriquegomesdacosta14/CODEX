<?php
// Avisos no celular (Web Push) sem bibliotecas externas.
// Os avisos vão sem conteúdo: o próprio app, ao receber, monta o texto do encontro liberado.
// Assim não é preciso criptografar a mensagem, só assinar o pedido com as chaves VAPID.

require_once __DIR__ . '/base.php';

function te_b64url($bin)
{
    return rtrim(strtr(base64_encode($bin), '+/', '-_'), '=');
}

/** Lê as chaves VAPID; cria na primeira vez. */
function te_chaves_vapid()
{
    $dados = te_ler('vapid');
    if (!empty($dados['privada']) && !empty($dados['publica'])) {
        return $dados;
    }
    $chave = openssl_pkey_new(array('curve_name' => 'prime256v1', 'private_key_type' => OPENSSL_KEYTYPE_EC));
    if (!$chave) {
        te_erro('O servidor não conseguiu criar as chaves dos avisos (OpenSSL).', 500);
    }
    openssl_pkey_export($chave, $pem);
    $det = openssl_pkey_get_details($chave);
    $x = str_pad($det['ec']['x'], 32, "\0", STR_PAD_LEFT);
    $y = str_pad($det['ec']['y'], 32, "\0", STR_PAD_LEFT);
    $novo = array('privada' => $pem, 'publica' => te_b64url("\x04" . $x . $y), 'criadaEm' => date('c'));
    te_atualizar('vapid', function (&$d) use ($novo) {
        if (empty($d['privada'])) {
            $d = $novo;
        }
    });
    return te_ler('vapid');
}

/** Converte a assinatura DER do OpenSSL para o formato bruto (r||s) que o JWT ES256 exige. */
function te_der_para_bruto($der)
{
    $pos = 2;
    if (ord($der[1]) & 0x80) {
        $pos += ord($der[1]) & 0x7f;
    }
    $partes = array();
    for ($i = 0; $i < 2; $i++) {
        $pos++; // tipo INTEGER
        $tam = ord($der[$pos++]);
        $valor = substr($der, $pos, $tam);
        $pos += $tam;
        $valor = ltrim($valor, "\0");
        $partes[] = str_pad($valor, 32, "\0", STR_PAD_LEFT);
    }
    return $partes[0] . $partes[1];
}

function te_jwt_vapid($endpoint, $chaves, $contato)
{
    $url = parse_url($endpoint);
    $aud = $url['scheme'] . '://' . $url['host'] . (isset($url['port']) ? ':' . $url['port'] : '');
    $cab = te_b64url(json_encode(array('typ' => 'JWT', 'alg' => 'ES256')));
    $corpo = te_b64url(json_encode(array('aud' => $aud, 'exp' => time() + 12 * 3600, 'sub' => $contato)));
    $entrada = $cab . '.' . $corpo;
    if (!openssl_sign($entrada, $der, $chaves['privada'], OPENSSL_ALGO_SHA256)) {
        return '';
    }
    return $entrada . '.' . te_b64url(te_der_para_bruto($der));
}

