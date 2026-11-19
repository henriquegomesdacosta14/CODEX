"""Funções compartilhadas por todas as etapas do pipeline."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PROJETOS = RAIZ / "projetos"


class ErroEtapa(Exception):
    """Erro esperado: a etapa não pode seguir (falta aprovação, chave, arquivo...)."""


# ---------------------------------------------------------------- config

def carregar_config() -> dict:
    with open(RAIZ / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def carregar_personagens() -> dict:
    with open(RAIZ / "personagens.yaml", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("personagens") or {}


def exigir_chave(nome: str) -> str:
    """Lê uma chave do .env. Nunca loga o valor."""
    try:
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
    except ImportError:
        pass
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise ErroEtapa(f"Chave {nome} não configurada no .env (veja .env.example).")
    return valor


def exigir_definido(valor, campo: str):
    if valor in (None, "", "A_DEFINIR"):
        raise ErroEtapa(f"'{campo}' ainda está A_DEFINIR no config.yaml.")
    return valor


# ---------------------------------------------------------------- projeto

def pasta_projeto(projeto_id: str, criar: bool = False) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", projeto_id):
        raise ErroEtapa("Id do projeto: use só letras minúsculas, números, - e _.")
    p = PROJETOS / projeto_id
    if criar:
        p.mkdir(parents=True, exist_ok=True)
    elif not p.is_dir():
        raise ErroEtapa(f"Projeto '{projeto_id}' não existe. Rode a etapa 1 primeiro.")
    return p


def log(pasta: Path, etapa: str, msg: str) -> None:
    linha = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{etapa}] {msg}"
    print(linha)
    with open(pasta / "log.txt", "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def ler_json(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def salvar_json(caminho: Path, dados: dict) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- aprovação

def ler_status(arquivo: Path) -> str:
    """Lê a linha 'status: ...' do cabeçalho (front matter) de um .md."""
    if not arquivo.exists():
        return "inexistente"
    texto = arquivo.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", texto, re.S)
    if m:
        s = re.search(r"^status:\s*(\S+)", m.group(1), re.M)
        if s:
            return s.group(1).strip().lower()
    return "sem_status"


def exigir_aprovado(arquivo: Path, descricao: str) -> None:
    status = ler_status(arquivo)
    if status != "aprovado":
        raise ErroEtapa(
            f"Aprovação pendente: {descricao} (status atual: {status}). "
            f"Revise {arquivo.name} e troque para 'status: aprovado' para seguir."
        )


def eh_teste(pasta: Path) -> bool:
    """Projeto de teste: só usa serviços locais gratuitos e nunca é enviado ao YouTube."""
    arquivo = pasta / "projeto.json"
    return arquivo.exists() and bool(ler_json(arquivo).get("teste"))


def exigir_roteiro_aprovado(pasta: Path) -> None:
    if eh_teste(pasta) and ler_status(pasta / "roteiro.md") != "aprovado":
        log(pasta, "aprovacao", "AVISO: projeto de teste — seguindo sem roteiro aprovado "
                                "(só serviços locais, upload bloqueado).")
        return
    exigir_aprovado(pasta / "roteiro.md", "Roteiro")


# ---------------------------------------------------------------- mídia

def duracao_midia(arquivo: Path) -> float:
    import subprocess
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(arquivo)], capture_output=True, text=True, check=True).stdout
    return float(saida.strip())


def ffmpeg(*args: str) -> None:
    import subprocess
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ErroEtapa(f"ffmpeg falhou: {r.stderr.strip()[-800:]}")


def formatos_do_projeto(pasta: Path) -> list[str]:
    f = ler_json(pasta / "projeto.json").get("formato", "shorts")
    return ["longo", "shorts"] if f == "ambos" else [f]


def fonte(negrito: bool = True) -> str:
    """Fonte para textos: usa assets/fontes/ se houver, senão a do sistema."""
    proprias = sorted((RAIZ / "assets" / "fontes").glob("*.[ot]tf"))
    if proprias:
        return str(proprias[0])
    nome = "DejaVuSans-Bold.ttf" if negrito else "DejaVuSans.ttf"
    return f"/usr/share/fonts/truetype/dejavu/{nome}"


# ---------------------------------------------------------------- roteiro

CAMPOS_CENA = {"narração": "narracao", "narracao": "narracao",
               "visual": "visual", "duração": "duracao", "duracao": "duracao",
               "personagens": "personagens"}


def ler_cenas(pasta: Path) -> list[dict]:
    """Extrai as cenas do roteiro.md.

    Formato de cada cena:
        ## Cena 1 — Gancho
        **Narração:** texto falado
        **Visual:** descrição da imagem
        **Personagens:** davi, golias
        **Duração:** 6
    """
    texto = (pasta / "roteiro.md").read_text(encoding="utf-8")
    blocos = re.split(r"^##\s+Cena\s+", texto, flags=re.M)[1:]
    cenas = []
    for bloco in blocos:
        titulo, _, corpo = bloco.partition("\n")
        cena = {"titulo": titulo.strip(), "narracao": "", "visual": "",
                "duracao": 0.0, "personagens": []}
        for m in re.finditer(r"^\*\*(\w+):\*\*[ \t]*(.*)$", corpo, re.M):
            chave = CAMPOS_CENA.get(m.group(1).lower())
            if not chave:
                continue
            valor = m.group(2).strip()
            if chave == "duracao":
                cena[chave] = float(re.sub(r"[^\d.,]", "", valor).replace(",", ".") or 0)
            elif chave == "personagens":
                cena[chave] = [p.strip() for p in valor.split(",") if p.strip()]
            else:
                cena[chave] = valor
        cenas.append(cena)
    return cenas


# ---------------------------------------------------------------- CLI

def rodar(etapa: str, funcao, extras=None) -> None:
    """Executa uma etapa com o argumento padrão --projeto e tratamento de erro."""
    parser = argparse.ArgumentParser(description=etapa)
    parser.add_argument("--projeto", required=True, help="id do projeto (pasta em projetos/)")
    if extras:
        extras(parser)
    args = parser.parse_args()
    try:
        funcao(args)
    except ErroEtapa as e:
        try:
            log(pasta_projeto(args.projeto), etapa, f"PAROU: {e}")
        except ErroEtapa:
            print(f"[{etapa}] PAROU: {e}")
        sys.exit(1)
