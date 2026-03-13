import subprocess


def mix_audio(ffmpeg, narration, music, out_file, logger):
    logger.info("[AUDIO] Mixando audio")

    # Saída WAV real (PCM), não AAC em contêiner .wav
    cmd = [
        ffmpeg,
        "-y",
        "-i", narration,
        "-i", music,
        "-filter_complex", "[1:a]volume=0.12[a1];[0:a][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]",
        "-ar", "22050",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        out_file,
    ]

    subprocess.run(cmd, check=True)
    return out_file
