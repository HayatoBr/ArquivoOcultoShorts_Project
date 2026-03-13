from __future__ import annotations

MYSTERY_SEQUENCE = [
"initial_event",
"signal_loss",
"investigation_phase",
"search_operation",
"physical_evidence",
"unresolved_end"
]


import math
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Tuple

from .style import build_scene_prompt_v9, dedupe_visual_focus, infer_motion, sanitize_scene_fields

SCENE_MIN_DEFAULT = 6
SCENE_MAX_DEFAULT = 6
STOPWORDS = {"the","a","an","of","in","on","at","to","and","or","for","with","de","da","do","das","dos","e","ou","em","no","na","nos","nas","um","uma","uns","umas","para","com","por","sobre","from","into","during","after","before","this","that","these","those"}
BAD_SUBJECTS = {"mystery","question mark","mark","corpse","tragedy","fear","truth","case","history","story","legend","theory","evidence","incident"}
ROLE_ORDER = ["establishing","character","detail","evidence","investigation","ending"]


def _slug(text:str)->str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")


def _clean(text:str)->str:
    return re.sub(r"\s+", " ", (text or "").replace("\n"," ").replace("\r"," ").strip(" ,.;:-"))


def _split_sentences(text:str)->List[str]:
    text=_clean(text)
    return [_clean(x) for x in re.split(r"(?<=[\.!?])\s+", text) if _clean(x)]


def _tokenize(text:str)->List[str]:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t and t not in STOPWORDS]


def _similarity(a:str,b:str)->float:
    sa,sb=set(_tokenize(a)),set(_tokenize(b))
    return (len(sa&sb)/max(1,len(sa|sb))) if sa and sb else 0.0


def normalize_research_items(items: Iterable[Any]) -> List[Dict[str, Any]]:
    normalized=[]
    for idx,item in enumerate(items or [], start=1):
        if isinstance(item,str):
            text=_clean(item)
            if text: normalized.append({"id":f"item_{idx}","title":text[:120],"snippet":text,"source":"unknown","score":0.5})
        elif isinstance(item,dict):
            title=_clean(item.get('title') or item.get('name') or item.get('headline') or '')
            snippet=_clean(item.get('snippet') or item.get('summary') or item.get('text') or item.get('content') or title)
            source=_clean(item.get('source') or item.get('provider') or 'unknown')
            try: score=float(item.get('score', item.get('rank',0.5)))
            except Exception: score=0.5
            if title or snippet:
                normalized.append({"id":item.get('id') or f"item_{idx}","title":title or snippet[:120],"snippet":snippet or title,"source":source,"score":score})
    return normalized


def dedupe_research_items(items: Iterable[Dict[str, Any]], threshold: float = 0.72) -> List[Dict[str, Any]]:
    unique=[]
    for item in normalize_research_items(items):
        candidate=f"{item.get('title','')}. {item.get('snippet','')}"
        dup=False
        for chosen in unique:
            ref=f"{chosen.get('title','')}. {chosen.get('snippet','')}"
            if _similarity(candidate, ref)>=threshold:
                dup=True
                if item.get('score',0)>chosen.get('score',0): chosen.update(item)
                break
        if not dup: unique.append(dict(item))
    unique.sort(key=lambda x: float(x.get('score',0)), reverse=True)
    return unique


def _infer_era(topic:str, script_text:str, research_items:Iterable[Dict[str,Any]])->str:
    joined=' '.join([topic or '', script_text or '']+[f"{x.get('title','')} {x.get('snippet','')}" for x in normalize_research_items(research_items)])
    m=re.search(r"(1[5-9]\d{2}|20\d{2})", joined)
    return m.group(1) if m else ''


def _infer_location(topic:str, research_items:Iterable[Dict[str,Any]])->str:
    joined=' '.join([topic or '']+[f"{x.get('title','')} {x.get('snippet','')}" for x in normalize_research_items(research_items)])
    # prefer phrases after in/em/de near capitals
    m=re.search(r"(?:in|em|de)\s+([A-ZÁÉÍÓÚÂÊÔÃÕ][\wÁÉÍÓÚÂÊÔÃÕç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÁÉÍÓÚÂÊÔÃÕç]+){0,3})", joined)
    return _clean(m.group(1)) if m else ''


def _extract_evidence_terms(research_items:Iterable[Dict[str,Any]])->List[str]:
    pool=[]
    for item in dedupe_research_items(research_items):
        pool.extend(re.split(r"(?<=[\.!?])\s+", _clean(item.get('snippet',''))))
    out=[]
    for s in pool:
        low=s.lower()
        if any(k in low for k in ['document', 'map', 'letter', 'tent', 'rope', 'boat', 'ship', 'journal', 'footprint', 'track', 'wreck', 'body', 'clothing', 'weapon', 'compass', 'chart']):
            out.append(s)
    return out[:8]


def _scene_type_for_index(idx:int,total:int)->str:
    if total<=len(ROLE_ORDER): return ROLE_ORDER[idx-1]
    return ROLE_ORDER[min(idx-1, len(ROLE_ORDER)-1)]


def _pick_scene_count(text:str,cfg:Dict[str,Any]|None=None)->int:
    cfg=cfg or {}
    planner_cfg=cfg.get('scene_planner',{}) or {}
    min_scenes=int(planner_cfg.get('min_scenes',SCENE_MIN_DEFAULT))
    max_scenes=int(planner_cfg.get('max_scenes',SCENE_MAX_DEFAULT))
    return max(min_scenes, min(max_scenes, 6))


def _chunk_script(script_text:str, n_chunks:int)->List[str]:
    units=_split_sentences(script_text)
    if not units: return []
    while len(units)<n_chunks:
        longest=max(range(len(units)), key=lambda i: len(units[i].split()))
        words=units.pop(longest).split(); cut=max(5,len(words)//2)
        units.insert(longest, ' '.join(words[:cut])); units.insert(longest+1, ' '.join(words[cut:]))
    chunk_size=max(1, math.ceil(len(units)/n_chunks))
    chunks=[_clean(' '.join(units[i:i+chunk_size])) for i in range(0,len(units),chunk_size)]
    while len(chunks)>n_chunks:
        tail=chunks.pop(); chunks[-1]=_clean(chunks[-1]+' '+tail)
    return chunks[:n_chunks]


def _sanitize_short_field(text:str, max_words:int)->str:
    text=_clean(text)
    text=re.sub(r"\([^)]*\)", '', text)
    text=re.sub(r"foi um[a]?.*$", '', text, flags=re.I)
    words=text.split()
    return ' '.join(words[:max_words]).strip(' ,.;:-')


def _make_scene(role:str, topic:str, chunk:str, location:str, era:str, evidence_terms:List[str], idx:int)->Dict[str,Any]:
    ev = evidence_terms[min(idx-1, len(evidence_terms)-1)] if evidence_terms else ''
    if role=='establishing':
        subject='historical landscape connected to the event'; action='wide establishing view'; details='terrain, weather, distant structures, traces of passage'
    elif role=='character':
        subject='people involved in the documented event'; action='preparing equipment or moving carefully'; details='clothing, tools, posture, faces, objects'
    elif role=='detail':
        subject='archival object or personal item'; action='close-up documentary detail'; details='surface texture, wear marks, nearby objects'
    elif role=='evidence':
        subject='physical evidence at the site'; action='evidence exposed in the environment'; details='tracks, damaged objects, documents, disturbed ground'
    elif role=='investigation':
        subject='investigators examining documents and evidence'; action='comparing records and physical traces'; details='maps, notebooks, measured observations, archival material'
    else:
        subject='abandoned site after the event'; action='stillness after the event'; details='silence, fading light, empty ground, distant horizon'
    if ev and role in {'detail','evidence','investigation'}:
        details = _sanitize_short_field(ev, 10)
    return {"scene_index":idx,"scene_type":role,"topic":topic,"subject":subject,"location":location,"era":era,"action":_sanitize_short_field(chunk, 10) or action,"details":details,"source_text":chunk,"seed_group":f"scene_group_{((idx-1)//2)+1}","motion":infer_motion(role),"camera":"documentary photography, 35mm lens","lighting":"low-key lighting, muted colors"}


def heuristic_scene_plan(topic:str, script_text:str, research_items:Iterable[Dict[str,Any]]|None=None, cfg:Dict[str,Any]|None=None)->List[Dict[str,Any]]:
    cfg=cfg or {}
    n=_pick_scene_count(script_text,cfg)
    era=_infer_era(topic, script_text, research_items or [])
    location=_infer_location(topic, research_items or [])
    evidence_terms=_extract_evidence_terms(research_items or [])
    chunks=_chunk_script(script_text, n) or [topic]*n
    plan=[]
    for idx, chunk in enumerate(chunks, start=1):
        role=_scene_type_for_index(idx, len(chunks))
        scene=_make_scene(role, topic, chunk, location, era, evidence_terms, idx)
        scene=sanitize_scene_fields(scene, topic=topic)
        scene['prompt_en']=build_scene_prompt_v9(scene, cfg=cfg, topic=topic)
        plan.append(scene)
    return dedupe_visual_focus(plan)


def normalize_scene_plan(plan:Iterable[Any], topic:str, cfg:Dict[str,Any]|None=None)->List[Dict[str,Any]]:
    cfg=cfg or {}
    normalized=[]
    for idx, scene in enumerate(plan or [], start=1):
        if isinstance(scene, str):
            scene={"scene_index":idx,"scene_type":_scene_type_for_index(idx,6),"topic":topic,"subject":topic,"action":scene,"details":scene}
        elif isinstance(scene, dict):
            scene=dict(scene)
        else:
            continue
        scene['scene_index']=int(scene.get('scene_index') or idx)
        scene['scene_type']=scene.get('scene_type') or _scene_type_for_index(idx,6)
        scene['topic']=scene.get('topic') or topic
        scene['subject']=_sanitize_short_field(scene.get('subject') or scene.get('subject_en') or topic, 8)
        scene['location']=_sanitize_short_field(scene.get('location') or scene.get('location_en') or '', 8)
        scene['era']=_sanitize_short_field(scene.get('era') or scene.get('era_en') or '', 6)
        scene['action']=_sanitize_short_field(scene.get('action') or scene.get('action_en') or scene.get('source_text') or '', 10)
        scene['details']=_sanitize_short_field(scene.get('details') or scene.get('details_en') or '', 12)
        scene['seed_group']=scene.get('seed_group') or f"scene_group_{((idx-1)//2)+1}"
        scene['motion']=scene.get('motion') or infer_motion(scene['scene_type'])
        scene['camera']=scene.get('camera') or 'documentary photography, 35mm lens'
        scene['lighting']=scene.get('lighting') or 'low-key lighting, muted colors'
        scene=sanitize_scene_fields(scene, topic=topic)
        scene['prompt_en']=build_scene_prompt_v9(scene, cfg=cfg, topic=topic)
        normalized.append(scene)
    return dedupe_visual_focus(normalized)


def planner_looks_weak(plan:Iterable[Dict[str,Any]], min_unique_subjects:int=5)->bool:
    plan=list(plan or [])
    if len(plan)<SCENE_MIN_DEFAULT: return True
    subjects={_slug(x.get('subject','')) for x in plan if _slug(x.get('subject',''))}
    prompts={_slug(x.get('prompt_en','')) for x in plan if _slug(x.get('prompt_en',''))}
    if len(subjects)<min_unique_subjects or len(prompts)<max(5,len(plan)-1): return True
    if any(_clean(x.get('subject','')).lower() in BAD_SUBJECTS for x in plan): return True
    return False


def enforce_scene_bounds(plan:List[Dict[str,Any]], script_text:str, topic:str, research_items:Iterable[Dict[str,Any]]|None=None, cfg:Dict[str,Any]|None=None)->List[Dict[str,Any]]:
    cfg=cfg or {}
    planner_cfg=cfg.get('scene_planner',{}) or {}
    min_scenes=int(planner_cfg.get('min_scenes',SCENE_MIN_DEFAULT)); max_scenes=int(planner_cfg.get('max_scenes',SCENE_MAX_DEFAULT))
    if len(plan)<min_scenes: return heuristic_scene_plan(topic, script_text, research_items, cfg)
    plan=plan[:max_scenes]
    final=[]
    for idx, scene in enumerate(plan, start=1):
        scene['scene_index']=idx; scene['scene_type']=scene.get('scene_type') or _scene_type_for_index(idx,len(plan)); scene['motion']=scene.get('motion') or infer_motion(scene.get('scene_type','detail'))
        scene=sanitize_scene_fields(scene, topic=topic); scene['prompt_en']=build_scene_prompt_v9(scene, cfg=cfg, topic=topic); final.append(scene)
    return dedupe_visual_focus(final)


def choose_best_scene_plan(topic:str, script_text:str, research_items:Iterable[Dict[str,Any]]|None=None, planner_output:Iterable[Any]|None=None, cfg:Dict[str,Any]|None=None)->Tuple[List[Dict[str,Any]],Dict[str,Any]]:
    cfg=cfg or {}
    if planner_output:
        normalized=normalize_scene_plan(planner_output, topic=topic, cfg=cfg)
        if not planner_looks_weak(normalized):
            final_plan=enforce_scene_bounds(normalized, script_text, topic, research_items, cfg)
            return final_plan, {"source":"planner_output","weak":False,"scene_count":len(final_plan)}
    final_plan=heuristic_scene_plan(topic, script_text, research_items, cfg)
    final_plan=enforce_scene_bounds(final_plan, script_text, topic, research_items, cfg)
    return final_plan, {"source":"heuristic_fallback","weak":True,"scene_count":len(final_plan)}


def build_scene_plan(topic:str, script_text:str, research_items:Iterable[Dict[str,Any]]|None=None, planner_output:Iterable[Any]|None=None, cfg:Dict[str,Any]|None=None)->List[Dict[str,Any]]:
    plan,_=choose_best_scene_plan(topic, script_text, research_items, planner_output, cfg)
    return plan

def enforce_scene_realism(scene: dict) -> dict:
    forbidden = [
        "flight data recorder recovered",
        "open cockpit",
        "dead body found",
        "confirmed killer"
    ]
    subj = (scene.get("subject") or "").lower()
    for f in forbidden:
        if f in subj:
            scene["subject"] = "archival investigation evidence"
    return scene
