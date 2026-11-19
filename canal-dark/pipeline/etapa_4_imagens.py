"""[4] Imagens das cenas: imagens/cena_NN_<formato>.png, com personagens consistentes.

Serviços:
  - local (projetos de teste): ilustração provisória desenhada por código
    (céu, montes e silhuetas), só para testar montagem e ritmo.
  - o serviço definido em config.yaml para os vídeos reais.
"""
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .comum import (ErroEtapa, carregar_config, carregar_personagens, eh_teste, exigir_chave,
                    exigir_definido, exigir_roteiro_aprovado, fonte, formatos_do_projeto,
                    ler_cenas, log, pasta_projeto, rodar, salvar_json)

ETAPA = "4-imagens"
ESCALA = 1.5   # imagem maior que o vídeo, para o zoom/pan não perder nitidez


# ------------------------------------------------------------------ prompt

def montar_prompt(cena, cfg, personagens):
    partes = [cena["visual"]]
    for nome in cena["personagens"]:
        if nome in personagens:
            partes.append(personagens[nome]["descricao"])
        elif personagens:
            raise ErroEtapa(f"Personagem '{nome}' não está em personagens.yaml.")
    if cfg["estilo_visual"].get("prompt_base"):
        partes.append(cfg["estilo_visual"]["prompt_base"])
    return ". ".join(p for p in partes if p)


# ------------------------------------------------------------------ provisório

PALETAS = {
    "amanhecer": [(40, 30, 70), (230, 120, 70), (255, 210, 140)],
    "dia":       [(60, 110, 170), (150, 190, 220), (240, 225, 190)],
    "por_do_sol": [(50, 20, 40), (190, 60, 40), (250, 170, 60)],
    "noite":     [(8, 10, 25), (30, 35, 70), (90, 80, 120)],
    "tensao":    [(25, 10, 10), (110, 25, 20), (200, 90, 40)],
    "gloria":    [(40, 50, 90), (220, 170, 80), (255, 245, 210)],
}
PALAVRAS = [("amanhecer", "amanhecer"), ("aurora", "amanhecer"), ("noite", "noite"),
            ("pôr do sol", "por_do_sol"), ("entardecer", "por_do_sol"),
            ("tens", "tensao"), ("fogo", "tensao"), ("sangue", "tensao"), ("tempestade", "tensao"),
            ("luz", "gloria"), ("glória", "gloria"), ("vitória", "gloria")]


def paleta_da_cena(visual: str, indice: int):
    v = visual.lower()
    for palavra, nome in PALAVRAS:
        if palavra in v:
            return PALETAS[nome]
    return list(PALETAS.values())[indice % len(PALETAS)]


def gradiente(w, h, cores):
    coluna = Image.new("RGB", (1, h))
    px = coluna.load()
    for y in range(h):
        t = y / (h - 1)
        a, b, f = (cores[0], cores[1], t * 2) if t < 0.5 else (cores[1], cores[2], (t - 0.5) * 2)
        px[0, y] = tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))
    return coluna.resize((w, h))


def figura(d, cx, base, altura, cor, tipo):
    """Silhueta simples de pessoa. tipo: gigante, pastor, rei, soldado."""
    cab = altura * 0.12
    larg = altura * (0.34 if tipo == "gigante" else 0.26)
    topo = base - altura
    d.ellipse([cx - cab / 2, topo, cx + cab / 2, topo + cab], fill=cor)
    d.polygon([(cx - larg / 2, base), (cx + larg / 2, base),
               (cx + larg * 0.32, topo + cab * 1.1), (cx - larg * 0.32, topo + cab * 1.1)], fill=cor)
    if tipo in ("gigante", "soldado"):       # lança
        d.line([(cx + larg * 0.55, base), (cx + larg * 0.55, topo - altura * 0.15)],
               fill=cor, width=max(3, int(altura * 0.025)))
        d.polygon([(cx + larg * 0.55, topo - altura * 0.25), (cx + larg * 0.5, topo - altura * 0.15),
                   (cx + larg * 0.6, topo - altura * 0.15)], fill=cor)
    if tipo == "gigante":                     # elmo com crista
        d.polygon([(cx - cab * 0.3, topo), (cx + cab * 0.3, topo), (cx, topo - cab * 0.6)], fill=cor)
    if tipo == "rei":                         # coroa
        for k in (-1, 0, 1):
            x = cx + k * cab * 0.3
            d.polygon([(x - cab * 0.15, topo + cab * 0.1), (x + cab * 0.15, topo + cab * 0.1),
                       (x, topo - cab * 0.4)], fill=cor)
    if tipo == "pastor":                      # cajado
        x = cx - larg * 0.6
        d.line([(x, base), (x, topo + cab * 0.2)], fill=cor, width=max(3, int(altura * 0.02)))
        d.arc([x, topo - cab * 0.3, x + cab * 0.8, topo + cab * 0.5], 180, 360, fill=cor,
              width=max(3, int(altura * 0.02)))


def ilustracao_provisoria(cena, indice, w, h, rotulo):
    rnd = random.Random(indice)
    cores = paleta_da_cena(cena["visual"], indice)
    img = gradiente(w, h, cores)
    d = ImageDraw.Draw(img, "RGBA")

    # brilho do sol/lua
    sx, sy, r = w * rnd.uniform(0.25, 0.75), h * rnd.uniform(0.18, 0.35), w * 0.16
    brilho = Image.new("L", (w, h), 0)
    ImageDraw.Draw(brilho).ellipse([sx - r, sy - r, sx + r, sy + r], fill=255)
    brilho = brilho.filter(ImageFilter.GaussianBlur(w * 0.08))
    img.paste(Image.new("RGB", (w, h), cores[2]), (0, 0), brilho)
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([sx - r * 0.35, sy - r * 0.35, sx + r * 0.35, sy + r * 0.35],
              fill=(*cores[2], 230))

    # camadas de montes (do fundo para a frente)
    for camada in range(3):
        base_y = h * (0.62 + camada * 0.09)
        # montes mais claros que as silhuetas, para os personagens se destacarem
        f = (0.42, 0.32, 0.24)[camada]
        escuro = tuple(int(cores[1][k] * f + 10) for k in range(3))
        pts, x = [(0, h)], 0
        while x <= w:
            pts.append((x, base_y - rnd.uniform(0, h * 0.06)))
            x += w / rnd.randint(4, 7)
        pts += [(w, base_y), (w, h)]
        d.polygon(pts, fill=escuro)

    chao = h * 0.86
    sombra = (5, 5, 10)
    nomes = [n.lower() for n in cena["personagens"]]
    visual = cena["visual"].lower()
    if "exército" in visual or "exercito" in visual or "acampamento" in visual:
        for k in range(14):
            figura(d, w * (0.05 + k * 0.068), h * 0.74, h * 0.06, (15, 12, 20), "soldado")
    posicoes = {1: [0.5], 2: [0.3, 0.68], 3: [0.22, 0.5, 0.78]}.get(len(nomes), [0.5])
    for nome, px_rel in zip(nomes, posicoes):
        tipo = {"golias": "gigante", "davi": "pastor", "saul": "rei"}.get(nome, "soldado")
        alt = {"gigante": 0.5, "pastor": 0.22, "rei": 0.28}.get(tipo, 0.25) * h
        figura(d, w * px_rel, chao, alt, sombra, tipo)
    if "pedra" in visual:
        for k in range(5 if "cinco" in visual else 1):
            d.ellipse([w * (0.4 + k * 0.05), h * 0.9, w * (0.43 + k * 0.05), h * 0.92],
                      fill=(150, 145, 140))

    # vinheta + rótulo de provisório
    vinheta = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vinheta).rectangle([w * 0.05, h * 0.04, w * 0.95, h * 0.99], fill=255)
    vinheta = vinheta.filter(ImageFilter.GaussianBlur(w * 0.07))
    img = Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)), vinheta)
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(fonte(), int(w * 0.022))
    d.text((w * 0.04, h * 0.02), rotulo, font=f, fill=(255, 255, 255, 110))
    return img


# ------------------------------------------------------------------ etapa

def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    cfg = carregar_config()
    cenas = ler_cenas(pasta)
    teste = eh_teste(pasta)
    personagens = carregar_personagens()
    prompts = [montar_prompt(c, cfg, personagens) for c in cenas]

    if not teste:
        exigir_definido(cfg["imagens"]["servico"], "imagens.servico")
        exigir_definido(cfg["estilo_visual"]["direcao"], "estilo_visual.direcao")
        exigir_chave("IMAGEM_API_KEY")
        # TODO: integrar o serviço escolhido, seguindo a documentação oficial dele.
        raise ErroEtapa(f"Integração com '{cfg['imagens']['servico']}' ainda não implementada.")

    destino = pasta / "imagens"
    destino.mkdir(exist_ok=True)
    for formato in formatos_do_projeto(pasta):
        w = int(cfg["formatos"][formato]["largura"] * ESCALA)
        h = int(cfg["formatos"][formato]["altura"] * ESCALA)
        for i, cena in enumerate(cenas, 1):
            img = ilustracao_provisoria(cena, i, w, h, "IMAGEM PROVISÓRIA — TESTE")
            img.save(destino / f"cena_{i:02d}_{formato}.png", optimize=True)
    salvar_json(destino / "prompts.json", {f"cena_{i:02d}": p for i, p in enumerate(prompts, 1)})
    log(pasta, ETAPA, f"{len(cenas)} imagens provisórias por formato "
                      f"({', '.join(formatos_do_projeto(pasta))}). Prompts em imagens/prompts.json.")


if __name__ == "__main__":
    rodar(ETAPA, main)
