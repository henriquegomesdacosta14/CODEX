/* Texto dos lembretes: cada encontro chega como um convite de quem espera por você.
   O Espírito Santo chama pelo nome; Jesus chama de irmão ou irmã (João 20:17, Hebreus 2:11);
   o Pai chama de filho ou filha (1 João 3:1). As frases ecoam convites da própria Bíblia.
   Usado pelo app e pelo service worker (avisos). */
(function (raiz) {
  "use strict";

  // {quem} = como cada um chama a pessoa; {cansado} concorda com o gênero.
  var CONVITES = {
    manha: {
      quem: "Espírito Santo",
      frases: [
        "Bom dia, {quem}! Estou aqui com você. Vamos começar o dia juntos?",
        "Bom dia, {quem}! Antes de tudo, vem conversar comigo.",
        "{quem}, eu habito em você. Separe um momento para ouvirmos a Palavra juntos.",
        "Bom dia, {quem}! Tenho algo para te ensinar hoje. Estou te esperando."
      ]
    },
    almoco: {
      quem: "Jesus",
      frases: [
        "Oi, {quem}! Estou te aguardando para o nosso encontro.",
        "{quem}, faz uma pausa comigo? Vem a mim, você que está {cansado}.",
        "Oi, {quem}! Eis que estou à porta e bato. Abre um tempo para mim?",
        "{quem}, no meio do seu dia, eu estou aqui. Vamos conversar?"
      ]
    },
    noite: {
      quem: "Deus Pai",
      frases: [
        "Boa noite, {quem}. Vem descansar comigo antes de dormir.",
        "{quem}, quero ouvir como foi o seu dia. Estou te esperando.",
        "Boa noite, {quem}. Aquiete o coração e me entregue o que ficou de hoje.",
        "{quem}, antes de fechar os olhos, vem para perto de mim."
      ]
    }
  };

  /** Como cada Pessoa chama: genero = "m", "f" ou vazio (sem gênero, usa o nome). */
  function chamado(momento, nome, genero) {
    if (momento === "almoco" && genero) return genero === "f" ? "minha irmã" : "meu irmão";
    if (momento === "noite" && genero) return genero === "f" ? "minha filha" : "meu filho";
    return String(nome || "").trim().split(/\s+/)[0];
  }

  /** Monta o lembrete de um encontro. dia = 1 a 30; titulo = título do dia (opcional). */
  function montar(momento, nome, dia, titulo, genero) {
    var c = CONVITES[momento] || CONVITES.manha;
    var frase = c.frases[((dia || 1) - 1) % c.frases.length];
    var quem = chamado(momento, nome, genero);
    frase = frase.replace(/\{cansado\}/g, genero === "f" ? "cansada" : genero === "m" ? "cansado" : "cansado(a)");
    if (quem) {
      frase = frase.replace(/\{quem\}/g, quem);
    } else {
      // Sem nome e sem gênero: tira o vocativo e mantém a frase natural.
      frase = frase.replace(/, \{quem\}([!.])/, "$1").replace(/^\{quem\}, /, "");
    }
    frase = frase.charAt(0).toUpperCase() + frase.slice(1);
    var rodape = dia >= 1 && dia <= 30 ? "\nDia " + dia + (titulo ? " · " + titulo : "") : "";
    return { titulo: c.quem, corpo: frase + rodape };
  }

  raiz.TELembretes = { montar: montar, CONVITES: CONVITES };
})(typeof self !== "undefined" ? self : this);
