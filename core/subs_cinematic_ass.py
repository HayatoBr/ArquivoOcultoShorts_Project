import re
from dataclasses import dataclass
from typing import List

_TIME_RE = re.compile(r"(\d+):(\d+):(\d+),(\d+)")

def _parse_time(t: str) -> float:
    m = _TIME_RE.search(t.strip())
    if not m:
        raise ValueError(f"Invalid timestamp: {t!r}")
    hh, mm, ss, ms = map(int, m.groups())
    return hh*3600 + mm*60 + ss + ms/1000.0

def _fmt_ass_time(seconds: float) -> str:
    # ASS time: H:MM:SS.cs (centiseconds)
    if seconds < 0:
        seconds = 0.0
    cs = int(round(seconds * 100.0))
    s = cs // 100
    cs2 = cs % 100
    hh = s // 3600
    mm = (s % 3600) // 60
    ss = s % 60
    return f"{hh}:{mm:02d}:{ss:02d}.{cs2:02d}"

@dataclass
class Cue:
    start: float
    end: float
    text: str

def load_srt(path: str) -> List[Cue]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().replace("\r\n", "\n").replace("\r", "\n")

    blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
    cues: List[Cue] = []
    for b in blocks:
        lines = [ln.strip() for ln in b.split("\n") if ln.strip()]
        if len(lines) < 2:
            continue
        if "-->" in lines[0]:
            time_line = lines[0]
            text_lines = lines[1:]
        else:
            time_line = lines[1] if len(lines) > 1 else ""
            text_lines = lines[2:]
        if "-->" not in time_line:
            continue
        a, b2 = [x.strip() for x in time_line.split("-->", 1)]
        start = _parse_time(a)
        end = _parse_time(b2.split()[0].strip())
        text = " ".join(text_lines).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            cues.append(Cue(start=start, end=end, text=text))
    return cues

def _wrap_words(words: List[str], max_chars: int, max_lines: int) -> List[str]:
    lines: List[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur) + 1 + len(w) <= max_chars:
            cur = cur + " " + w
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                return lines
    if cur:
        lines.append(cur)
    return lines[:max_lines]

def _split_text(text: str, max_chars: int, max_lines: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    return _wrap_words(words, max_chars=max_chars, max_lines=max_lines)

def _estimate_duration(text: str, target_cps: float, min_dur: float, max_dur: float) -> float:
    n = max(1, len(text))
    dur = n / max(1e-6, target_cps)
    dur = max(min_dur, min(max_dur, dur))
    return dur

def normalize_cues(cues: List[Cue],
                   max_chars_per_line: int = 26,
                   max_lines: int = 2,
                   target_cps: float = 12.0,
                   min_dur: float = 0.7,
                   max_dur: float = 2.2,
                   min_gap: float = 0.05) -> List[Cue]:
    out: List[Cue] = []
    for c in cues:
        text = c.text.strip()
        if not text:
            continue
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"\s+", " ", text).strip()

        words = text.split()
        max_total_chars = max_chars_per_line * max_lines

        # chunk by total characters (2 lines max)
        chunk_texts: List[str] = []
        cur: List[str] = []
        cur_len = 0
        for w in words:
            add = len(w) + (1 if cur else 0)
            if cur_len + add <= max_total_chars:
                cur.append(w)
                cur_len += add
            else:
                chunk_texts.append(" ".join(cur))
                cur = [w]
                cur_len = len(w)
        if cur:
            chunk_texts.append(" ".join(cur))

        t0 = c.start
        t1 = c.end
        avail = max(0.01, t1 - t0)
        desired = sum(_estimate_duration(ct, target_cps, min_dur, max_dur) for ct in chunk_texts)
        scale = min(1.0, avail / desired) if desired > 0 else 1.0

        for ct in chunk_texts:
            dur = _estimate_duration(ct, target_cps, min_dur, max_dur) * scale
            start = t0
            end = min(t1, start + dur)
            if out and start < out[-1].end + min_gap:
                start = out[-1].end + min_gap
                end = min(t1, start + dur)
            if end - start < 0.2:
                continue
            lines = _split_text(ct, max_chars=max_chars_per_line, max_lines=max_lines)
            disp = r"\N".join(lines) if lines else ct
            out.append(Cue(start=start, end=end, text=disp))
            t0 = end
            if t0 >= t1 - 0.05:
                break
    return out

def write_ass(out_ass: str,
              cues: List[Cue],
              play_res_x: int = 576,
              play_res_y: int = 1024,
              font: str = "Arial",
              font_size: int = 13,
              margin_v: int = 48,
              margin_l: int = 56,
              margin_r: int = 56,
              outline: int = 2,
              shadow: int = 1,
              fade_in_ms: int = 70,
              fade_out_ms: int = 120,
              blur: float = 0.6) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_l},{margin_r},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    fad_tag = f"{{\\fad({fade_in_ms},{fade_out_ms})\\blur{blur}}}"
    for c in cues:
        s = _fmt_ass_time(c.start)
        e = _fmt_ass_time(c.end)
        txt = c.text.replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{s},{e},Default,,0,0,0,,{fad_tag}{txt}\n")

    with open(out_ass, "w", encoding="utf-8-sig") as f:
        f.writelines(lines)

def make_cinematic_ass_from_srt(cfg: dict, srt_path: str, ass_path: str) -> dict:
    subs_cfg = cfg.get("subs") or {}
    video_cfg = cfg.get("video") or {}
    w = int(video_cfg.get("width", 576))
    h = int(video_cfg.get("height", 1024))

    cues = load_srt(srt_path)
    norm = normalize_cues(
        cues,
        max_chars_per_line=int(subs_cfg.get("max_chars_per_line", 26)),
        max_lines=int(subs_cfg.get("max_lines", 2)),
        target_cps=float(subs_cfg.get("target_cps", 12.0)),
        min_dur=float(subs_cfg.get("min_dur", 0.7)),
        max_dur=float(subs_cfg.get("max_dur", 2.2)),
        min_gap=float(subs_cfg.get("min_gap", 0.05)),
    )

    write_ass(
        ass_path,
        norm,
        play_res_x=w,
        play_res_y=h,
        font=str(subs_cfg.get("font", "Arial")),
        font_size=int(subs_cfg.get("font_size", 13)),
        margin_v=int(subs_cfg.get("margin_v", 48)),
        margin_l=int(subs_cfg.get("margin_lr", 56)),
        margin_r=int(subs_cfg.get("margin_lr", 56)),
        outline=int(subs_cfg.get("outline", 2)),
        shadow=int(subs_cfg.get("shadow", 1)),
        fade_in_ms=int(subs_cfg.get("fade_in_ms", 70)),
        fade_out_ms=int(subs_cfg.get("fade_out_ms", 120)),
        blur=float(subs_cfg.get("blur", 0.6)),
    )

    return {
        "input_srt": srt_path,
        "output_ass": ass_path,
        "cues_in": len(cues),
        "cues_out": len(norm),
    }
