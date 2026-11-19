"""[6] Legendas: legendas.srt (YouTube) + legenda animada queimada para Shorts."""
from .comum import exigir_roteiro_aprovado, log, pasta_projeto, rodar, ErroEtapa

ETAPA = "6-legendas"


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    log(pasta, ETAPA, "Iniciando.")
    raise ErroEtapa("Legendas serão implementadas no vídeo de teste (Whisper para timestamps).")


if __name__ == "__main__":
    rodar(ETAPA, main)
