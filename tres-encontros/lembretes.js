/* Texto dos lembretes: cada encontro chega como um convite de quem espera por você.
   As frases ecoam convites da própria Bíblia. Usado pelo app (botão de teste) e pelo service worker (avisos). */
(function (raiz) {
  "use strict";

  var CONVITES = {
    manha: {
      quem: "Espírito Santo",
      frases: [
        "Bom dia, {nome}! Estou aqui com você. Vamos começar o dia juntos?",
        "Bom dia, {nome}! Antes de tudo, vem conversar comigo.",
        "{nome}, eu habito em você. Separe um momento para ouvirmos a Palavra juntos.",
        "Bom dia, {nome}! Tenho algo para te ensinar hoje. Estou te esperando."
      ]
    },
    almoco: {
      quem: "Jesus",
      frases: [
        "Oi, {nome}! Estou te aguardando para o nosso encontro.",
        "{nome}, faz uma pausa comigo? Vem a mim, você que está cansado(a).",
        "Oi, {nome}! Eis que estou à porta e bato. Abre um tempo para mim?",
        "{nome}, no meio do seu dia, eu estou aqui. Vamos conversar?"
      ]
    },
    noite: {
      quem: "Deus Pai",
      frases: [
        "Boa noite, {nome}. Vem descansar comigo antes de dormir.",
        "{nome}, quero ouvir como foi o seu dia. Estou te esperando.",
        "Boa noite, {nome}. Aquiete o coração e me entregue o que ficou de hoje.",
        "{nome}, antes de fechar os olhos, vem para perto de mim."
      ]
    }
  };

  /** Monta o lembrete de um encontro. dia = 1 a 30; titulo = título do dia (opcional). */
  function montar(momento, nome, dia, titulo) {
    var c = CONVITES[momento] || CONVITES.manha;
    var frase = c.frases[((dia || 1) - 1) % c.frases.length];
    var primeiro = String(nome || "").trim().split(/\s+/)[0];
    frase = primeiro ? frase.replace(/\{nome\}/g, primeiro)
      : frase.replace(/^Bom dia, \{nome\}! /, "Bom dia! ").replace(/^Boa noite, \{nome\}\. /, "Boa noite. ")
        .replace(/^Oi, \{nome\}! /, "Oi! ").replace(/^\{nome\}, /, "").replace(/, \{nome\}/g, "");
    frase = frase.charAt(0).toUpperCase() + frase.slice(1);
    var rodape = dia >= 1 && dia <= 30 ? "\nDia " + dia + (titulo ? " · " + titulo : "") : "";
    return { titulo: c.quem, corpo: frase + rodape };
  }

  raiz.TELembretes = { montar: montar, CONVITES: CONVITES };
})(typeof self !== "undefined" ? self : this);
