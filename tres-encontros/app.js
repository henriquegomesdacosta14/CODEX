/* Três Encontros: app do devocional de 30 dias.
   Funciona offline depois do primeiro acesso. O progresso fica no celular e é copiado para o servidor. */
(function () {
  "use strict";

  var API = "api.php";
  var CONTEUDO = "conteudo/mes-01.json";
  var CODIGO_DEMO = "DEMO";
  var DIAS_DEMO = 3;
  var TOTAL = 30;

  var MOMENTOS = [
    { id: "manha", nome: "Bom dia com o Espírito Santo", curto: "Manhã", pessoa: "Espírito Santo", pratica: "Para hoje", padrao: "06:30", pergunta: "a que horas você acorda?" },
    { id: "almoco", nome: "Boa tarde com Jesus", curto: "Almoço", pessoa: "Jesus", pratica: "Atitude", padrao: "12:00", pergunta: "a que horas você almoça?" },
    { id: "noite", nome: "Boa noite com Deus Pai", curto: "Noite", pessoa: "Deus Pai", pratica: "Oração", padrao: "21:30", pergunta: "a que horas você se recolhe?" }
  ];
  var SAUDACAO = { manha: "Bom dia", almoco: "Boa tarde", noite: "Boa noite" };

  var ICONES = {
    manha: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M5 17a7 7 0 0 1 14 0"/><path d="M2 17h20M12 4v3M4.9 9.9l1.4 1.4M19.1 9.9l-1.4 1.4M8 21h8"/></svg>',
    almoco: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    noite: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/><path d="M17 3v2M16 4h2"/></svg>',
    hoje: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M3 18a9 9 0 0 1 18 0"/><circle cx="12" cy="18" r="1.5" fill="currentColor"/><path d="M2 21h20"/></svg>',
    jornada: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="5" cy="6" r="1.5"/><circle cx="12" cy="6" r="1.5"/><circle cx="19" cy="6" r="1.5"/><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/><circle cx="5" cy="18" r="1.5"/><circle cx="12" cy="18" r="1.5"/><circle cx="19" cy="18" r="1.5"/></svg>',
    ajustes: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/></svg>',
    livro: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5"/></svg>',
    voltar: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>',
    cadeado: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
    ok: '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>',
    sino: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/></svg>',
    presente: '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8M12 8v13M12 8c-1.5-3-5-4-5.5-2S9 8 12 8zm0 0c1.5-3 5-4 5.5-2S15 8 12 8z"/></svg>'
  };

  /* ---------- Estado ---------- */
  var conteudo = null;
  var config = { chaveAvisos: "", linkCompra: "", linkProximoMes: "" };
  var app = document.getElementById("app");
  var apresentacao = { ativa: false, dia: 1, hora: "agora" };
  var instalar = null; // evento de instalação do Android
  var notasSujas = {};
  var timerSync = null;
  var tela = { passo: 0 };
  var swRegistrado = false;

  var estado = ler("estado") || {};

  function ler(chave) {
    try { var v = localStorage.getItem("te:" + chave); return v ? JSON.parse(v) : null; } catch (e) { return null; }
  }
  function gravar(chave, valor) {
    try { localStorage.setItem("te:" + chave, JSON.stringify(valor)); } catch (e) { /* armazenamento indisponível */ }
  }
  function salvarEstado(sincronizar) {
    gravar("estado", estado);
    informarServiceWorker();
    if (sincronizar && !estado.demo) agendarSync();
  }

  /* ---------- Datas ---------- */
  function agora() {
    if (!apresentacao.ativa) return new Date();
    var d = dataLocal(estado.inicio || hojeISO(new Date()));
    d.setDate(d.getDate() + apresentacao.dia - 1);
    if (apresentacao.hora === "agora") { var n = new Date(); d.setHours(n.getHours(), n.getMinutes()); return d; }
    if (apresentacao.hora === "cedo") { d.setHours(5, 0); return d; }
    var hm = horario(apresentacao.hora).split(":");
    d.setHours(+hm[0], +hm[1] + 1);
    return d;
  }
  function hojeISO(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function dataLocal(iso) { var p = iso.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function diaDeHoje() {
    if (!estado.inicio) return 1;
    var a = dataLocal(estado.inicio), b = agora();
    b = new Date(b.getFullYear(), b.getMonth(), b.getDate());
    return Math.round((b - a) / 864e5) + 1;
  }
  function horario(m) { return (estado.horarios && estado.horarios[m]) || momento(m).padrao; }
  function minutos(hm) { var p = hm.split(":"); return +p[0] * 60 + +p[1]; }
  function minutosAgora() { var d = agora(); return d.getHours() * 60 + d.getMinutes(); }
  function momento(id) { for (var i = 0; i < MOMENTOS.length; i++) if (MOMENTOS[i].id === id) return MOMENTOS[i]; return MOMENTOS[0]; }

  /** Qual momento do dia é agora, pelos horários da pessoa (antes da manhã ainda é noite). */
  function momentoDoRelogio() {
    var t = minutosAgora();
    if (t >= minutos(horario("noite"))) return "noite";
    if (t >= minutos(horario("almoco"))) return "almoco";
    if (t >= minutos(horario("manha"))) return "manha";
    return "noite";
  }

  function limiteDias() {
    var disponivel = conteudo ? conteudo.dias.length : 0;
    return Math.min(disponivel, estado.demo && !apresentacao.ativa ? DIAS_DEMO : TOTAL);
  }
  function aberto(d, m) {
    if (d < 1 || d > limiteDias()) return false;
    var hoje = diaDeHoje();
    if (apresentacao.ativa) return true; // na apresentação, todos os dias ficam abertos para conferir
    return d <= hoje; // os três encontros do dia abrem à meia-noite; o horário é só para o lembrete
  }
  function concluido(d, m) { return (estado.concluidos || []).indexOf(d + "-" + m) >= 0; }
  function totalConcluidos() { return (estado.concluidos || []).length; }
  function jornadaConcluida() { return concluido(30, "noite") || diaDeHoje() > TOTAL; }
  function blocoDoDia(d) { return conteudo.blocos[Math.min(2, Math.floor((d - 1) / 10))]; }
  function diaConteudo(d) { return conteudo.dias[d - 1]; }


  /* ---------- Utilidades ---------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function aviso(texto) {
    var el = document.getElementById("aviso");
    el.textContent = texto; el.hidden = false;
    clearTimeout(aviso.t); aviso.t = setTimeout(function () { el.hidden = true; }, 3200);
  }
  function api(acao, dados) {
    return fetch(API, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ acao: acao }, dados || {}))
    }).then(function (r) {
      return r.json().catch(function () { return { ok: false, erro: "Resposta inválida do servidor." }; });
    });
  }
  function definirMomentoVisual(m) {
    document.body.setAttribute("data-momento", m);
    var cor = getComputedStyle(document.body).getPropertyValue("--bg").trim();
    var meta = document.getElementById("corTema");
    if (meta && cor) meta.setAttribute("content", cor);
  }
  function primeiroNome() { return (estado.nome || "").trim().split(/\s+/)[0] || ""; }
  function plural(n, um, varios) { return n === 1 ? um : varios; }

  /* ---------- Sincronização ---------- */
  function agendarSync() {
    clearTimeout(timerSync);
    timerSync = setTimeout(sincronizar, 1500);
  }
  function sincronizar() {
    if (!estado.codigo || estado.demo || !navigator.onLine) return;
    var notas = {};
    Object.keys(notasSujas).forEach(function (k) { notas[k] = (estado.notas || {})[k] || ""; });
    api("salvar", { codigo: estado.codigo, nome: estado.nome || "", horarios: estado.horarios, concluidos: estado.concluidos || [], notas: notas })
      .then(function (r) { if (r.ok) notasSujas = {}; })
      .catch(function () { /* tenta de novo na próxima mudança */ });
  }
  window.addEventListener("online", sincronizar);

  /** Junta o que veio do servidor com o que já estava no celular. */
  function mesclarPerfil(p) {
    var locais = estado.concluidos || [];
    var todos = locais.concat((p.concluidos || []).filter(function (k) { return locais.indexOf(k) < 0; }));
    var notas = Object.assign({}, p.notas || {}, estado.notas || {});
    estado = Object.assign({}, estado, {
      codigo: p.codigo, inicio: p.inicio, demo: false,
      nome: estado.nome || p.nome || "",
      horarios: estado.horarios || p.horarios || null,
      concluidos: todos, notas: notas
    });
    if (p.horarios) estado.configurado = true;
  }

  /* ---------- Service worker e avisos ---------- */
  function informarServiceWorker() {
    if (!("serviceWorker" in navigator) || !swRegistrado) return;
    var msg = { tipo: "estado", dados: { inicio: estado.inicio, horarios: estado.horarios, demo: !!estado.demo, nome: primeiroNome(),
      titulos: conteudo ? conteudo.dias.map(function (d) { return d.titulo; }) : [] } };
    navigator.serviceWorker.ready.then(function (reg) { if (reg.active) reg.active.postMessage(msg); }).catch(function () {});
  }
  function registrarServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    if (location.protocol !== "https:" && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") return;
    navigator.serviceWorker.register("sw.js").then(function () {
      swRegistrado = true;
      informarServiceWorker();
    }).catch(function () { /* sem modo offline neste navegador */ });
  }
  function avisosSuportados() { return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window; }
  function ehIphone() { return /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); }
  function instalado() { return window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true; }
  function chaveParaBytes(b64) {
    var pad = "=".repeat((4 - b64.length % 4) % 4);
    var bin = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function ativarAvisos() {
    if (estado.demo) return Promise.resolve("demo");
    if (!avisosSuportados()) return Promise.resolve(ehIphone() && !instalado() ? "instalar" : "sem-suporte");
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") return "negado";
      return (config.chaveAvisos ? Promise.resolve() : carregarConfig()).then(function () {
        if (!config.chaveAvisos) return "sem-servidor";
        return navigator.serviceWorker.ready.then(function (reg) {
          return reg.pushManager.getSubscription().then(function (s) {
            return s || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chaveParaBytes(config.chaveAvisos) });
          });
        }).then(function (sub) {
          var fuso = "America/Sao_Paulo";
          try { fuso = Intl.DateTimeFormat().resolvedOptions().timeZone || fuso; } catch (e) { /* usa o padrão */ }
          return api("inscrever_avisos", { codigo: estado.codigo, endpoint: sub.endpoint, fuso: fuso });
        }).then(function (r) {
          if (!r.ok) return "sem-servidor";
          estado.avisos = true; salvarEstado(false); return "ok";
        });
      });
    }).catch(function () { return "sem-servidor"; });
  }
  function desativarAvisos() {
    estado.avisos = false; salvarEstado(false);
    if (!avisosSuportados()) return;
    navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (s) {
      if (!s) return;
      api("cancelar_avisos", { endpoint: s.endpoint }).catch(function () {});
      return s.unsubscribe();
    }).catch(function () {});
  }
  function mensagemAvisos(res) {
    return {
      ok: "Pronto. Você vai receber um aviso em cada encontro.",
      negado: "Os avisos foram bloqueados. Libere nas configurações do celular para este app.",
      instalar: "No iPhone, primeiro adicione o app à tela de início. Depois ative os avisos aqui.",
      "sem-suporte": "Este navegador não recebe avisos. Tente pelo Chrome no Android ou pelo app instalado no iPhone.",
      "sem-servidor": "Não foi possível ativar os avisos agora. Verifique a internet e tente de novo.",
      demo: "Na degustação, os avisos ficam desligados. Eles funcionam com o código de acesso."
    }[res] || "";
  }
  function carregarConfig() {
    return api("publico").then(function (r) { if (r.ok) config = Object.assign(config, r); }).catch(function () {});
  }
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); instalar = e; });

  /* ---------- Rotas ---------- */
  function rotaAtual() {
    var h = (location.hash || "").replace(/^#/, "");
    if (h === "apresentacao") return "inicio";
    return h || "inicio";
  }
  function ir(rota) {
    if (rotaAtual() === rota) render(); else location.hash = rota;
  }
  window.addEventListener("hashchange", function () { render(); window.scrollTo(0, 0); });

  function render() {
    if (!conteudo) return;
    renderTela();
    // Na apresentação, a barra de controle aparece em todas as telas.
    if (apresentacao.ativa && !app.querySelector(".apresentacao")) app.insertAdjacentHTML("afterbegin", barraApresentacao());
  }

  function renderTela() {
    if (!estado.codigo) { renderEntrada(); return; }
    if (!estado.configurado) { renderConfiguracao(); return; }
    var rota = rotaAtual(), m;
    app.classList.remove("sem-menu");
    if ((m = rota.match(/^encontro-(\d+)-(manha|almoco|noite)$/))) return renderEncontro(+m[1], m[2]);
    if ((m = rota.match(/^dia-(\d+)$/))) return renderDia(+m[1]);
    if (rota === "jornada") return renderJornada();
    if (rota === "ajustes") return renderAjustes();
    if (rota === "final" && jornadaConcluida()) return renderFinal();
    if (rota === "fim-degustacao" && apresentacao.ativa) return renderFimDemo();
    return renderHoje();
  }

  function menu(ativo) {
    var itens = [["inicio", "Hoje", ICONES.hoje], ["jornada", "Jornada", ICONES.jornada], ["ajustes", "Ajustes", ICONES.ajustes]];
    return '<div class="menu"><nav aria-label="Menu">' + itens.map(function (i) {
      return '<a href="#' + i[0] + '"' + (ativo === i[0] ? ' aria-current="page"' : "") + ">" + i[2] + "<span>" + i[1] + "</span></a>";
    }).join("") + "</nav></div>";
  }

  function barraApresentacao() {
    if (!apresentacao.ativa) return "";
    var opcoes = [["agora", "Hora real"], ["cedo", "Madrugada"], ["manha", "Depois da manhã"], ["almoco", "Depois do almoço"], ["noite", "Depois da noite"]];
    return '<div class="apresentacao"><strong>Apresentação</strong>' +
      '<input type="range" id="apDia" min="1" max="31" value="' + apresentacao.dia + '" aria-label="Dia simulado">' +
      '<span class="numeros" id="apRotulo">' + (apresentacao.dia > 30 ? "Depois do dia 30" : "Dia " + apresentacao.dia) + "</span>" +
      '<select id="apHora" aria-label="Hora simulada">' + opcoes.map(function (o) {
        return '<option value="' + o[0] + '"' + (apresentacao.hora === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
      }).join("") + "</select>" +
      '<select id="apIr" aria-label="Ir para a tela"><option value="">Ir para a tela…</option>' + [
        ["boas-vindas", "1. Boas-vindas"], ["codigo", "2. Digitar o código"], ["abertura", "3. Abertura (3 telas)"],
        ["marque", "4. Marque seus encontros"], ["convites", "5. Ativar os convites"], ["hoje", "6. Hoje"],
        ["encontro", "7. Um encontro"], ["jornada", "8. Jornada"], ["ajustes", "9. Ajustes"],
        ["fim-degustacao", "10. Fim da degustação"], ["final", "11. Encerramento do dia 30"], ["admin", "12. Área do administrador"]
      ].map(function (o) { return '<option value="' + o[0] + '">' + o[1] + "</option>"; }).join("") + "</select></div>";
  }

  /* ---------- Entrada ---------- */
  function marcaSvg() {
    return '<svg viewBox="0 0 160 96" aria-hidden="true">' +
      '<path d="M14 82 Q80 -18 146 82" fill="none" stroke="var(--line)" stroke-width="2.5" stroke-dasharray="2 7" stroke-linecap="round"/>' +
      '<line x1="6" y1="82" x2="154" y2="82" stroke="var(--line)" stroke-width="2"/>' +
      '<circle cx="34" cy="50" r="10" fill="#E89A5B"/><circle cx="80" cy="32" r="12" fill="#E3B23C"/>' +
      '<path d="M134 44a11 11 0 1 1-12-12 8.5 8.5 0 0 0 12 12z" fill="#7F72C9"/></svg>';
  }

  function renderEntrada() {
    app.classList.add("sem-menu");
    definirMomentoVisual(momentoDoRelogio());
    if (tela.passo === "codigo") {
      app.innerHTML = '<section class="passo entra">' +
        '<button class="voltar" data-acao="voltar-inicio">' + ICONES.voltar + " Voltar</button>" +
        '<div class="pilha"><span class="rotulo acento">Seu acesso</span><h1>Digite o seu código</h1>' +
        '<p class="mudo">Ele chegou junto com a compra ou com o presente que você recebeu. O formato é TE-XXXX-XXXX.</p></div>' +
        '<form class="pilha" id="formCodigo" novalidate>' +
        '<label class="campo"><span class="rotulo-campo">Código de acesso</span>' +
        '<input class="entrada codigo" id="codigo" autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" maxlength="14" placeholder="TE-XXXX-XXXX" inputmode="text"></label>' +
        '<p class="erro" id="erroCodigo" hidden></p>' +
        '<button class="btn cheio" type="submit" id="botaoEntrar">Entrar</button>' +
        (apresentacao.ativa ? '<p class="mudo" style="font-size:14px">Na apresentação, digite DEMO para entrar.</p>' : "") + "</form></section>";
      setTimeout(function () { var c = document.getElementById("codigo"); if (c) c.focus(); }, 50);
      return;
    }
    app.innerHTML = '<section class="boas-vindas entra">' +
      '<div class="marca">' + marcaSvg() + '<span class="rotulo acento">30 dias com Deus</span><h1>Três Encontros</h1>' +
      '<p class="lead">Ao acordar com o Espírito Santo. No almoço com Jesus. Antes de dormir com o Pai.</p></div>' +
      '<div class="tres"><div><b>Manhã</b><span>Espírito Santo</span></div><div><b>Almoço</b><span>Jesus</span></div><div><b>Noite</b><span>Deus Pai</span></div></div>' +
      '<div class="pilha"><button class="btn cheio" data-acao="tenho-codigo">Tenho um código de acesso</button>' +
      '<button class="btn secundario cheio" data-acao="demo">Experimentar 3 dias grátis</button></div></section>';
  }

  function entrarComCodigo(valor) {
    var erro = document.getElementById("erroCodigo"), botao = document.getElementById("botaoEntrar");
    var limpo = valor.toUpperCase().replace(/[^A-Z0-9]/g, "");
    function falha(msg) { erro.textContent = msg; erro.hidden = false; botao.disabled = false; botao.textContent = "Entrar"; }
    if (limpo === CODIGO_DEMO) return iniciarDemo();
    if (!/^TE[A-Z0-9]{8}$/.test(limpo)) return falha("Confira o código. Ele tem o formato TE-XXXX-XXXX.");
    botao.disabled = true; botao.textContent = "Entrando…";
    api("entrar", { codigo: limpo, hoje: hojeISO(new Date()) }).then(function (r) {
      if (!r.ok) return falha(r.erro || "Não foi possível entrar.");
      estado = { notas: {}, concluidos: [] };
      mesclarPerfil(r.perfil);
      salvarEstado(false);
      carregarConfig();
      tela.passo = 0;
      return carregarConteudo().then(render);
    }).catch(function () { falha("Sem conexão com o servidor. Verifique a internet e tente de novo."); });
  }

  function iniciarDemo() {
    estado = { codigo: CODIGO_DEMO, demo: true, inicio: hojeISO(new Date()), concluidos: [], notas: {} };
    salvarEstado(false);
    tela.passo = 0;
    render();
  }

  /* ---------- Configuração inicial (abertura, nome, horários, avisos) ---------- */
  function renderConfiguracao() {
    app.classList.add("sem-menu");
    definirMomentoVisual("manha");
    var passos = conteudo.abertura.length + 2;
    var p = typeof tela.passo === "number" ? tela.passo : 0;
    var pontos = '<div class="pontos" aria-hidden="true">' + Array.from({ length: passos }, function (_, i) {
      return "<i" + (i <= p ? ' class="ativo"' : "") + "></i>";
    }).join("") + "</div>";

    if (p < conteudo.abertura.length) {
      var pag = conteudo.abertura[p];
      app.innerHTML = '<section class="passo entra">' + pontos +
        '<span class="rotulo acento">Antes de começar · ' + (p + 1) + " de " + passos + "</span><h1>" + esc(pag.titulo) + "</h1>" +
        (p === 1 ? cicloSvg() : "") +
        '<div class="texto">' + pag.texto.map(function (t) { return "<p>" + esc(t) + "</p>"; }).join("") + "</div>" +
        '<button class="btn cheio" data-acao="passo" data-ir="' + (p + 1) + '">Continuar</button>' +
        (p > 0 ? '<button class="link" data-acao="passo" data-ir="' + (p - 1) + '">Voltar</button>' : "") + "</section>";
      return;
    }
    if (p === conteudo.abertura.length) {
      app.innerHTML = '<section class="passo entra">' + pontos +
        '<span class="rotulo acento">Seus encontros</span><h1>Marque seus encontros com Deus</h1>' +
        '<p class="mudo">Escolha o horário de cada encontro. Na hora marcada, você recebe um convite no celular. Os encontros do dia abrem à meia-noite, então dá para viver cada um antes ou depois, quando puder. Dá para mudar em Ajustes.</p>' +
        '<form class="pilha-g" id="formHorarios" novalidate>' +
        '<label class="campo"><span class="rotulo-campo">Como podemos te chamar? (aparece nos convites)</span><input class="entrada" id="nome" maxlength="40" autocomplete="given-name" placeholder="Seu primeiro nome" value="' + esc(estado.nome || "") + '"></label>' +
        camposHorarios() +
        '<button class="btn cheio" type="submit">Marcar meus encontros</button></form>' +
        '<button class="link" data-acao="passo" data-ir="' + (p - 1) + '">Voltar</button></section>';
      return;
    }
    app.innerHTML = '<section class="passo entra">' + pontos +
      '<span class="rotulo acento">Convites no celular</span><h1>Quer receber o convite na hora de cada encontro?</h1>' +
      '<p class="mudo">No horário que você marcou, chega um convite assim:</p>' + previaConvites(true) +
      blocoInstalacao() +
      '<p class="erro" id="erroAvisos" hidden></p>' +
      '<button class="btn cheio" data-acao="ativar-avisos-inicio">' + ICONES.sino + " Ativar os convites</button>" +
      '<button class="btn secundario cheio" data-acao="concluir-config">Agora não</button></section>';
  }

  function camposHorarios() {
    return '<div class="horarios">' + MOMENTOS.map(function (m) {
      return '<label class="horario"><span class="ic ' + m.id + '">' + ICONES[m.id] + "</span>" +
        "<span><b>" + m.pessoa + "</b><small>" + {manha: "Encontro da manhã", almoco: "Encontro do almoço", noite: "Encontro da noite"}[m.id] + "</small></span>" +
        '<input type="time" id="h-' + m.id + '" value="' + horario(m.id) + '" required aria-label="Horário: ' + m.nome + '"></label>';
    }).join("") + "</div>";
  }

  /** Mostra como chegam os convites, no formato de notificação do celular. */
  function previaConvites(soUm) {
    var dia = Math.max(1, Math.min(TOTAL, diaDeHoje()));
    var lista = soUm ? [MOMENTOS[1]] : MOMENTOS;
    return '<div class="convites">' + lista.map(function (m) {
      var l = window.TELembretes.montar(m.id, estado.nome, dia, conteudo && conteudo.dias[dia - 1] ? conteudo.dias[dia - 1].titulo : "");
      return '<div class="convite"><span class="ic ' + m.id + '">' + ICONES[m.id] + '</span><div><div class="linha" style="justify-content:space-between"><b>' + esc(l.titulo) +
        '</b><small class="numeros">' + horario(m.id) + "</small></div><p>" + esc(l.corpo).replace(/\n/g, "<br>") + "</p></div></div>";
    }).join("") + "</div>";
  }

  function testarConvite() {
    var m = momentoDoRelogio(), dia = Math.max(1, Math.min(TOTAL, diaDeHoje()));
    var l = window.TELembretes.montar(m, estado.nome, dia, diaConteudo(dia) ? diaConteudo(dia).titulo : "");
    function naTela() { aviso(l.titulo + ": " + l.corpo.split("\n")[0]); }
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !swRegistrado) return naTela();
    Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") return naTela();
      return navigator.serviceWorker.ready.then(function (reg) {
        return reg.showNotification(l.titulo, { body: l.corpo, icon: "icones/icone-192.png", tag: "teste", data: { rota: "#encontro-" + dia + "-" + m } });
      });
    }).catch(naTela);
  }

  function lerHorarios() {
    var h = {}, ok = true;
    MOMENTOS.forEach(function (m) {
      var v = (document.getElementById("h-" + m.id) || {}).value || "";
      if (!/^\d{2}:\d{2}$/.test(v)) ok = false;
      h[m.id] = v;
    });
    if (!ok) { aviso("Preencha os três horários."); return null; }
    if (!(minutos(h.manha) < minutos(h.almoco) && minutos(h.almoco) < minutos(h.noite))) {
      aviso("Os horários precisam estar em ordem: manhã, almoço e noite."); return null;
    }
    return h;
  }

  function blocoInstalacao() {
    if (instalado()) return "";
    if (ehIphone()) {
      return '<div class="dica">' + ICONES.sino + '<div><b>No iPhone, instale o app primeiro</b>' +
        "<ol><li>Toque no botão Compartilhar do Safari.</li><li>Escolha “Adicionar à Tela de Início”.</li><li>Abra o app pelo ícone e ative os avisos.</li></ol></div></div>";
    }
    if (instalar) {
      return '<div class="dica">' + ICONES.sino + '<div><b>Instale o app no seu celular</b><p>Ele fica na tela inicial, abre mais rápido e funciona sem internet.</p>' +
        '<button class="btn suave" data-acao="instalar" style="margin-top:10px">Instalar app</button></div></div>';
    }
    return "";
  }

  function cicloSvg() {
    return '<svg class="ciclo" viewBox="0 0 320 210" role="img" aria-label="O Espírito leva a Jesus, Jesus leva ao Pai, o Pai dá o Espírito">' +
      '<defs><marker id="seta" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--muted)"/></marker></defs>' +
      '<path d="M120 52 Q160 28 200 52" fill="none" stroke="var(--muted)" stroke-width="1.6" marker-end="url(#seta)"/>' +
      '<path d="M246 92 Q258 136 214 164" fill="none" stroke="var(--muted)" stroke-width="1.6" marker-end="url(#seta)"/>' +
      '<path d="M106 164 Q62 136 74 92" fill="none" stroke="var(--muted)" stroke-width="1.6" marker-end="url(#seta)"/>' +
      '<circle cx="80" cy="66" r="30" fill="#F6E1E2"/><circle cx="240" cy="66" r="30" fill="#DDECF1"/><circle cx="160" cy="176" r="30" fill="#252B52"/>' +
      '<text x="80" y="70" text-anchor="middle" style="fill:#7d2a3c">Espírito</text>' +
      '<text x="240" y="70" text-anchor="middle" style="fill:#124b5e">Jesus</text>' +
      '<text x="160" y="180" text-anchor="middle" style="fill:#F3D58C">Pai</text></svg>';
  }

  /* ---------- Hoje ---------- */
  function arcoSvg() {
    var ini = 300, fim = 1380; // 05:00 a 23:00
    function ponto(min) {
      var t = Math.max(0, Math.min(1, (min - ini) / (fim - ini)));
      return { x: 24 + 292 * t, y: 108 - 84 * Math.sin(Math.PI * t) };
    }
    function caminho(ate) {
      var pts = [], passos = 48;
      for (var i = 0; i <= passos; i++) {
        var min = ini + (ate - ini) * i / passos, p = ponto(min);
        pts.push((i ? "L" : "M") + p.x.toFixed(1) + " " + p.y.toFixed(1));
      }
      return pts.join(" ");
    }
    var hoje = diaDeHoje(), agoraMin = Math.max(ini, Math.min(fim, minutosAgora()));
    var marcos = MOMENTOS.map(function (m) {
      var p = ponto(minutos(horario(m.id)));
      var cls = concluido(hoje, m.id) ? "marco concluido" : (aberto(hoje, m.id) ? "marco aberto" : "marco");
      return '<circle class="' + cls + '" cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="8"/>' +
        '<text x="' + p.x.toFixed(1) + '" y="' + (p.y + 24).toFixed(1) + '" text-anchor="middle">' + horario(m.id) + "</text>";
    }).join("");
    var a = ponto(agoraMin), noite = momentoDoRelogio() === "noite" && minutosAgora() >= minutos(horario("noite"));
    var astro = noite
      ? '<path class="astro" transform="translate(' + (a.x - 9).toFixed(1) + " " + (a.y - 9).toFixed(1) + ')" d="M16 11a7 7 0 1 1-8-8 5.5 5.5 0 0 0 8 8z"/>'
      : '<circle class="astro" cx="' + a.x.toFixed(1) + '" cy="' + a.y.toFixed(1) + '" r="6"/>';
    return '<svg class="arco" viewBox="0 0 340 136" role="img" aria-label="Os três encontros de hoje ao longo do dia">' +
      '<line class="horizonte" x1="8" y1="108" x2="332" y2="108"/>' +
      '<path class="trilha" d="' + caminho(fim) + '"/>' +
      '<path class="feito" d="' + caminho(agoraMin) + '"/>' + marcos + astro + "</svg>";
  }

  function cartaoEncontro(d, m) {
    var mo = momento(m), dc = diaConteudo(d)[m];
    var feito = concluido(d, m), ab = aberto(d, m);
    var estadoTxt = feito ? "Vivido" : (ab ? horario(m) : ICONES.cadeado);
    var cls = "encontro" + (feito ? " concluido" : "") + (ab ? "" : " fechado");
    return '<button class="' + cls + '"' + (ab ? ' data-ir="encontro-' + d + "-" + m + '"' : ' disabled aria-disabled="true"') + ">" +
      '<span class="ic ' + m + '">' + ICONES[m] + "</span>" +
      '<span class="tx"><b>' + mo.nome + "</b><small>" + (ab ? esc(dc.versiculo.referencia) : "Abre à meia-noite") + "</small></span>" +
      '<span class="estado">' + estadoTxt + "</span></button>";
  }

  function renderHoje() {
    var hoje = diaDeHoje(), relogio = momentoDoRelogio();
    definirMomentoVisual(relogio);
    if (hoje > limiteDias() && hoje <= TOTAL) return renderFimDemo();
    if (jornadaConcluida() && hoje > TOTAL) return renderFinal();
    var d = Math.max(1, Math.min(TOTAL, hoje)), dia = diaConteudo(d), bloco = blocoDoDia(d);
    var nome = primeiroNome();
    // Sugere o encontro do momento atual; se já foi vivido, o primeiro que ainda falta hoje.
    var pendente = null;
    [relogio].concat(MOMENTOS.map(function (x) { return x.id; })).some(function (m) {
      if (aberto(d, m) && !concluido(d, m)) { pendente = m; return true; }
      return false;
    });
    var destaque;
    if (pendente) {
      var mo = momento(pendente);
      destaque = '<button class="cartao sombra destaque entra" data-ir="encontro-' + d + "-" + pendente + '">' +
        '<span class="rotulo acento">' + mo.nome + "</span><h2>" + esc(dia.titulo) + "</h2>" +
        '<span class="trecho">“' + esc(dia[pendente].versiculo.texto) + '”</span>' +
        '<span class="ref">' + esc(dia[pendente].versiculo.referencia) + "</span>" +
        '<span class="btn">Começar o encontro</span></button>';
    } else {
      if (d < limiteDias()) {
        destaque = '<div class="cartao destaque"><span class="rotulo acento">Você viveu os três encontros de hoje</span>' +
          "<h2>Amanhã: " + esc(diaConteudo(d + 1).titulo) + "</h2>" +
          '<p class="mudo">Os encontros do dia ' + (d + 1) + " abrem à meia-noite. Descanse em paz.</p></div>";
      } else if (limiteDias() < TOTAL) {
        destaque = '<div class="cartao destaque"><span class="rotulo acento">Você viveu os três encontros de hoje</span>' +
          "<h2>Hoje é o último dia da degustação</h2>" +
          '<p class="mudo">Para continuar a jornada depois do dia ' + limiteDias() + ", é só adquirir o seu código de acesso.</p></div>";
      } else {
        destaque = '<a class="cartao sombra destaque" href="#final"><span class="rotulo acento">Jornada concluída</span><h2>Você viveu os 30 dias</h2><span class="btn">Abrir</span></a>';
      }
    }
    var total = totalConcluidos();
    app.innerHTML = barraApresentacao() +
      '<header class="saudacao"><span class="rotulo acento">Dia ' + d + " de " + TOTAL + " · " + esc(bloco.titulo.replace(/^Bloco \d+ — /, "")) + "</span>" +
      "<h1>" + SAUDACAO[relogio] + (nome ? ", " + esc(nome) : "") + ".</h1>" +
      '<p class="mudo">' + esc(bloco.subtitulo) + "</p></header>" +
      arcoSvg() +
      '<div class="pilha-g">' + destaque +
      '<section class="pilha" aria-labelledby="tHoje"><h3 id="tHoje">Os encontros de hoje</h3><div class="encontros">' +
      MOMENTOS.map(function (mm) { return cartaoEncontro(d, mm.id); }).join("") + "</div></section>" +
      '<section class="pilha" aria-labelledby="tConvites"><div class="linha" style="justify-content:space-between"><h3 id="tConvites">Seus encontros marcados</h3>' +
      '<a class="link" href="#ajustes">Mudar horários</a></div>' +
      '<p class="mudo" style="font-size:14px">No horário marcado, você recebe um convite assim no celular:</p>' + previaConvites(false) +
      (!estado.avisos && !estado.demo ? '<button class="btn suave" data-acao="ativar-avisos">' + ICONES.sino + " Ativar os convites</button>" : "") +
      "</section>" +
      '<section class="progresso"><div class="linha" style="justify-content:space-between"><span class="rotulo">Sua jornada</span>' +
      '<span class="mudo numeros">' + total + " de 90 " + plural(total, "encontro vivido", "encontros vividos") + "</span></div>" +
      '<div class="barra"><i style="width:' + Math.round(total / 90 * 100) + '%"></i></div></section>' +
      (estado.demo && !apresentacao.ativa ? cartaoDemo() : "") + "</div>" + menu("inicio");
  }


  function cartaoDemo() {
    return '<div class="cartao pilha"><span class="rotulo acento">Degustação</span><h3>Você está vivendo os 3 primeiros dias</h3>' +
      '<p class="mudo">Gostou? Com o código de acesso você vive os 30 dias, com avisos no celular e as suas anotações guardadas.</p>' +
      botaoCompra("Quero os 30 dias") + "</div>";
  }

  function botaoCompra(texto, link) {
    var url = link || config.linkCompra;
    if (url) return '<a class="btn cheio" href="' + esc(url) + '" target="_blank" rel="noopener">' + texto + "</a>";
    return '<button class="btn cheio" data-acao="sem-link">' + texto + "</button>";
  }

  function renderFimDemo() {
    definirMomentoVisual(momentoDoRelogio());
    app.innerHTML = barraApresentacao() + '<section class="final entra"><div class="coroa">' + ICONES.ok + '<span class="rotulo acento">Fim da degustação</span>' +
      "<h1>Os três primeiros dias terminaram</h1>" +
      '<p class="mudo">Você conheceu o Espírito Santo como Pessoa, como Aquele que mora em você e que convence com amor. Ainda faltam 27 dias de encontros com o Espírito, com Jesus e com o Pai.</p></div>' +
      botaoCompra("Quero continuar os 30 dias") +
      '<button class="btn secundario cheio" data-acao="sair">Já comprei, quero digitar o código</button></section>' + menu("inicio");
  }

  /* ---------- Encontro ---------- */
  function renderEncontro(d, m) {
    if (!aberto(d, m)) { aviso("Este dia ainda não chegou."); ir("inicio"); return; }
    definirMomentoVisual(m);
    var mo = momento(m), dia = diaConteudo(d), enc = dia[m], chave = d + "-" + m;
    var nota = (estado.notas || {})[chave] || "", feito = concluido(d, m);
    app.innerHTML = barraApresentacao() +
      '<div class="barra-leitura"><button class="voltar" data-acao="voltar">' + ICONES.voltar + " Voltar</button>" +
      '<span class="selo numeros">Dia ' + d + " de " + TOTAL + "</span></div>" +
      '<article class="leitura entra"><header class="cab"><span class="rotulo acento linha">' + ICONES[m] + " " + mo.nome + "</span>" +
      "<h1>" + esc(dia.titulo) + '</h1><span class="mudo">' + esc(blocoDoDia(d).titulo.replace(/^Bloco \d+ — /, "")) + "</span></header>" +
      '<figure class="palavra"><span class="aspas" aria-hidden="true">“</span><span class="rotulo acento">Palavra de hoje</span>' +
      "<blockquote>" + esc(enc.versiculo.texto) + "</blockquote>" +
      "<figcaption>" + esc(enc.versiculo.referencia) + "</figcaption>" +
      (enc.referencia !== enc.versiculo.referencia ? '<p class="leia">' + ICONES.livro + " Leia na sua Bíblia: " + esc(enc.referencia) + "</p>" : "") + "</figure>" +
      '<section class="pilha"><span class="rotulo acento">Reflexão</span>' +
      '<div class="reflexao' + (/^[A-Za-zÀ-ÿ]/.test(enc.texto[0]) ? " capitular" : "") + '">' + enc.texto.map(function (t) { return "<p>" + esc(t) + "</p>"; }).join("") + "</div></section>" +
      (enc.inspiracao ? '<aside class="voz"><span class="rotulo acento">Na voz de quem caminhou</span><p>' + esc(enc.inspiracao.texto) + "</p>" +
        '<span class="autor">' + esc(enc.inspiracao.autor) + " · <i>" + esc(enc.inspiracao.livro) + "</i></span></aside>" : "") +
      '<div class="ornamento" aria-hidden="true"><i></i><i></i><i></i></div>' +
      '<section class="cartao pergunta"><span class="rotulo acento">Para refletir</span><p class="q">' + esc(enc.pergunta) + "</p>" +
      '<textarea class="notas" id="nota" data-chave="' + chave + '" placeholder="Escreva aqui o que vier ao seu coração. Só você vê.">' + esc(nota) + "</textarea>" +
      '<span class="salvo" id="salvo"></span></section>' +
      '<section class="pratica' + (m === "noite" ? " oracao" : "") + '"><span class="rotulo acento">' + mo.pratica + "</span><p>" + esc(enc.pratica) + "</p></section>" +
      '<div id="fechamento">' + (feito ? blocoConcluido(d, m) : '<div class="concluir"><button class="btn cheio" data-acao="concluir" data-dia="' + d + '" data-momento="' + m + '">Concluir este encontro</button>' +
        '<span class="mudo" style="font-size:14px">Fique o tempo que precisar. Não há pressa.</span></div>') + "</div>" +
      "</article>" + menu("");
  }

  function blocoConcluido(d, m) {
    var idx = ["manha", "almoco", "noite"].indexOf(m), texto;
    if (d === TOTAL && m === "noite") {
      return '<div class="feito-ok">' + ICONES.ok + "<h3>Você viveu os 30 dias</h3>" +
        '<a class="btn" href="#final">Ver o encerramento</a></div>';
    }
    if (idx < 2) {
      var prox = MOMENTOS[idx + 1];
      texto = concluido(d, prox.id) ? "Você já viveu " + prox.nome + " hoje." : "Quando quiser, " + prox.nome + " já está esperando por você (lembrete às " + horario(prox.id) + ").";
    } else {
      texto = d < limiteDias() ? "Amanhã: " + diaConteudo(d + 1).titulo + ". Os encontros abrem à meia-noite." : "Você chegou ao fim desta etapa.";
    }
    return '<div class="feito-ok">' + ICONES.ok + "<h3>Encontro vivido</h3><p class=\"mudo\">" + esc(texto) + "</p>" +
      '<a class="btn suave" href="#inicio">Voltar para hoje</a></div>';
  }

  function concluirEncontro(d, m) {
    var chave = d + "-" + m;
    estado.concluidos = estado.concluidos || [];
    if (estado.concluidos.indexOf(chave) < 0) estado.concluidos.push(chave);
    salvarEstado(true);
    var f = document.getElementById("fechamento");
    if (f) f.innerHTML = blocoConcluido(d, m);
    if (navigator.vibrate) { try { navigator.vibrate(18); } catch (e) { /* sem vibração */ } }
  }

  /* ---------- Jornada ---------- */
  function renderJornada() {
    definirMomentoVisual(momentoDoRelogio());
    var hoje = diaDeHoje();
    var blocos = conteudo.blocos.map(function (b, i) {
      var cells = "";
      for (var d = i * 10 + 1; d <= i * 10 + 10; d++) {
        var passado = aberto(d, "manha");
        var gotas = MOMENTOS.map(function (m) { return "<i" + (concluido(d, m.id) ? ' class="ok"' : "") + "></i>"; }).join("");
        var cls = "dia" + (d === hoje ? " hoje" : "") + (passado ? "" : " futuro") + (estado.demo && d > DIAS_DEMO && !apresentacao.ativa ? " bloq-demo" : "");
        cells += '<button class="' + cls + '"' + (passado ? ' data-ir="dia-' + d + '"' : ' disabled aria-disabled="true"') +
          ' aria-label="Dia ' + d + (passado ? ": " + esc(diaConteudo(d).titulo) : ", ainda não liberado") + '"><b class="numeros">' + d + '</b><span class="gotas">' + gotas + "</span></button>";
      }
      return '<section class="bloco"><div class="bloco-cab"><span class="rotulo acento">Dias ' + (i * 10 + 1) + " a " + (i * 10 + 10) + "</span>" +
        "<h2>" + esc(b.titulo.replace(/^Bloco \d+ — /, "")) + "</h2><p>" + esc(b.subtitulo) + '</p></div><div class="dias">' + cells + "</div></section>";
    }).join("");
    app.innerHTML = barraApresentacao() + '<header class="saudacao"><span class="rotulo acento">Jornada</span><h1>30 dias, 90 encontros</h1>' +
      '<p class="mudo numeros">' + totalConcluidos() + plural(totalConcluidos(), " encontro vivido", " encontros vividos") + " até agora.</p></header>" +
      '<div class="pilha-g">' + blocos + "</div>" + menu("jornada");
  }

  function renderDia(d) {
    if (!aberto(d, "manha")) { ir("jornada"); return; }
    definirMomentoVisual(momentoDoRelogio());
    var dia = diaConteudo(d);
    app.innerHTML = barraApresentacao() + '<div class="barra-leitura"><a class="voltar" href="#jornada">' + ICONES.voltar + " Jornada</a></div>" +
      '<header class="saudacao"><span class="rotulo acento">Dia ' + d + " · " + esc(blocoDoDia(d).titulo.replace(/^Bloco \d+ — /, "")) + "</span><h1>" + esc(dia.titulo) + "</h1></header>" +
      '<div class="encontros">' + MOMENTOS.map(function (m) { return cartaoEncontro(d, m.id); }).join("") + "</div>" + menu("jornada");
  }

  /* ---------- Ajustes ---------- */
  function renderAjustes() {
    definirMomentoVisual(momentoDoRelogio());
    var avisosTxt = estado.demo ? "Disponível com o código de acesso." : (estado.avisos ? "Ativados neste celular." : "Desligados.");
    app.innerHTML = barraApresentacao() + '<header class="saudacao"><span class="rotulo acento">Ajustes</span><h1>Do seu jeito</h1></header>' +
      '<div class="pilha-g">' +
      '<form class="cartao grupo" id="formAjustes" novalidate><h2>Seus encontros</h2>' +
      '<label class="campo"><span class="rotulo-campo">Seu nome (aparece nos convites)</span><input class="entrada" id="nome" maxlength="40" value="' + esc(estado.nome || "") + '"></label>' +
      camposHorarios() + '<button class="btn" type="submit">Salvar</button></form>' +
      '<section class="cartao grupo"><h2>Convites no celular</h2><p class="mudo">' + avisosTxt + "</p>" + previaConvites(false) + blocoInstalacao() +
      '<button class="btn suave" data-acao="testar-convite">Testar um convite agora</button>' +
      (estado.demo ? "" : (estado.avisos ? '<button class="btn secundario" data-acao="desativar-avisos">Desligar os convites</button>' : '<button class="btn" data-acao="ativar-avisos">' + ICONES.sino + " Ativar os convites</button>")) + "</section>" +
      '<section class="cartao grupo"><h2>Seu acesso</h2><p class="mudo numeros">' + (estado.demo ? "Degustação de 3 dias." : "Código " + esc(estado.codigo) + ". Use o mesmo código para continuar em outro celular.") + "</p>" +
      (estado.demo ? botaoCompra("Quero os 30 dias") : "") +
      '<button class="btn secundario" data-acao="pedir-sair">Sair deste celular</button>' +
      '<div id="confirmaSair" hidden class="pilha"><p>' + (estado.demo ? "A degustação será apagada deste celular." : "O seu progresso fica guardado no código. Para voltar, basta digitar o código de novo.") + "</p>" +
      '<div class="linha"><button class="btn" data-acao="sair">Sair</button><button class="btn secundario" data-acao="cancelar-sair">Cancelar</button></div></div></section>' +
      "</div>" + menu("ajustes");
  }

  /* ---------- Final ---------- */
  function renderFinal() {
    definirMomentoVisual("noite");
    var total = totalConcluidos(), notas = Object.keys(estado.notas || {}).filter(function (k) { return (estado.notas[k] || "").trim(); }).length;
    var px = conteudo.proximoMes, nome = primeiroNome();
    var msg = "Eu vivi os 30 dias do Três Encontros: um encontro com o Espírito Santo de manhã, com Jesus no almoço e com o Pai à noite. Fez muita diferença na minha vida com Deus. Quero te dar esse presente." + (config.linkCompra ? "\n\n" + config.linkCompra : "");
    app.innerHTML = barraApresentacao() + '<section class="final entra"><div class="coroa">' + ICONES.ok +
      '<span class="rotulo acento">Jornada concluída</span><h1>' + (nome ? esc(nome) + ", você" : "Você") + " viveu os 30 dias</h1>" +
      '<p class="mudo">Pelo Espírito você conheceu mais a Jesus, e por Jesus chegou mais perto do Pai. O ciclo continua todos os dias.</p></div>' +
      '<div class="numeros-final"><div><b class="numeros">' + total + '</b><span>encontros vividos</span></div><div><b class="numeros">' + notas + '</b><span>anotações suas</span></div><div><b class="numeros">30</b><span>dias com Deus</span></div></div>' +
      (px.length ? '<article class="proximo"><span class="rotulo acento">No próximo mês</span><h2>' + esc(px[0].titulo) + "</h2>" +
        '<p class="mudo">' + esc(px[0].texto.join(" ")) + "</p>" +
        (px[1] ? '<span class="rotulo">' + esc(px[1].titulo) + '</span><div class="previa">' + px[1].texto.map(function (t) { return "<p>" + esc(t) + "</p>"; }).join("") + "</div>" : "") +
        botaoCompra("Quero continuar no próximo mês", config.linkProximoMes || config.linkCompra) + "</article>" : "") +
      '<article class="proximo"><div class="linha">' + ICONES.presente + '<div><span class="rotulo acento">Se você quiser</span><h2>Presentear alguém</h2></div></div>' +
      '<p class="mudo">Se esta jornada fez bem a você, pode dar um acesso de presente para alguém. É um gesto livre, sem nenhuma obrigação.</p>' +
      '<pre class="mensagem" id="msgPresente">' + esc(msg) + "</pre>" +
      '<button class="btn suave cheio" data-acao="compartilhar">Enviar esta mensagem</button>' +
      botaoCompra("Comprar um acesso de presente") + "</article>" +
      '<a class="btn secundario cheio" href="#jornada">Reler os encontros</a></section>' + menu("inicio");
    app._mensagem = msg;
  }

  /* ---------- Eventos ---------- */
  app.addEventListener("click", function (e) {
    var alvo = e.target.closest("[data-acao], [data-ir]");
    if (!alvo || alvo.disabled) return;
    if (alvo.hasAttribute("data-ir") && !alvo.hasAttribute("data-acao")) { ir(alvo.getAttribute("data-ir")); return; }
    var acao = alvo.getAttribute("data-acao");
    switch (acao) {
      case "tenho-codigo": tela.passo = "codigo"; render(); break;
      case "voltar-inicio": tela.passo = 0; render(); break;
      case "demo": iniciarDemo(); break;
      case "passo": tela.passo = +alvo.getAttribute("data-ir"); render(); window.scrollTo(0, 0); break;
      case "ativar-avisos-inicio":
        ativarAvisos().then(function (res) {
          if (res === "ok" || res === "demo") { aviso(mensagemAvisos(res)); concluirConfiguracao(); }
          else { var el = document.getElementById("erroAvisos"); el.textContent = mensagemAvisos(res); el.hidden = false; }
        });
        break;
      case "concluir-config": concluirConfiguracao(); break;
      case "ativar-avisos": ativarAvisos().then(function (res) { aviso(mensagemAvisos(res)); render(); }); break;
      case "desativar-avisos": desativarAvisos(); aviso("Avisos desligados neste celular."); render(); break;
      case "instalar":
        if (instalar) { instalar.prompt(); instalar.userChoice.then(function () { instalar = null; render(); }); }
        break;
      case "concluir": concluirEncontro(+alvo.getAttribute("data-dia"), alvo.getAttribute("data-momento")); break;
      case "voltar": if (history.length > 1) history.back(); else ir("inicio"); break;
      case "pedir-sair": document.getElementById("confirmaSair").hidden = false; alvo.hidden = true; break;
      case "cancelar-sair": render(); break;
      case "sair":
        var eraDemo = !!estado.demo;
        if (estado.avisos) desativarAvisos();
        estado = {}; gravar("estado", estado); tela.passo = eraDemo ? 0 : "codigo";
        history.replaceState(null, "", location.pathname + location.search); render(); break;
      case "sem-link": aviso("O link de compra ainda não foi configurado."); break;
      case "compartilhar": compartilhar(app._mensagem || ""); break;
      case "testar-convite": testarConvite(); break;

    }
  });

  app.addEventListener("submit", function (e) {
    e.preventDefault();
    if (e.target.id === "formCodigo") { entrarComCodigo(document.getElementById("codigo").value); return; }
    if (e.target.id === "formHorarios" || e.target.id === "formAjustes") {
      var h = lerHorarios(); if (!h) return;
      estado.horarios = h;
      estado.nome = document.getElementById("nome").value.trim().slice(0, 40);
      salvarEstado(true);
      if (e.target.id === "formHorarios") { tela.passo = conteudo.abertura.length + 1; render(); window.scrollTo(0, 0); }
      else { aviso("Salvo."); render(); }
    }
  });

  app.addEventListener("input", function (e) {
    if (e.target.id === "nota") {
      var k = e.target.getAttribute("data-chave");
      estado.notas = estado.notas || {};
      estado.notas[k] = e.target.value;
      notasSujas[k] = true;
      clearTimeout(app._tNota);
      app._tNota = setTimeout(function () { salvarEstado(true); var s = document.getElementById("salvo"); if (s) s.textContent = "Anotação guardada."; }, 500);
    }
    if (e.target.id === "codigo") {
      var v = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "");
      if (v.indexOf("TE") === 0 && v.length > 2) v = "TE-" + v.slice(2, 6) + (v.length > 6 ? "-" + v.slice(6, 10) : "");
      e.target.value = v;
    }
    if (e.target.id === "apDia") {
      apresentacao.dia = +e.target.value;
      document.getElementById("apRotulo").textContent = apresentacao.dia > 30 ? "Depois do dia 30" : "Dia " + apresentacao.dia;
    }
  });
  /* Navegação da apresentação: leva direto a qualquer tela do sistema. */
  function garantirDemo() {
    if (!estado.codigo) {
      estado = { codigo: CODIGO_DEMO, demo: true, inicio: hojeISO(new Date()), concluidos: [], notas: {}, nome: "Ana", configurado: true,
        horarios: { manha: "06:30", almoco: "12:00", noite: "21:30" } };
    }
    estado.configurado = true;
    if (apresentacao.dia > 30) apresentacao.dia = Math.min(30, diaDeHoje());
  }
  function irParaTela(t) {
    var semHash = function () { history.replaceState(null, "", location.pathname + location.search); };
    if (t === "boas-vindas" || t === "codigo") { estado = {}; tela.passo = t === "codigo" ? "codigo" : 0; semHash(); render(); }
    else if (t === "abertura" || t === "marque" || t === "convites") {
      garantirDemo(); estado.configurado = false;
      tela.passo = t === "abertura" ? 0 : (t === "marque" ? conteudo.abertura.length : conteudo.abertura.length + 1);
      semHash(); render();
    }
    else if (t === "admin") { location.href = "admin.html"; return; }
    else if (t === "final") { garantirDemo(); apresentacao.dia = 31; ir("final"); }
    else if (t === "encontro") { garantirDemo(); ir("encontro-" + Math.max(1, Math.min(30, diaDeHoje())) + "-" + momentoDoRelogio()); }
    else { garantirDemo(); ir(t === "hoje" ? "inicio" : t); }
    window.scrollTo(0, 0);
  }

  app.addEventListener("change", function (e) {
    if (e.target.id === "apIr" && e.target.value) { irParaTela(e.target.value); return; }
    if (e.target.id === "apDia" || e.target.id === "apHora") {
      if (e.target.id === "apHora") apresentacao.hora = e.target.value;
      var y = window.scrollY; render(); window.scrollTo(0, y);
    }
  });

  function concluirConfiguracao() {
    estado.configurado = true;
    estado.horarios = estado.horarios || { manha: "06:30", almoco: "12:00", noite: "21:30" };
    salvarEstado(true);
    location.hash = "inicio"; render();
  }

  function compartilhar(texto) {
    if (navigator.share) {
      navigator.share({ text: texto }).catch(function () { copiar(texto); });
      return;
    }
    copiar(texto);
  }
  function copiar(texto) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(function () { aviso("Mensagem copiada. Cole no WhatsApp."); }, selecionar);
    } else selecionar();
    function selecionar() {
      var el = document.getElementById("msgPresente"); if (!el) return;
      var r = document.createRange(); r.selectNodeContents(el);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      aviso("Texto selecionado. Copie e cole no WhatsApp.");
    }
  }

  // Libera o dia novo e atualiza as cores do momento sem precisar recarregar.
  var ultimaChave = "";
  setInterval(function () {
    if (!conteudo || !estado.configurado) return;
    var chave = diaDeHoje() + "|" + momentoDoRelogio();
    if (ultimaChave && chave !== ultimaChave && rotaAtual() === "inicio") render();
    ultimaChave = chave;
  }, 30000);

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && conteudo && estado.configurado && rotaAtual() === "inicio") render();
  });

  /* ---------- Início ---------- */
  if ((location.hash || "") === "#apresentacao" || window.TE_APRESENTACAO) {
    apresentacao.ativa = true; // começa pela tela de boas-vindas, como um cliente novo
    apresentacao.dia = Math.max(1, Math.min(31, diaDeHoje()));
  }

  /* Os textos completos vêm da API para quem tem código; a degustação recebe só os 3 primeiros dias.
     Ficam guardados no celular para funcionar sem internet. */
  function carregarConteudo() {
    var codigo = estado.codigo && !estado.demo ? estado.codigo : "";
    return api("conteudo", { codigo: codigo }).then(function (r) {
      if (!r.ok || !r.conteudo) throw new Error("sem conteúdo");
      conteudo = r.conteudo;
      gravar("conteudo", conteudo);
      informarServiceWorker();
    }).catch(function () {
      if (conteudo) return;
      // Sem servidor (prévia): usa o arquivo, se estiver acessível.
      return fetch(CONTEUDO).then(function (r) {
        if (!r.ok) throw new Error("indisponível");
        return r.json();
      }).then(function (dados) { conteudo = dados; });
    });
  }

  conteudo = ler("conteudo");
  if (conteudo) render();
  carregarConteudo().then(function () {
    if (!conteudo) throw new Error("vazio");
    render();
  }).catch(function () {
    if (!conteudo) app.innerHTML = '<section class="carregando"><p>Não foi possível carregar o devocional. Verifique a internet e abra de novo.</p></section>';
  });

  if (estado.codigo && !estado.demo && navigator.onLine) {
    api("entrar", { codigo: estado.codigo, hoje: hojeISO(new Date()) }).then(function (r) {
      if (r.ok) { mesclarPerfil(r.perfil); salvarEstado(false); render(); }
    }).catch(function () { /* offline: segue com o que está no celular */ });
    carregarConfig();
  }
  registrarServiceWorker();
})();
