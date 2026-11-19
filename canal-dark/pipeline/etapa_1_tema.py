"""[1] Tema: cria o projeto a partir de uma ideia livre ou de uma linha do temas.csv.

Exemplos:
  python -m pipeline.etapa_1_tema --projeto davi-golias --tema "Davi e Golias"
  python -m pipeline.etapa_1_tema --projeto jonas --ideia "Jonas fugindo de Deus" --passagem "Jonas 1-2"
  python -m pipeline.etapa_1_tema --projeto teste --formato shorts
"""
import csv
from datetime import datetime

from .comum import RAIZ, ErroEtapa, log, pasta_projeto, rodar, salvar_json

ETAPA = "1-tema"


def args_extras(p):
    p.add_argument("--tema", help="título exato de uma linha do temas.csv")
    p.add_argument("--ideia", help="ideia livre (alternativa ao temas.csv)")
    p.add_argument("--passagem", default="", help="referência bíblica (livro cap:vers)")
    p.add_argument("--formato", choices=["shorts", "longo", "ambos"], default="shorts")
    p.add_argument("--teste", action="store_true",
                   help="projeto de teste: voz e imagens locais provisórias, sem upload")


def ler_temas():
    with open(RAIZ / "temas.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def marcar_tema(titulo, status):
    temas = ler_temas()
    for t in temas:
        if t["titulo"] == titulo:
            t["status"] = status
    with open(RAIZ / "temas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["titulo", "passagem", "status"])
        w.writeheader()
        w.writerows(temas)


def main(args):
    if args.ideia:
        titulo, passagem = args.ideia, args.passagem
    else:
        temas = ler_temas()
        if args.tema:
            achados = [t for t in temas if t["titulo"] == args.tema]
        else:
            achados = [t for t in temas if t["status"] == "pendente"][:1]
        if not achados:
            raise ErroEtapa("Tema não encontrado em temas.csv (ou nenhum pendente).")
        titulo, passagem = achados[0]["titulo"], achados[0]["passagem"]
        if not args.teste:
            marcar_tema(titulo, "em_producao")

    pasta = pasta_projeto(args.projeto, criar=True)
    arquivo = pasta / "projeto.json"
    if arquivo.exists():
        raise ErroEtapa(f"Projeto '{args.projeto}' já existe ({arquivo}).")
    salvar_json(arquivo, {
        "id": args.projeto, "titulo": titulo, "passagem": passagem,
        "formato": args.formato, "teste": args.teste, "criado_em": datetime.now().isoformat(timespec="seconds"),
    })
    log(pasta, ETAPA, f"Projeto criado: '{titulo}' ({passagem or 'passagem a definir'}), formato {args.formato}.")


if __name__ == "__main__":
    rodar(ETAPA, main, args_extras)
