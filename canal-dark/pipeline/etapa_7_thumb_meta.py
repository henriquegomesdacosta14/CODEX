"""[7] Thumbnail 1280x720 + metadados.json + revisao_final.md (APROVAÇÃO FINAL).

Lê do cabeçalho do roteiro.md:
  titulo_video: título para o YouTube (até 100 caracteres)
  texto_thumb:  texto curto da thumbnail (2 a 4 palavras; use | para quebrar linha)
  thumb_cena:   número da cena usada de fundo (padrão 1)
  tags:         lista de tags
"""
import re

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .comum import (ErroEtapa, carregar_config, eh_teste, exigir_roteiro_aprovado, fonte,
                    formatos_do_projeto, ler_cenas, ler_json, log, pasta_projeto, rodar,
                    salvar_json)

ETAPA = "7-thumb-meta"

REVISAO = """---
status: pendente
---

# Revisão final — {titulo}

Antes de aprovar, confira:
- [ ] Assisti ao vídeo inteiro (imagem, áudio, legendas)
- [ ] A história está fiel à passagem ({passagem})
- [ ] Thumbnail legível no celular
- [ ] Título, descrição e tags em metadados.json
- [ ] Créditos e licença da música em creditos.txt
- [ ] Data/privacidade do upload conferidas

Para liberar o upload, troque 'status: pendente' por 'status: aprovado'.
"""


def cabecalho(pasta):
    texto = (pasta / "roteiro.md").read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", texto, re.S)
    return (yaml.safe_load(m.group(1)) if m else None) or {}


def fundo_16x9(pasta, cena, w, h):
    if eh_teste(pasta):
        from .etapa_4_imagens import ilustracao_provisoria
        cenas = ler_cenas(pasta)
        return ilustracao_provisoria(cenas[cena - 1], cena, w, h, "")
    for formato in ("longo", "shorts"):
        arq = pasta / "imagens" / f"cena_{cena:02d}_{formato}.png"
        if arq.exists():
            img = Image.open(arq).convert("RGB")
            break
    else:
        raise ErroEtapa("Nenhuma imagem de cena encontrada (rode a etapa 4).")
    # recorte central na proporção 16:9, puxado para a parte de baixo (onde ficam as figuras)
    iw, ih = img.size
    alvo = w / h
    if iw / ih > alvo:
        nw = int(ih * alvo)
        img = img.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else:
        nh = int(iw / alvo)
        topo = int((ih - nh) * 0.7)
        img = img.crop((0, topo, iw, topo + nh))
    return img.resize((w, h), Image.LANCZOS)


def gerar_thumbnail(pasta, texto, cena, w, h, rotulo=""):
    img = fundo_16x9(pasta, cena, w, h)
    # escurece o lado esquerdo para o texto saltar
    mascara = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h))
    img = Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)),
                          mascara.point(lambda p: int(110 + p * 0.57)))
    d = ImageDraw.Draw(img)
    linhas = [l.strip().upper() for l in texto.split("|") if l.strip()]
    tam = int(h * (0.26 if len(linhas) <= 1 else 0.2))
    f = ImageFont.truetype(fonte(), tam)
    while max(d.textlength(l, font=f) for l in linhas) > w * 0.62 and tam > 40:
        tam -= 4
        f = ImageFont.truetype(fonte(), tam)
    y = (h - len(linhas) * tam * 1.1) / 2
    for k, linha in enumerate(linhas):
        cor = (255, 215, 0) if k == len(linhas) - 1 else (255, 255, 255)
        d.text((int(w * 0.05), int(y)), linha, font=f, fill=cor,
               stroke_width=max(4, tam // 14), stroke_fill=(0, 0, 0))
        y += tam * 1.1
    if rotulo:
        d.text((int(w * 0.02), int(h * 0.93)), rotulo,
               font=ImageFont.truetype(fonte(), int(h * 0.03)), fill=(255, 255, 255))
    img.save(pasta / "thumbnail.png", optimize=True)


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    cfg = carregar_config()
    p = ler_json(pasta / "projeto.json")
    cab = cabecalho(pasta)
    cenas = ler_cenas(pasta)

    titulo = str(cab.get("titulo_video") or p["titulo"])[:100]
    passagem = cab.get("passagem") or p.get("passagem") or ""
    if not passagem or passagem == "A_DEFINIR":
        raise ErroEtapa("Passagem bíblica não definida no roteiro.")
    shorts = formatos_do_projeto(pasta) == ["shorts"]

    t = cfg["formatos"]["thumbnail"]
    gerar_thumbnail(pasta, str(cab.get("texto_thumb") or p["titulo"]),
                    int(cab.get("thumb_cena") or 1), t["largura"], t["altura"],
                    "PROVISÓRIO — TESTE" if eh_teste(pasta) else "")

    gancho = cenas[0]["narracao"] if cenas else ""
    descricao = "\n".join([
        gancho, "",
        f"📖 Passagem bíblica: {passagem}",
        "Leia a história completa na sua Bíblia.", "",
        "Inscreva-se para mais histórias da Bíblia.", "",
        "Narração e ilustrações produzidas com auxílio de inteligência artificial, "
        "com roteiro e revisão humanos.", "",
        "#historiasbiblicas #biblia" + (" #shorts" if shorts else ""),
    ])
    tags = list(cab.get("tags") or []) + ["histórias bíblicas", "bíblia", passagem.split()[0]]
    up = cfg["upload"]
    salvar_json(pasta / "metadados.json", {
        "titulo": titulo,
        "descricao": descricao,
        "tags": list(dict.fromkeys(tags)),
        "idioma": cfg["canal"]["idioma"],
        "privacidade": up["privacidade_padrao"],
        "feito_para_criancas": up["feito_para_criancas"],
        "conteudo_sintetico": up["conteudo_sintetico"],
        "video": "video/shorts_final.mp4" if shorts else "video/longo.mp4",
        "legendas": "legendas.srt",
        "thumbnail": "thumbnail.png",
    })

    revisao = pasta / "revisao_final.md"
    if not revisao.exists():
        revisao.write_text(REVISAO.format(titulo=titulo, passagem=passagem), encoding="utf-8")
    log(pasta, ETAPA, "thumbnail.png, metadados.json e revisao_final.md (pendente) prontos. "
                      "PARE: aguardando aprovação final.")


if __name__ == "__main__":
    rodar(ETAPA, main)
