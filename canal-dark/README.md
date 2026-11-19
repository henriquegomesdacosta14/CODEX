# Canal Dark — Pipeline de Vídeos

Pipeline em Python que leva uma história bíblica da ideia ao upload no YouTube,
com **duas aprovações humanas obrigatórias**: o roteiro e a revisão final.

## Fluxo

```
[1] Tema → [2] Roteiro → APROVAÇÃO → [3] Narração → [4] Imagens → [5] Montagem
→ [6] Legendas → [7] Thumbnail + metadados → APROVAÇÃO FINAL → [8] Upload (privado/agendado)
```

Cada etapa roda sozinha, a partir desta pasta:

```bash
pip install -r requirements.txt
python -m pipeline.etapa_1_tema     --projeto davi-golias --tema "Davi e Golias"
python -m pipeline.etapa_2_roteiro  --projeto davi-golias            # cria o modelo
python -m pipeline.etapa_2_roteiro  --projeto davi-golias --validar
# revisar projetos/davi-golias/roteiro.md e trocar para "status: aprovado"
python -m pipeline.etapa_3_narracao --projeto davi-golias
python -m pipeline.etapa_4_imagens  --projeto davi-golias
python -m pipeline.etapa_5_montagem --projeto davi-golias
python -m pipeline.etapa_6_legendas --projeto davi-golias
python -m pipeline.etapa_7_thumb_meta --projeto davi-golias
# revisar vídeo/thumbnail/metadados e trocar revisao_final.md para "status: aprovado"
python -m pipeline.etapa_8_upload   --projeto davi-golias
```

Ideia livre, sem usar o temas.csv:

```bash
python -m pipeline.etapa_1_tema --projeto jonas --ideia "Jonas fugindo de Deus" --passagem "Jonas 1-2"
```

## Arquivos de um projeto (`projetos/<id>/`)

| Arquivo | Etapa | Conteúdo |
|---|---|---|
| `projeto.json` | 1 | título, passagem, formato |
| `roteiro.md` | 2 | cenas (narração, visual, personagens, duração) + `status:` |
| `audio/` | 3 | um áudio por cena + narração completa |
| `imagens/` | 4 | imagens por cena (1920x1080 e/ou 1080x1920) |
| `video/` | 5 | MP4 H.264 + AAC |
| `legendas.srt` | 6 | legenda para o YouTube |
| `thumbnail.png`, `metadados.json` | 7 | thumbnail 1280x720, título, descrição, tags |
| `revisao_final.md` | 7 | checklist + `status:` da aprovação final |
| `creditos.txt` | 5 | fonte e licença das músicas |
| `log.txt` | todas | registro do que cada etapa fez |

`projetos/` não vai para o git (vídeos são pesados).

## Segredos

- Copie `.env.example` para `.env` e preencha as chaves. **O `.env` nunca vai para o git.**
- `client_secret.json` (OAuth do YouTube) fica nesta pasta, fora do git.

## Estado atual

| Etapa | Situação |
|---|---|
| 1 Tema, 2 Roteiro | funcionando |
| 3 Narração | modo teste com voz local (espeak-ng + MBROLA); aguarda serviço real + chave |
| 4 Imagens | modo teste com ilustração provisória por código; aguarda serviço real + chave |
| 5 Montagem | funcionando (Ken Burns, transições, trilha com ducking, volume -14 LUFS) |
| 6 Legendas | funcionando (.srt + legenda animada nos Shorts); tempos estimados por cena |
| 7 Thumbnail e metadados | funcionando |
| 8 Upload | aguarda `client_secret.json`; travas de aprovação e privacidade já ativas |

### Modo teste

`--teste` na etapa 1 cria um projeto que usa só serviços locais gratuitos e **nunca** é
enviado ao YouTube. Ele roda sem o roteiro aprovado, só para conferir ritmo e montagem.

```bash
sudo apt-get install -y espeak-ng mbrola-br3   # voz provisória
python -m pipeline.etapa_1_tema --projeto teste-davi-golias --teste --tema "Davi e Golias"
```

## Decisões em aberto

1. Estilo visual final (direção inicial: mangá/anime)
2. Serviço de geração de imagens
3. Serviço de voz e voz escolhida
4. Formato inicial (Shorts, longo ou os dois)
5. Fonte de pesquisa de palavras-chave
6. Frequência de postagem
7. Nome e identidade visual do canal
