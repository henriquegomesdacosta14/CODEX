#!/usr/bin/env python3
"""Converte os textos de conteudo/mes-XX/*.md em conteudo/mes-XX.json.

Uso:  python3 ferramentas/gerar_conteudo.py mes-01

Formato dos arquivos .md:
  # Bloco N — Título          (abre um bloco de 10 dias)
  > Subtítulo do bloco
  # Dia N — Título            (abre um dia)
  ## Manhã · Referência       (Manhã, Almoço ou Noite; a referência é a passagem para ler)
  > “Texto do versículo” — Referência do versículo   (versículo em destaque)
  parágrafos de reflexão...
  ? pergunta para refletir
  ! prática do dia, atitude ou oração

00-abertura.md e 99-proximo-mes.md usam "## Título" seguido de parágrafos.
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MOMENTOS = {"Manhã": "manha", "Almoço": "almoco", "Noite": "noite"}


def paginas(caminho):
    """Lê um arquivo de páginas simples: ## título + parágrafos."""
    resultado, atual = [], None
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha.startswith("## "):
            atual = {"titulo": linha[3:].strip(), "texto": []}
            resultado.append(atual)
        elif linha.startswith("# ") or not linha:
            continue
        elif atual is not None:
            atual["texto"].append(linha)
    return resultado


def dias(arquivos):
    blocos, lista = [], []
    bloco = dia = momento = None
    for caminho in arquivos:
        for n, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            onde = f"{caminho.name}:{n}"
            linha = linha.strip()
            if not linha:
                continue
            m = re.match(r"^# Bloco (\d+) — (.+)$", linha)
            if m:
                bloco = {"numero": int(m[1]), "titulo": m[2].strip(), "subtitulo": ""}
                blocos.append(bloco)
                continue
            if linha.startswith("> ") and bloco and (dia is None or dia["bloco"] != bloco["numero"]):
                bloco["subtitulo"] = linha[2:].strip()
                continue
            m = re.match(r"^# Dia (\d+) — (.+)$", linha)
            if m:
                if bloco is None:
                    sys.exit(f"{onde}: dia antes de qualquer bloco")
                dia = {"dia": int(m[1]), "titulo": m[2].strip(), "bloco": bloco["numero"]}
                lista.append(dia)
                momento = None
                continue
            m = re.match(r"^## (Manhã|Almoço|Noite) · (.+)$", linha)
            if m:
                if dia is None:
                    sys.exit(f"{onde}: momento fora de um dia")
                momento = {"referencia": m[2].strip(), "versiculo": None, "texto": [], "pergunta": "", "pratica": ""}
                dia[MOMENTOS[m[1]]] = momento
                continue
            if momento is None:
                sys.exit(f"{onde}: texto fora de um momento: {linha[:60]}")
            if linha.startswith("> "):
                v = re.match(r"^> “(.+)” — (.+)$", linha)
                if not v:
                    sys.exit(f"{onde}: versículo fora do formato > “texto” — Referência")
                momento["versiculo"] = {"texto": v[1].strip(), "referencia": v[2].strip()}
            elif linha.startswith("? "):
                momento["pergunta"] = linha[2:].strip()
            elif linha.startswith("! "):
                momento["pratica"] = linha[2:].strip()
            else:
                momento["texto"].append(linha)
    return blocos, lista


def validar(lista):
    erros = []
    numeros = [d["dia"] for d in lista]
    if numeros != list(range(1, len(lista) + 1)):
        erros.append(f"dias fora de ordem ou faltando: {numeros}")
    for d in lista:
        for chave in MOMENTOS.values():
            mo = d.get(chave)
            if not mo:
                erros.append(f"dia {d['dia']}: falta o momento {chave}")
                continue
            if not mo["versiculo"]:
                erros.append(f"dia {d['dia']} {chave}: sem versículo em destaque")
            if not mo["texto"]:
                erros.append(f"dia {d['dia']} {chave}: sem reflexão")
            if not mo["pergunta"]:
                erros.append(f"dia {d['dia']} {chave}: sem pergunta")
            if not mo["pratica"]:
                erros.append(f"dia {d['dia']} {chave}: sem prática")
            if '"' in " ".join(mo["texto"] + [mo["pergunta"], mo["pratica"]]):
                erros.append(f"dia {d['dia']} {chave}: use aspas curvas “ ” em vez de \"")
    return erros


def main():
    mes = sys.argv[1] if len(sys.argv) > 1 else "mes-01"
    pasta = RAIZ / "conteudo" / mes
    arquivos = sorted(p for p in pasta.glob("*.md") if p.name[:2] not in ("00", "99"))
    blocos, lista = dias(arquivos)
    erros = validar(lista)
    if erros:
        print("\n".join(erros))
        sys.exit(1)
    abertura = pasta / "00-abertura.md"
    proximo = pasta / "99-proximo-mes.md"
    saida = {
        "mes": mes,
        "titulo": "Três Encontros",
        "subtitulo": "30 dias com o Espírito Santo, Jesus e Deus Pai",
        "blocos": blocos,
        "abertura": paginas(abertura) if abertura.exists() else [],
        "proximoMes": paginas(proximo) if proximo.exists() else [],
        "dias": lista,
    }
    destino = RAIZ / "conteudo" / f"{mes}.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    palavras = sum(len(" ".join(m["texto"]).split()) for d in lista for m in (d["manha"], d["almoco"], d["noite"]))
    print(f"{destino.relative_to(RAIZ)}: {len(lista)} dias, {len(blocos)} blocos, {palavras} palavras de reflexão")


if __name__ == "__main__":
    main()
