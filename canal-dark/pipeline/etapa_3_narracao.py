"""[3] Narração (TTS): audio/cena_NN.wav por cena + audio/narracao_completa.wav.

Também grava audio/tempos.json com início e duração de cada cena na linha do tempo,
que as etapas 5 (montagem) e 6 (legendas) usam para sincronizar.

Serviços:
  - local (projetos de teste): espeak-ng com voz MBROLA brasileira. Gratuito, robótico.
  - o serviço definido em config.yaml (ex.: elevenlabs) para os vídeos reais.
"""
import shutil
import subprocess

from .comum import (ErroEtapa, carregar_config, duracao_midia, eh_teste, exigir_chave,
                    exigir_definido, exigir_roteiro_aprovado, ffmpeg, ler_cenas, log,
                    pasta_projeto, rodar, salvar_json)

ETAPA = "3-narracao"
PAUSA_ENTRE_CENAS = 0.35   # segundos de respiro depois de cada cena
TAXA = "44100"


def tts_local(texto: str, destino) -> None:
    if not shutil.which("espeak-ng"):
        raise ErroEtapa("espeak-ng não instalado (apt-get install espeak-ng mbrola-br3).")
    bruto = destino.with_suffix(".bruto.wav")
    subprocess.run(["espeak-ng", "-v", "mb-br3", "-s", "150", "-w", str(bruto), texto],
                   check=True)
    # normaliza para 44,1 kHz estéreo
    ffmpeg("-i", str(bruto), "-ar", TAXA, "-ac", "2", str(destino))
    bruto.unlink()


def main(args):
    pasta = pasta_projeto(args.projeto)
    exigir_roteiro_aprovado(pasta)
    cenas = ler_cenas(pasta)
    if not cenas:
        raise ErroEtapa("Roteiro sem cenas.")

    if eh_teste(pasta):
        sintetizar, servico = tts_local, "local (espeak-ng, provisório)"
    else:
        cfg = carregar_config()["voz"]
        servico = exigir_definido(cfg["servico"], "voz.servico")
        exigir_definido(cfg["voz_id"], "voz.voz_id")
        exigir_chave("TTS_API_KEY")
        # TODO: integrar o serviço escolhido, seguindo a documentação oficial dele.
        raise ErroEtapa(f"Integração com '{servico}' ainda não implementada.")

    pasta_audio = pasta / "audio"
    pasta_audio.mkdir(exist_ok=True)
    tempos, inicio, lista = [], 0.0, []
    for i, cena in enumerate(cenas, 1):
        arq = pasta_audio / f"cena_{i:02d}.wav"
        sintetizar(cena["narracao"], arq)
        fala = duracao_midia(arq)
        # cena com pausa no fim -> segmento de duração fixa na linha do tempo
        seg = pasta_audio / f"seg_{i:02d}.wav"
        ffmpeg("-i", str(arq), "-af", f"apad=pad_dur={PAUSA_ENTRE_CENAS}", str(seg))
        dur = duracao_midia(seg)
        tempos.append({"cena": i, "inicio": round(inicio, 3), "fala": round(fala, 3),
                       "duracao": round(dur, 3), "texto": cena["narracao"]})
        lista.append(f"file '{seg.name}'")
        inicio += dur

    (pasta_audio / "lista.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(pasta_audio / "lista.txt"),
           "-c", "copy", str(pasta_audio / "narracao_completa.wav"))
    salvar_json(pasta_audio / "tempos.json", {"servico": servico, "cenas": tempos,
                                              "total": round(inicio, 3)})
    log(pasta, ETAPA, f"{len(cenas)} cenas narradas com {servico}. Total: {inicio:.1f} s.")


if __name__ == "__main__":
    rodar(ETAPA, main)
