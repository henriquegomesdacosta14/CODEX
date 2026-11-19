"""[8] Upload no YouTube (Data API v3 + OAuth). Só roda com revisao_final.md aprovado.

Sempre PRIVADO ou AGENDADO, nunca público direto.
"""
from .comum import (RAIZ, carregar_config, exigir_aprovado, exigir_roteiro_aprovado, log,
                    pasta_projeto, rodar, ErroEtapa)

ETAPA = "8-upload"


def args_extras(p):
    p.add_argument("--agendar", help="data/hora ISO 8601 para publicação agendada")


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    exigir_aprovado(pasta / "revisao_final.md", "Revisão final")
    cfg = carregar_config()["upload"]
    if cfg["privacidade_padrao"] not in ("private", "agendado"):
        raise ErroEtapa("config.yaml: privacidade_padrao precisa ser 'private' ou 'agendado'.")
    if not (RAIZ / "client_secret.json").exists():
        raise ErroEtapa("client_secret.json não encontrado na pasta canal-dark/.")
    log(pasta, ETAPA, "Aprovação final ok.")
    # TODO: conferir na documentação oficial atual as cotas e a regra de projetos
    # não verificados (upload restrito a privado) antes de implementar.
    raise ErroEtapa("Upload ainda não implementado.")


if __name__ == "__main__":
    rodar(ETAPA, main, args_extras)
