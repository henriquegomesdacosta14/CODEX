"""[5] Montagem: Ken Burns + transições + trilha com ducking -> video/<formato>.mp4.

Entradas: imagens/cena_NN_<formato>.png, audio/narracao_completa.wav, audio/tempos.json.

Trilha:
  - config.yaml video.musica = nome de um arquivo em assets/musicas/. Ao lado dele deve
    existir <mesmo nome>.txt com a fonte e a licença; o texto é copiado para creditos.txt.
  - vazio: gera um fundo ambiente por código (sem direitos de terceiros).
"""
from .comum import (RAIZ, ErroEtapa, carregar_config, exigir_roteiro_aprovado, ffmpeg,
                    formatos_do_projeto, ler_json, log, pasta_projeto, rodar)

ETAPA = "5-montagem"
TRANSICAO = 0.4   # segundos de fusão entre cenas

# movimentos alternados para não ficar repetitivo
MOVIMENTOS = ["zoom_in", "pan_direita", "zoom_out", "pan_cima", "zoom_in_lateral", "pan_esquerda"]


def expressao_movimento(nome, frames):
    t = f"(on/{max(frames - 1, 1)})"            # 0 -> 1 ao longo da cena
    centro_x, centro_y = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    if nome == "zoom_in":
        return f"1.0+0.18*{t}", centro_x, centro_y
    if nome == "zoom_out":
        return f"1.18-0.18*{t}", centro_x, centro_y
    if nome == "zoom_in_lateral":
        return f"1.05+0.15*{t}", f"(iw-iw/zoom)*(0.3+0.4*{t})", centro_y
    if nome == "pan_direita":
        return "1.15", f"(iw-iw/zoom)*{t}", centro_y
    if nome == "pan_esquerda":
        return "1.15", f"(iw-iw/zoom)*(1-{t})", centro_y
    if nome == "pan_cima":
        return "1.15", centro_x, f"(ih-ih/zoom)*(1-{t})"
    raise ValueError(nome)


def preparar_trilha(pasta, total, cfg_video):
    musica = (cfg_video.get("musica") or "").strip()
    creditos = pasta / "creditos.txt"
    if musica:
        arq = RAIZ / "assets" / "musicas" / musica
        licenca = arq.with_suffix(".txt")
        if not arq.exists():
            raise ErroEtapa(f"Música {arq} não encontrada.")
        if not licenca.exists():
            raise ErroEtapa(f"Falta {licenca.name} com a fonte e a licença da música.")
        creditos.write_text(f"Música: {musica}\n{licenca.read_text(encoding='utf-8')}",
                            encoding="utf-8")
        return ["-stream_loop", "-1", "-i", str(arq)]
    creditos.write_text("Música: fundo ambiente gerado por código pelo próprio pipeline "
                        "(sem direitos de terceiros).\n", encoding="utf-8")
    # acorde grave em ré menor com leve pulsação
    notas = [73.42, 110.0, 146.83, 174.61]
    expr = "+".join(f"0.18*sin(2*PI*{f}*t)*(0.7+0.3*sin(2*PI*0.{k + 1}*t))"
                    for k, f in enumerate(notas))
    return ["-f", "lavfi", "-t", f"{total:.2f}", "-i",
            f"aevalsrc={expr}:s=44100:c=stereo"]


def montar(pasta, formato, cfg):
    tempos = ler_json(pasta / "audio" / "tempos.json")
    cenas = tempos["cenas"]
    total = tempos["total"]
    fmt = cfg["formatos"][formato]
    w, h, fps = fmt["largura"], fmt["altura"], cfg["video"]["fps"]
    v = cfg["video"]

    entradas, filtros = [], []
    for i, c in enumerate(cenas):
        img = pasta / "imagens" / f"cena_{c['cena']:02d}_{formato}.png"
        if not img.exists():
            raise ErroEtapa(f"Falta {img.name} (rode a etapa 4).")
        dur = c["duracao"] + (TRANSICAO if i < len(cenas) - 1 else 0)
        frames = int(round(dur * fps))
        z, x, y = expressao_movimento(MOVIMENTOS[i % len(MOVIMENTOS)], frames)
        entradas += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(img)]
        # amplia antes do zoompan para o movimento ficar suave (sem tremido)
        filtros.append(
            f"[{i}:v]scale={w * 3}:-2,zoompan=z='{z}':x='{x}':y='{y}':d={frames}:"
            f"s={w}x{h}:fps={fps},setsar=1,format=yuv420p,trim=duration={dur:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]")

    # cadeia de transições: cada cena começa exatamente quando o áudio dela começa
    ultimo = "v0"
    for i in range(1, len(cenas)):
        saida = f"x{i}"
        filtros.append(f"[{ultimo}][v{i}]xfade=transition=fade:duration={TRANSICAO}:"
                       f"offset={cenas[i]['inicio']:.3f}[{saida}]")
        ultimo = saida

    n = len(cenas)
    entradas += ["-i", str(pasta / "audio" / "narracao_completa.wav")]
    entradas += preparar_trilha(pasta, total, v)
    vol = v.get("volume_musica", 0.12)
    filtros.append(
        f"[{n}:a]asplit=2[narr][chave];"
        f"[{n + 1}:a]volume={vol},afade=t=in:d=1.5,afade=t=out:st={max(total - 2, 0):.2f}:d=2,"
        f"atrim=duration={total:.3f}[mus];"
        f"[mus][chave]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=400[mus_d];"
        f"[narr][mus_d]amix=inputs=2:duration=first:normalize=0,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11[a]")

    destino = pasta / "video"
    destino.mkdir(exist_ok=True)
    saida = destino / f"{formato}.mp4"
    ffmpeg(*entradas, "-filter_complex", ";".join(filtros), "-map", f"[{ultimo}]", "-map", "[a]",
           "-c:v", v["codec_video"], "-preset", v["preset"], "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", v["codec_audio"], "-b:a", "192k", "-ar", "44100",
           "-t", f"{total:.3f}", "-movflags", "+faststart", str(saida))
    return saida, total


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    if not (pasta / "audio" / "tempos.json").exists():
        raise ErroEtapa("Falta audio/tempos.json (rode a etapa 3).")
    cfg = carregar_config()
    for formato in formatos_do_projeto(pasta):
        saida, total = montar(pasta, formato, cfg)
        log(pasta, ETAPA, f"Vídeo {formato} montado: {saida.relative_to(pasta)} ({total:.1f} s).")


if __name__ == "__main__":
    rodar(ETAPA, main)
