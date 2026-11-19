"""[2] Roteiro: cria o modelo do roteiro.md e valida o roteiro preenchido.

  python -m pipeline.etapa_2_roteiro --projeto davi-golias            # cria o modelo
  python -m pipeline.etapa_2_roteiro --projeto davi-golias --validar  # confere estrutura

Depois de revisar, o Henrique troca 'status: rascunho' para 'status: aprovado'.
Nenhuma etapa seguinte roda sem isso.
"""
from .comum import ErroEtapa, ler_cenas, ler_json, ler_status, log, pasta_projeto, rodar

ETAPA = "2-roteiro"

MODELO = """---
status: rascunho
titulo: {titulo}
passagem: {passagem}
formato: {formato}
---

# {titulo}

Referência bíblica: {passagem}

## Cena 1 — Gancho
**Narração:** (primeiros 5–10 s: frase forte que prende a atenção)
**Visual:** (descrição da imagem)
**Personagens:**
**Duração:** 6

## Cena 2 — Desenvolvimento
**Narração:**
**Visual:**
**Personagens:**
**Duração:** 10

## Cena 3 — Fechamento
**Narração:** (conclusão + chamada para se inscrever)
**Visual:**
**Personagens:**
**Duração:** 8
"""


def args_extras(p):
    p.add_argument("--validar", action="store_true", help="só valida o roteiro existente")


def validar(pasta):
    cenas = ler_cenas(pasta)
    if not cenas:
        raise ErroEtapa("Nenhuma cena encontrada (use '## Cena N — título').")
    problemas = []
    for i, c in enumerate(cenas, 1):
        for campo in ("narracao", "visual"):
            if not c[campo] or c[campo].startswith("("):
                problemas.append(f"cena {i}: campo '{campo}' vazio")
        if c["duracao"] <= 0:
            problemas.append(f"cena {i}: duração inválida")
    if problemas:
        raise ErroEtapa("Roteiro incompleto: " + "; ".join(problemas))
    total = sum(c["duracao"] for c in cenas)
    log(pasta, ETAPA, f"Roteiro válido: {len(cenas)} cenas, ~{total:.0f} s. "
                      f"Status: {ler_status(pasta / 'roteiro.md')}.")


def main(args):
    pasta = pasta_projeto(args.projeto)
    roteiro = pasta / "roteiro.md"
    if args.validar:
        validar(pasta)
        return
    if roteiro.exists():
        raise ErroEtapa("roteiro.md já existe. Use --validar, ou apague para recriar o modelo.")
    p = ler_json(pasta / "projeto.json")
    roteiro.write_text(MODELO.format(titulo=p["titulo"], passagem=p["passagem"] or "A_DEFINIR",
                                     formato=p["formato"]), encoding="utf-8")
    log(pasta, ETAPA, "Modelo de roteiro criado. Preencha, valide e aprove antes de seguir.")


if __name__ == "__main__":
    rodar(ETAPA, main, args_extras)
