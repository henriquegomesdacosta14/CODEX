/* Service worker do Três Encontros: funciona sem internet e mostra os avisos dos encontros. */
var VERSAO = "te-v5";
var ARQUIVOS = ["./", "index.html", "app.css", "app.js", "manifest.webmanifest",
  "icones/icone.svg", "icones/icone-192.png", "icones/icone-512.png", "icones/apple-touch-icon.png"];
var MOMENTOS = [
  { id: "manha", nome: "Bom dia com o Espírito Santo", padrao: "06:30" },
  { id: "almoco", nome: "Boa tarde com Jesus", padrao: "12:00" },
  { id: "noite", nome: "Boa noite com Deus Pai", padrao: "21:30" }
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSAO).then(function (c) { return c.addAll(ARQUIVOS); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (nomes) {
    return Promise.all(nomes.filter(function (n) { return n !== VERSAO && n !== "te-estado" && n !== "te-fontes"; })
      .map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return; // a API usa POST e vai direto para a rede
  var url = new URL(req.url);
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    e.respondWith(caches.open("te-fontes").then(function (c) {
      return c.match(req).then(function (r) {
        return r || fetch(req).then(function (resp) { c.put(req, resp.clone()); return resp; });
      });
    }));
    return;
  }
  if (url.origin !== self.location.origin) return;
  // Mostra o que está guardado e atualiza em segundo plano.
  e.respondWith(caches.open(VERSAO).then(function (c) {
    return c.match(req, { ignoreSearch: true }).then(function (guardado) {
      var rede = fetch(req).then(function (resp) {
        if (resp && resp.ok) c.put(req, resp.clone());
        return resp;
      }).catch(function () { return guardado; });
      return guardado || rede;
    });
  }));
});

// O app manda o início da jornada e os horários para o aviso saber o que mostrar.
self.addEventListener("message", function (e) {
  if (!e.data || e.data.tipo !== "estado") return;
  e.waitUntil(caches.open("te-estado").then(function (c) {
    return c.put("estado", new Response(JSON.stringify(e.data.dados), { headers: { "Content-Type": "application/json" } }));
  }));
});

function hojeISO(d) {
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

self.addEventListener("push", function (e) {
  e.waitUntil(Promise.all([
    caches.open("te-estado").then(function (c) { return c.match("estado"); }).then(function (r) { return r ? r.json() : {}; })
  ]).then(function (res) {
    var est = res[0] || {};
    var agora = new Date(), min = agora.getHours() * 60 + agora.getMinutes();
    var h = est.horarios || {};
    var atual = MOMENTOS[0];
    MOMENTOS.forEach(function (m) {
      var p = (h[m.id] || m.padrao).split(":");
      if (min >= +p[0] * 60 + +p[1]) atual = m;
    });
    var dia = 1;
    if (est.inicio) {
      var p = est.inicio.split("-");
      var ini = new Date(+p[0], +p[1] - 1, +p[2]);
      var hoje = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate());
      dia = Math.round((hoje - ini) / 864e5) + 1;
    }
    var titulo = est.titulos && est.titulos[dia - 1] ? est.titulos[dia - 1] : "";
    var corpo = (dia >= 1 && dia <= 30 ? "Dia " + dia + (titulo ? " · " + titulo : "") + ". " : "") + "O seu encontro está esperando por você.";
    return self.registration.showNotification(atual.nome, {
      body: corpo,
      icon: "icones/icone-192.png",
      badge: "icones/icone-192.png",
      tag: "encontro-" + hojeISO(agora) + "-" + atual.id,
      data: { rota: dia >= 1 && dia <= 30 ? "#encontro-" + dia + "-" + atual.id : "#inicio" }
    });
  }));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var rota = (e.notification.data && e.notification.data.rota) || "#inicio";
  var destino = new URL("./" + rota, self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (janelas) {
    for (var i = 0; i < janelas.length; i++) {
      if (janelas[i].url.indexOf(self.registration.scope) === 0) {
        janelas[i].navigate(destino);
        return janelas[i].focus();
      }
    }
    return self.clients.openWindow(destino);
  }));
});
