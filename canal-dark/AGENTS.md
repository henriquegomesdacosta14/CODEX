# AGENTS.md — canal-dark

Pipeline de vídeos para um canal dark (histórias bíblicas, público geral). Veja o README.md.

Regras obrigatórias:
- Nunca publicar sem `revisao_final.md` com `status: aprovado`, marcado pelo Henrique.
- Upload sempre privado ou agendado, nunca público direto. Marcar "não é para crianças"
  e a declaração de conteúdo sintético.
- Não aprovar roteiro nem revisão final no lugar do Henrique: só ele troca o `status:`.
- Não inventar chaves, endpoints, preços ou limites de API: consultar a documentação oficial
  ou perguntar.
- Nunca commitar `.env`, `client_secret*.json`, tokens ou a pasta `projetos/`.
- Um vídeo por vez, revisado individualmente. Nada de lote sem revisão.
- Música só royalty-free, com fonte e licença em `projetos/<id>/creditos.txt`.
- Roteiro sempre com a referência bíblica (livro, capítulo, versículos) e fiel ao texto.
