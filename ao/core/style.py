
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List

STYLE_BASE_DEFAULT = "documentary photography, 35mm lens, realistic photojournalism, low-key lighting, muted colors, analog film grain, atmospheric depth, historical realism, vertical composition"
NEGATIVE_PROMPT_DEFAULT = "anime, cartoon, illustration, graphic, text, watermark, blurry, low quality, distorted, deformed, malformed hands, extra fingers, duplicate, oversaturated, floating objects"
PT_TO_EN = {"atlântico":"atlantic ocean","oceano atlântico":"atlantic ocean","ilha":"island","colônia":"colony","colonos":"colonists","praia":"beach","desaparecimento":"disappearance","misterio":"mystery","mistério":"mystery","investigação":"investigation","investigacao":"investigation","provas":"evidence","evidências":"evidence","navio":"ship","floresta":"forest","vilarejo":"village","cidade":"city","antigo":"historic","sombrio":"dark","documental":"documentary"}
SCENE_TYPE_MOTIONS = {"establishing":"slow_zoom_out","character":"slow_push","detail":"slow_macro_push","evidence":"slow_pan_right","investigation":"slow_pan_left","reenactment":"slow_push","ending":"slow_pull_out"}
WEAK_SUBJECT_MAP = {"mystery":"archival evidence board","question mark":"archival evidence board","question":"archival evidence board","corpse":"covered body at investigation site","tragedy":"abandoned site after the event","fear":"investigator examining evidence","truth":"archival document close-up","history":"archival document close-up","case":"archival document close-up","avalanche":"snow slab breaking on mountain slope","research lab":"scientists studying archival data in laboratory","physical evidence":"archival evidence close-up","people connected":"historical group portrait"}
TOPIC_VISUAL_HINTS = {"somerton":{"location":"Somerton beach, Adelaide","era":"1948","subject":"forensic investigation on seaside sand"},"roanoke":{"location":"Roanoke Island","era":"1580s","subject":"abandoned colonial settlement"},"dyatlov":{"location":"Ural Mountains","era":"1959","subject":"abandoned expedition campsite"},"mh370":{"location":"Indian Ocean","era":"2014","subject":"aviation investigation control room"}}


def _slug(text:str)->str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")


def _clean_phrase(text:str)->str:
    text=(text or '').replace("\n"," ").strip(' ,.;:-')
    text=re.sub(r"\s+", " ", text)
    return text


def _split_tokens(text:str)->List[str]:
    if not text: return []
    text=text.replace(';',',')
    return [_clean_phrase(x) for x in text.split(',') if _clean_phrase(x)]


def normalize_prompt_text(text:str)->str:
    text=_clean_phrase(text)
    if not text: return ''
    lowered=text.lower()
    for pt,en in sorted(PT_TO_EN.items(), key=lambda x: len(x[0]), reverse=True):
        lowered=lowered.replace(pt,en)
    lowered = re.sub(r"\([^)]*\)", '', lowered)
    lowered = re.sub(r"foi um[a]?.*$", '', lowered)
    lowered = re.sub(r"[^a-z0-9,\-\s]", ' ', lowered)
    lowered = re.sub(r"\s+", ' ', lowered)
    parts=[]; seen=set()
    for part in _split_tokens(lowered):
        part=' '.join(part.split()[:10])
        if part and part not in seen:
            seen.add(part); parts.append(part)
    return ', '.join(parts)


def get_style_base(cfg:Dict[str,Any]|None=None)->str:
    cfg=cfg or {}; style_cfg=cfg.get('style',{}) or {}
    return style_cfg.get('base_prompt') or style_cfg.get('base_style') or STYLE_BASE_DEFAULT


def get_negative_prompt(cfg:Dict[str,Any]|None=None)->str:
    cfg=cfg or {}; style_cfg=cfg.get('style',{}) or {}; images_cfg=cfg.get('images',{}) or {}
    return style_cfg.get('negative_prompt') or images_cfg.get('negative_prompt') or NEGATIVE_PROMPT_DEFAULT


def _topic_hint_block(topic:str)->Dict[str,str]:
    slug=_slug(topic)
    for key,val in TOPIC_VISUAL_HINTS.items():
        if key in slug: return dict(val)
    return {}


def _sanitize_subject(text:str, topic:str, scene_type:str='')->str:
    normalized=normalize_prompt_text(text)
    lowered=normalized.lower().strip()
    if lowered in WEAK_SUBJECT_MAP: return WEAK_SUBJECT_MAP[lowered]
    if not lowered or len(lowered.split())<=1 or lowered in {'fernão','magalhães','fernao'}:
        hints=_topic_hint_block(topic)
        if scene_type=='investigation': return 'investigators examining archival evidence'
        if scene_type=='evidence': return 'physical evidence at the site'
        if scene_type=='ending': return 'abandoned location after the event'
        return hints.get('subject') or 'historical documentary scene'
    return ' '.join(normalized.split()[:8])


def sanitize_scene_fields(scene:Dict[str,Any], topic:str='')->Dict[str,Any]:
    scene=dict(scene)
    scene_type=(scene.get('scene_type') or 'detail').strip().lower()
    hints=_topic_hint_block(topic or scene.get('topic',''))
    scene['subject']=_sanitize_subject(scene.get('subject') or scene.get('subject_en') or '', topic or scene.get('topic',''), scene_type)
    scene['location']=' '.join(normalize_prompt_text(scene.get('location') or scene.get('location_en') or hints.get('location','')).split()[:8])
    scene['era']=' '.join(normalize_prompt_text(scene.get('era') or scene.get('era_en') or hints.get('era','')).split()[:6])
    scene['action']=' '.join(normalize_prompt_text(scene.get('action') or scene.get('action_en') or '').split()[:10])
    details=scene.get('details') or scene.get('details_en') or ', '.join(scene.get('objects_en') or [])
    parts=[]
    for p in _split_tokens(normalize_prompt_text(details)):
        if len(p.split())<=6 and p not in parts:
            parts.append(p)
    scene['details']=', '.join(parts[:5])
    scene['camera']=scene.get('camera') or 'documentary photography, 35mm lens'
    scene['lighting']=scene.get('lighting') or 'low-key lighting, muted colors'
    return scene


def compile_visual_prompt(subject:str, location:str='', era:str='', action:str='', details:str='', camera:str='documentary photography, 35mm lens', lighting:str='low-key lighting, muted colors', film_style:str|None=None, cfg:Dict[str,Any]|None=None, topic:str='', scene_type:str='')->str:
    film_style = film_style or get_style_base(cfg)
    subject=_sanitize_subject(subject, topic, scene_type)
    location=' '.join(normalize_prompt_text(location).split()[:8])
    era=' '.join(normalize_prompt_text(era).split()[:6])
    action=' '.join(normalize_prompt_text(action).split()[:10])
    details=', '.join(_split_tokens(normalize_prompt_text(details))[:4])
    ordered=[subject, location, era, action, details, camera, lighting, film_style]
    compact=[]; seen=set()
    for item in ordered:
        for part in _split_tokens(item):
            key=part.lower()
            if key and key not in seen:
                seen.add(key); compact.append(part)
    return ', '.join(compact[:14])


def build_scene_prompt_v9(scene:Dict[str,Any], cfg:Dict[str,Any]|None=None, topic:str='')->str:
    scene=sanitize_scene_fields(scene, topic=topic)
    return compile_visual_prompt(subject=scene.get('subject') or topic, location=scene.get('location') or '', era=scene.get('era') or '', action=scene.get('action') or '', details=scene.get('details') or '', camera=scene.get('camera') or 'documentary photography, 35mm lens', lighting=scene.get('lighting') or 'low-key lighting, muted colors', film_style=scene.get('film_style') or get_style_base(cfg), cfg=cfg, topic=topic, scene_type=scene.get('scene_type',''))


def infer_motion(scene_type:str)->str:
    return SCENE_TYPE_MOTIONS.get((scene_type or '').strip().lower(), 'slow_push')


def dedupe_visual_focus(plan:Iterable[Dict[str,Any]])->List[Dict[str,Any]]:
    deduped=[]; seen=set()
    for scene in plan or []:
        scene=sanitize_scene_fields(dict(scene), topic=scene.get('topic',''))
        signature='|'.join([_slug(scene.get('scene_type','')),_slug(scene.get('subject','')),_slug(scene.get('location','')),_slug(scene.get('era',''))]).strip('|')
        if signature in seen:
            extra=_clean_phrase(scene.get('details','') or scene.get('source_text','') or 'archival evidence')
            scene['details']=_clean_phrase(f"{scene.get('details','')}, {extra}")
            scene['prompt_en']=build_scene_prompt_v9(scene, cfg=None, topic=scene.get('topic',''))
            signature=f"{signature}|{_slug(scene.get('details','detail'))}"
        seen.add(signature)
        deduped.append(scene)
    return deduped

def factual_scene_filter(prompt: str) -> str:
    forbidden = [
        "dead body",
        "corpse discovered",
        "flight recorder recovered",
        "open cockpit"
    ]
    low = prompt.lower()
    for f in forbidden:
        if f in low:
            return "archival investigation evidence board, documents, low-key lighting"
    return prompt
