"""[4] Imagens das cenas: imagens/cena_NN_<formato>.png, com personagens consistentes."""
from .comum import (carregar_config, carregar_personagens, exigir_chave, exigir_definido,
                    exigir_roteiro_aprovado, ler_cenas, log, pasta_projeto, rodar, ErroEtapa)

ETAPA = "4-imagens"


def montar_prompt(cena, cfg, personagens):
    partes = [cena["visual"]]
    for nome in cena["personagens"]:
        if nome not in personagens:
            raise ErroEtapa(f"Personagem '{nome}' não está em personagens.yaml.")
        partes.append(personagens[nome]["descricao"])
    if cfg["estilo_visual"].get("prompt_base"):
        partes.append(cfg["estilo_visual"]["prompt_base"])
    return ". ".join(partes)


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    cfg = carregar_config()
    exigir_definido(cfg["imagens"]["servico"], "imagens.servico")
    exigir_definido(cfg["estilo_visual"]["direcao"], "estilo_visual.direcao")
    personagens = carregar_personagens()
    prompts = [montar_prompt(c, cfg, personagens) for c in ler_cenas(pasta)]
    exigir_chave("IMAGEM_API_KEY")
    (pasta / "imagens").mkdir(exist_ok=True)
    log(pasta, ETAPA, f"{len(prompts)} prompts montados para {cfg['imagens']['servico']}.")
    # TODO: integrar o serviço escolhido, seguindo a documentação oficial dele.
    raise ErroEtapa(f"Integração com '{cfg['imagens']['servico']}' ainda não implementada.")


if __name__ == "__main__":
    rodar(ETAPA, main)
