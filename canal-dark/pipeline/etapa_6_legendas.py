"""[6] Legendas: legendas.srt (para enviar ao YouTube) + legenda animada queimada nos Shorts.

Tempos: vêm de audio/tempos.json (início/duração da fala de cada cena). Dentro da cena,
o tempo de cada trecho é proporcional ao número de letras. Quando a narração real
estiver pronta, isto pode ser refinado com timestamps palavra a palavra (Whisper ou
os timestamps do próprio serviço de voz).

Saídas:
  legendas.srt              — frases curtas, para o YouTube
  video/shorts_legendas.ass — legenda animada (2 a 4 palavras por vez)
  video/shorts_final.mp4    — Shorts com a legenda queimada
"""
import re

from .comum import (RAIZ, ErroEtapa, carregar_config, exigir_roteiro_aprovado, ffmpeg,
                    formatos_do_projeto, ler_json, log, pasta_projeto, rodar)

ETAPA = "6-legendas"


def dividir(texto, max_palavras, max_letras):
    """Quebra o texto em trechos curtos, respeitando a pontuação."""
    trechos, atual = [], []
    for palavra in texto.split():
        atual.append(palavra)
        fim_frase = re.search(r"[.!?:;,]$", palavra)
        if len(atual) >= max_palavras or len(" ".join(atual)) >= max_letras or fim_frase:
            trechos.append(" ".join(atual))
            atual = []
    if atual:
        trechos.append(" ".join(atual))
    return trechos


def cronometrar(tempos, max_palavras, max_letras):
    itens = []
    for c in tempos["cenas"]:
        trechos = dividir(c["texto"], max_palavras, max_letras)
        letras = sum(len(t) for t in trechos) or 1
        t0 = c["inicio"]
        for t in trechos:
            dur = c["fala"] * len(t) / letras
            itens.append((t0, t0 + dur, t))
            t0 += dur
    return itens


def hms(seg, sep=","):
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)) % 1000:03d}"


def ass_tempo(seg):
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def gerar_srt(itens, destino):
    linhas = []
    for n, (ini, fim, txt) in enumerate(itens, 1):
        linhas += [str(n), f"{hms(ini)} --> {hms(fim)}", txt, ""]
    destino.write_text("\n".join(linhas), encoding="utf-8")


def gerar_ass(itens, destino, w, h, nome_fonte):
    tamanho = int(w * 0.085)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Principal,{nome_fonte},{tamanho},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,{int(tamanho * 0.09)},{int(tamanho * 0.05)},2,60,60,{int(h * 0.28)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    for k, (ini, fim, txt) in enumerate(itens):
        cor = r"\c&H00D7FF&" if k % 3 == 2 else ""          # destaque amarelo-dourado
        anim = r"{\fscx70\fscy70" + cor + r"\t(0,110,\fscx105\fscy105)\t(110,180,\fscx100\fscy100)}"
        eventos.append(f"Dialogue: 0,{ass_tempo(ini)},{ass_tempo(fim)},Principal,,0,0,0,,"
                       f"{anim}{txt.upper()}")
    destino.write_text(cab + "\n".join(eventos) + "\n", encoding="utf-8")


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    arq_tempos = pasta / "audio" / "tempos.json"
    if not arq_tempos.exists():
        raise ErroEtapa("Falta audio/tempos.json (rode a etapa 3).")
    tempos = ler_json(arq_tempos)
    cfg = carregar_config()

    gerar_srt(cronometrar(tempos, 8, 42), pasta / "legendas.srt")
    log(pasta, ETAPA, "legendas.srt gerado.")

    if "shorts" in formatos_do_projeto(pasta):
        video = pasta / "video" / "shorts.mp4"
        if not video.exists():
            raise ErroEtapa("Falta video/shorts.mp4 (rode a etapa 5).")
        fmt = cfg["formatos"]["shorts"]
        ass = pasta / "video" / "shorts_legendas.ass"
        fontes = RAIZ / "assets" / "fontes"
        tem_fonte_propria = any(fontes.glob("*.[ot]tf"))
        nome_fonte = cfg.get("legendas", {}).get("fonte", "DejaVu Sans") \
            if tem_fonte_propria else "DejaVu Sans"
        gerar_ass(cronometrar(tempos, 3, 18), ass, fmt["largura"], fmt["altura"], nome_fonte)
        filtro = f"ass={ass}" + (f":fontsdir={fontes}" if tem_fonte_propria else "")
        v = cfg["video"]
        ffmpeg("-i", str(video), "-vf", filtro, "-c:v", v["codec_video"], "-preset", v["preset"],
               "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
               str(pasta / "video" / "shorts_final.mp4"))
        log(pasta, ETAPA, "Legenda animada queimada: video/shorts_final.mp4.")


if __name__ == "__main__":
    rodar(ETAPA, main)
