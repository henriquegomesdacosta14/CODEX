<?php
/**
 * Verificação da instalação. Abra no navegador:
 *   https://SEU-DOMINIO/secretaria-whatsapp/verificar.php
 * Mostra o que está certo e o que falta. Não exibe senhas nem chaves.
 * Depois de instalar, APAGUE este arquivo.
 */

$aqui = __DIR__;
$arquivoTeste = $aqui . '/dados/_teste_acesso.txt';

$config = null;
try {
    if (is_file($aqui . '/config.php')) {
        $c = require $aqui . '/config.php';
        $config = is_array($c) ? $c : null;
    }
} catch (\Throwable $e) {
    $config = null;
}

// ---------- Ações da página (teste da IA / limpeza) ----------
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json; charset=utf-8');
    $e = json_decode(file_get_contents('php://input') ?: '', true) ?? [];

    if (($e['acao'] ?? '') === 'limpar_teste') {
        @unlink($arquivoTeste);
        echo json_encode(['ok' => true]);
        exit;
    }

    if (($e['acao'] ?? '') === 'testar_ia') {
        $senha = (string) (($config['senha_cadastro'] ?? '') ?: ($config['senha_simulador'] ?? ''));
        if (!$config || $senha === '' || !hash_equals($senha, (string) ($e['senha'] ?? ''))) {
            usleep(500000);
            http_response_code(401);
            echo json_encode(['erro' => 'Senha incorreta (use a senha_simulador do config.php).']);
            exit;
        }
        require_once $aqui . '/src/ClaudeApiException.php';
        require_once $aqui . '/src/ClaudeApi.php';
        try {
            $api = new Secretaria\ClaudeApi((string) ($config['anthropic_api_key'] ?? ''), $config['anthropic_base_url'] ?? null, 40, 0);
            $modelo = $config['modelo'] ?? 'claude-haiku-5-5';
            $r = $api->mensagem([
                'model' => $modelo,
                'max_tokens' => 300,
                'messages' => [['role' => 'user', 'content' => 'Responda apenas com a palavra: OK']],
                'output_config' => ['effort' => 'low'],
            ]);
            $texto = '';
            foreach ($r['content'] ?? [] as $b) {
                if (($b['type'] ?? '') === 'text') {
                    $texto .= $b['text'];
                }
            }
            echo json_encode(['ok' => true, 'modelo' => $modelo, 'texto' => trim($texto)]);
        } catch (\Throwable $ex) {
            $m = $ex->getMessage();
            $dica = match (true) {
                str_contains($m, '401') => 'A chave está errada ou foi apagada. Crie uma nova em console.anthropic.com e cole no config.php.',
                str_contains($m, '402') || stripos($m, 'credit') !== false || stripos($m, 'billing') !== false => 'Parece que faltam créditos. Veja em console.anthropic.com → Billing.',
                str_contains($m, '404') => 'O nome do modelo no config.php não existe. Use claude-haiku-5-5.',
                str_contains($m, '429') => 'Muitas chamadas ou limite de uso atingido. Espere um pouco.',
                default => '',
            };
            echo json_encode(['erro' => $m, 'dica' => $dica]);
        }
        exit;
    }

    http_response_code(400);
    echo json_encode(['erro' => 'Ação desconhecida']);
    exit;
}

// ---------- Verificações ----------
$itens = [];
function item(array &$l, string $estado, string $titulo, string $ajuda = ''): void
{
    $l[] = ['estado' => $estado, 'titulo' => $titulo, 'ajuda' => $ajuda]; // ok | erro | aviso
}

item($itens, PHP_VERSION_ID >= 80300 ? 'ok' : 'erro', 'PHP ' . PHP_VERSION . ' (precisa do 8.3 ou mais novo)',
    'No hPanel da Hostinger: Avançado → Configuração do PHP → escolha a versão 8.3 ou mais nova.');

foreach (['curl' => 'conversar com a IA e o WhatsApp', 'mbstring' => 'textos com acento', 'json' => 'dados', 'openssl' => 'conexão segura'] as $ext => $para) {
    item($itens, extension_loaded($ext) ? 'ok' : 'erro', "Extensão do PHP “{$ext}” ({$para})",
        'No hPanel: Avançado → Configuração do PHP → Extensões → ative “' . $ext . '”.');
}

item($itens, $config ? 'ok' : 'erro', $config ? 'Arquivo config.php encontrado' : 'Falta o arquivo config.php',
    'No Gerenciador de Arquivos, abra a pasta secretaria-whatsapp, copie config.example.php com o nome config.php e preencha as senhas e a chave.');

if ($config) {
    $senha = (string) ($config['senha_simulador'] ?? '');
    item($itens, ($senha !== '' && $senha !== 'troque-esta-senha') ? 'ok' : 'erro', 'Senha do simulador trocada',
        'Em config.php, mude senha_simulador para uma senha sua. Sem isso qualquer pessoa que souber o endereço pode abrir o simulador.');

    $chave = (string) ($config['anthropic_api_key'] ?? '');
    item($itens, $chave !== '' ? 'ok' : 'erro', $chave !== '' ? 'Chave da IA preenchida' : 'Chave da IA (anthropic_api_key) vazia',
        'Crie em console.anthropic.com → API Keys e cole entre as aspas em config.php. Não mande a chave para ninguém.');

    $modelo = (string) ($config['modelo'] ?? '');
    item($itens, $modelo !== '' ? 'ok' : 'aviso', 'Modelo da IA: ' . ($modelo !== '' ? $modelo : '(não definido, usa claude-haiku-5-5)'),
        'Para gastar pouco, use claude-haiku-5-5.');

    $wa = array_filter([
        'whatsapp_token' => 'token de acesso',
        'whatsapp_phone_number_id' => 'identificação do número',
        'whatsapp_app_secret' => 'chave secreta do app',
        'whatsapp_verify_token' => 'token de verificação',
    ], fn ($k) => trim((string) ($config[$k] ?? '')) === '' || $config[$k] === 'troque-este-texto', ARRAY_FILTER_USE_KEY);
    item($itens, $wa ? 'aviso' : 'ok', $wa ? 'WhatsApp ainda não configurado (faltam: ' . implode(', ', $wa) . ')' : 'Dados do WhatsApp preenchidos',
        $wa ? 'Tudo bem por enquanto: só é preciso quando for ligar o WhatsApp (guia em LEIAME.md, “Etapa B”). O simulador funciona sem isso.' : '');
}

$dados = $aqui . '/dados';
if (!is_dir($dados)) {
    @mkdir($dados, 0755, true);
}
$gravou = is_dir($dados) && @file_put_contents($arquivoTeste, 'VISIVEL') !== false;
item($itens, $gravou ? 'ok' : 'erro', $gravou ? 'Pasta dados/ aceita gravação' : 'A pasta dados/ não aceita gravação',
    'No Gerenciador de Arquivos, clique com o botão direito na pasta “dados” → Permissões → 755.');

$clinica = json_decode((string) @file_get_contents($aqui . '/clinica/clinica.json'), true);
item($itens, is_array($clinica) ? 'ok' : 'erro', 'Dados da clínica (clinica/clinica.json) legíveis',
    'O arquivo está com problema. Reenvie a pasta clinica do GitHub.');

foreach (['webhook.php', 'simulador.php', 'src/Secretaria.php', 'src/ClaudeApi.php'] as $arq) {
    if (!is_file($aqui . '/' . $arq)) {
        item($itens, 'erro', "Falta o arquivo {$arq}", 'A publicação (deploy) do GitHub não trouxe tudo. Em hPanel → Git → Implantar, rode de novo.');
    }
}

$erros = count(array_filter($itens, fn ($i) => $i['estado'] === 'erro'));
$https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
$host = (string) ($_SERVER['HTTP_HOST'] ?? 'SEU-DOMINIO');
$base = ($https ? 'https' : 'http') . '://' . $host . rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? '/'), '/');
$h = fn ($s) => htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8');
?><!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Verificar instalação</title>
<style>
  :root { --bg: #f3f5f2; --surface: #fff; --line: #dde3dc; --fg: #17201b; --muted: #5f6d64; --ok: #1f7a3a; --erro: #b4321f; --aviso: #8a5a00; --acc: #13866f; }
  @media (prefers-color-scheme: dark) { :root { --bg: #0e1412; --surface: #151d1a; --line: #26322d; --fg: #e4ebe7; --muted: #92a199; --ok: #5fd28a; --erro: #ff8a75; --aviso: #f2c062; --acc: #2bb394; color-scheme: dark; } }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; padding: 16px; }
  .wrap { max-width: 720px; margin: 0 auto; display: grid; gap: 14px; }
  h1 { margin: 0; font-size: 1.5rem; } p { margin: 0; }
  .card { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }
  .resumo { font-weight: 600; font-size: 1.05rem; }
  .resumo.ok { color: var(--ok); } .resumo.erro { color: var(--erro); }
  .item { display: flex; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--line); }
  .item:last-child { border-bottom: 0; }
  .ic { flex: none; width: 22px; font-weight: 700; }
  .ok .ic { color: var(--ok); } .erro .ic { color: var(--erro); } .aviso .ic { color: var(--aviso); }
  .item small { display: block; color: var(--muted); }
  code { background: var(--bg); padding: 1px 6px; border-radius: 6px; overflow-wrap: anywhere; }
  button { font: inherit; cursor: pointer; border: 0; border-radius: 10px; background: var(--acc); color: #fff; padding: 9px 14px; font-weight: 600; }
  input { font: inherit; padding: 9px 12px; border-radius: 10px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); width: 100%; }
  .linha { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
  .linha input { flex: 1 1 200px; }
  .muted { color: var(--muted); font-size: 14px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Verificar instalação</h1>
  <div class="card">
    <p class="resumo <?= $erros ? 'erro' : 'ok' ?>"><?= $erros ? "Faltam {$erros} coisa(s) para funcionar. Veja os itens com ✗ abaixo." : '✓ Tudo certo para usar o simulador.' ?></p>
  </div>

  <div class="card">
    <?php foreach ($itens as $i): ?>
      <div class="item <?= $h($i['estado']) ?>">
        <span class="ic"><?= $i['estado'] === 'ok' ? '✓' : ($i['estado'] === 'erro' ? '✗' : '!') ?></span>
        <div><?= $h($i['titulo']) ?><?php if ($i['estado'] !== 'ok' && $i['ajuda']): ?><small><?= $h($i['ajuda']) ?></small><?php endif; ?></div>
      </div>
    <?php endforeach; ?>
    <div class="item" id="itemAcesso"><span class="ic" id="icAcesso">…</span><div id="txtAcesso">Conferindo se a pasta de dados está protegida…</div></div>
  </div>

  <div class="card">
    <strong>Testar a IA agora</strong>
    <p class="muted">Faz uma chamada mínima (custa menos de 1 centavo) para confirmar que a chave e os créditos funcionam.</p>
    <div class="linha"><input id="senha" type="password" placeholder="Senha do simulador" autocomplete="current-password"><button type="button" id="btnIa">Testar</button></div>
    <p id="resIa" style="margin-top:8px"></p>
  </div>

  <div class="card">
    <strong>Endereço do webhook (para a Meta, depois)</strong>
    <p class="muted" style="margin:4px 0 8px">Cole este endereço no painel da Meta, em WhatsApp → Configuração → Webhook:</p>
    <p><code><?= $h($base) ?>/webhook.php</code></p>
    <?php if (!$https): ?><p class="muted" style="margin-top:8px">⚠ Esta página abriu sem https. A Meta exige https: confira se o certificado SSL do domínio está ativo na Hostinger.</p><?php endif; ?>
  </div>

  <p class="muted">Quando tudo estiver certo, abra <a href="simulador.html">simulador.html</a>. Depois de instalar, <strong>apague o arquivo verificar.php</strong> da hospedagem.</p>
</div>
<script>
  const $ = (id) => document.getElementById(id);
  (async () => {
    // Tenta abrir um arquivo da pasta dados: se abrir, a pasta está exposta na internet.
    let estado = 'ok', txt = 'Pasta de dados protegida (ninguém de fora consegue abrir)';
    try {
      const r = await fetch('dados/_teste_acesso.txt', { cache: 'no-store' });
      const t = r.ok ? await r.text() : '';
      if (r.ok && t.includes('VISIVEL')) { estado = 'erro'; txt = 'ATENÇÃO: a pasta dados/ está aberta na internet. Confira se o arquivo dados/.htaccess existe (precisa conter “Require all denied”) e peça ajuda antes de usar com pacientes.'; }
    } catch (e) { /* não abriu: protegido */ }
    $('itemAcesso').className = 'item ' + estado; $('icAcesso').textContent = estado === 'ok' ? '✓' : '✗'; $('txtAcesso').textContent = txt;
    fetch('verificar.php', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ acao: 'limpar_teste' }) }).catch(() => {});
  })();
  $('btnIa').addEventListener('click', async () => {
    $('resIa').textContent = 'Testando…';
    try {
      const r = await fetch('verificar.php', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ acao: 'testar_ia', senha: $('senha').value }) });
      const j = await r.json();
      $('resIa').textContent = j.ok ? `✓ A IA respondeu (“${j.texto}”) usando ${j.modelo}. Chave e créditos funcionando.` : `✗ ${j.erro}${j.dica ? ' → ' + j.dica : ''}`;
    } catch (e) { $('resIa').textContent = '✗ Não consegui testar: ' + e.message; }
  });
</script>
</body>
</html>
