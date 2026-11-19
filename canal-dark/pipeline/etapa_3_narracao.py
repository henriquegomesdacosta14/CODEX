"""[3] Narração (TTS): um áudio por cena em audio/cena_NN.mp3 + audio/narracao_completa.mp3."""
from .comum import (carregar_config, exigir_chave, exigir_definido, exigir_roteiro_aprovado,
                    ler_cenas, log, pasta_projeto, rodar, ErroEtapa)

ETAPA = "3-narracao"


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    cfg = carregar_config()["voz"]
    exigir_definido(cfg["servico"], "voz.servico")
    exigir_definido(cfg["voz_id"], "voz.voz_id")
    exigir_chave("TTS_API_KEY")
    cenas = ler_cenas(pasta)
    (pasta / "audio").mkdir(exist_ok=True)
    log(pasta, ETAPA, f"{len(cenas)} cenas para narrar com {cfg['servico']}.")
    # TODO: integrar o serviço escolhido, seguindo a documentação oficial dele.
    raise ErroEtapa(f"Integração com '{cfg['servico']}' ainda não implementada.")


if __name__ == "__main__":
    rodar(ETAPA, main)
