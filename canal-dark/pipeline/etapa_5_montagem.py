"""[5] Montagem: ffmpeg, Ken Burns, transições, trilha com ducking -> video/<formato>.mp4.

Exige a fonte/licença de toda música usada registrada em creditos.txt.
"""
from .comum import exigir_roteiro_aprovado, log, pasta_projeto, rodar, ErroEtapa

ETAPA = "5-montagem"


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    for sub in ("audio", "imagens"):
        if not (pasta / sub).is_dir() or not any((pasta / sub).iterdir()):
            raise ErroEtapa(f"Falta a pasta '{sub}/' com conteúdo (rode as etapas 3 e 4).")
    log(pasta, ETAPA, "Entradas encontradas.")
    raise ErroEtapa("Montagem será implementada no vídeo de teste.")


if __name__ == "__main__":
    rodar(ETAPA, main)
