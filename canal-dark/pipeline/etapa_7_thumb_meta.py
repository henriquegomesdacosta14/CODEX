"""[7] Thumbnail 1280x720 + metadados.json, e cria revisao_final.md para a APROVAÇÃO FINAL."""
from .comum import exigir_roteiro_aprovado, ler_json, log, pasta_projeto, rodar, ErroEtapa

ETAPA = "7-thumb-meta"

REVISAO = """---
status: pendente
---

# Revisão final — {titulo}

Antes de aprovar, confira:
- [ ] Assisti ao vídeo inteiro (imagem, áudio, legendas)
- [ ] Thumbnail legível no celular
- [ ] Título, descrição (com a passagem bíblica) e tags em metadados.json
- [ ] Créditos e licença da música em creditos.txt
- [ ] Data/privacidade do upload conferidas

Para liberar o upload, troque 'status: pendente' por 'status: aprovado'.
"""


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    p = ler_json(pasta / "projeto.json")
    revisao = pasta / "revisao_final.md"
    if not revisao.exists():
        revisao.write_text(REVISAO.format(titulo=p["titulo"]), encoding="utf-8")
    log(pasta, ETAPA, "revisao_final.md criado (status: pendente).")
    raise ErroEtapa("Thumbnail e metadados serão implementados no vídeo de teste.")


if __name__ == "__main__":
    rodar(ETAPA, main)
