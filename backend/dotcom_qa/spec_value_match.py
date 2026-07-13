"""
spec_value_match.py — 큐비 — Spec QA [V3] 값 우선(value-first) 다국어 매칭 계층

[2026-07 전면 재설계 배경]
  기존 엔진은 label-first였다: 번역된 attribute 라벨을 사전으로 찾고, 그 주변 텍스트를
  잘라 정답과 비교. 91개 사이트·30여 개 언어에서 라벨 번역/DOM이 제각각이라 태생적으로
  취약했고, 실제로 "고해상도의 동영상…" 같은 마케팅 문장이 Resolution의 '찾은 값'으로
  잘려 들어와 Critical 오탐을 냈다 (KR Fold7 PDP 사례 — 회귀 테스트로 고정).

  V3 원칙 (운영 결정 사항):
    · 판정 질문을 뒤집는다 — "라벨 옆 텍스트가 정답과 같은가?"(X)
      → "이 단위를 단 숫자 중 정답 집합 밖의 것이 페이지에 있는가?"(O)
    · 값 없음 ≠ 오류. FAIL은 '틀린 값이 실제로 적혀 있다'는 적극적 증거가 있을 때만.
    · 복수 정답: expected "4400|4272" — 어느 값이든 노출되면 PASS.
    · 한정어(qualifier) 교차검증: "일반(Typical) 4,272mAh"처럼 짝이 틀리면 숫자가
      집합 안에 있어도 FAIL. (배터리 외 모든 스펙에 공통 적용)
    · 근사("약 8인치")·단위 환산(inch→cm) 표기는 FAIL이 아닌 확인(warn) 등급.
    · 전작 귀속: 같은 블록에 전작 모델명(Galaxy Z Fold6 등)이 있으면 그 숫자는 전작
      소속 — 전작 정답지(previous_models)와 대조해 pass(무시)/fail을 판단한다.
      PDP에 전작 비교 문구가 매우 흔하기 때문 ("Fold6의 1,750니트보다 밝아진…").

  다국어 대응 (요구: 2600 nits = 2,600 nits = 2600nits = 2600니트 = 2,600니트 = ٢٦٠٠ نت):
    · 숫자: 아랍-인도 숫자(٠-٩/۰-۹)·전각(０-９) → ASCII, 천단위(콤마/점/공백) 제거,
      소수점 콤마(6,5 → 6.5) 변환.
    · 단위: 정준 단위별 다국어 동의어 테이블. 기본값은 코드에 내장하고, Rule DB 엑셀의
      'UnitSynonym' 시트(운영자 관리)가 있으면 병합/확장한다 — 운영 결정: 혼합이 아닌
      "엑셀 운영자 관리"이지만, 엑셀이 아직 없는 제품도 동작해야 하므로 기본 테이블을
      깔고 엑셀이 항상 우선(추가·확장)되게 한다.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

# ── ① 텍스트/숫자 정규화 ──────────────────────────────────────────────
_UNICODE_MAP = {
    "\u2011": "-", "\u2010": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u00d7": "x", "\u2715": "x", "\u2716": "x",           # × ✕ ✖
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",           # 공백류
}
# 아랍-인도(٠١٢٣٤٥٦٧٨٩) · 동아랍/페르시아(۰-۹) · 전각(０-９) 숫자 → ASCII
_DIGIT_TRANS = {}
for i in range(10):
    _DIGIT_TRANS[ord("\u0660") + i] = str(i)   # Arabic-Indic
    _DIGIT_TRANS[ord("\u06f0") + i] = str(i)   # Extended Arabic-Indic (Persian/Urdu)
    _DIGIT_TRANS[ord("\uff10") + i] = str(i)   # Fullwidth


def normalize_text(s: str) -> str:
    """유니코드 통일 → 숫자 스크립트 통일 → 천단위 제거 → 소수점 콤마 변환 → 소문자.
    · 천단위: 2,600 / 2.600(DE) / 2 600(FR) → 2600 ('뒤 정확히 3자리'일 때만)
    · 소수점 콤마: 위 처리 후 남은 '숫자,숫자1~2자리'는 소수점 — 6,5 Zoll → 6.5 zoll
      (2,600은 천단위 규칙이 먼저 소거하므로 여기 걸리지 않는다)"""
    s = str(s or "")
    for k, v in _UNICODE_MAP.items():
        s = s.replace(k, v)
    s = s.translate(_DIGIT_TRANS)
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)
    s = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", s)
    s = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", s)
    s = re.sub(r"(?<=\d),(?=\d{1,2}(?!\d))", ".", s)   # 소수점 콤마 → 점
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _fmt_num(x: float) -> str:
    return f"{x:g}"


# ── ② 단위 동의어 (기본 내장 — Rule DB 엑셀 'UnitSynonym' 시트가 병합·우선) ──
# canonical → 표기 변형 리스트. 검색은 normalize_text 이후 소문자 기준.
DEFAULT_UNIT_SYNONYMS: Dict[str, List[str]] = {
    "nits":  ["nits", "nit", "니트", "ニト", "尼特", "нит", "نت", "نيت"],
    "hz":    ["hz", "hertz", "헤르츠", "ヘルツ", "赫兹", "赫茲", "гц", "هرتز"],
    "inch":  ["inch", "inches", "in.", "\"", "인치", "インチ", "英寸", "吋", "英吋",
              "zoll", "pouces", "pouce", "pulgadas", "pulgada", "pollici",
              "polegadas", "cali", "дюйм", "дюйма", "дюймов", "بوصة", "นิ้ว", "inci"],
    "mah":   ["mah", "밀리암페어시", "ミリアンペア時", "毫安时", "毫安時", "мач", "مللي أمبير"],
    "w":     ["w", "watt", "watts", "와트", "ワット", "瓦", "вт", "واط"],
    "hours": ["hours", "hour", "hrs", "hr", "h", "시간", "時間", "小时", "小時",
              "stunden", "heures", "horas", "ore", "godzin", "часов", "часа", "ساعة", "ชั่วโมง", "jam", "giờ"],
    "g":     ["g", "grams", "gram", "그램", "グラム", "克", "gramm", "grammes", "gramos", "грамм", "جرام", "غرام"],
    "mm":    ["mm", "밀리미터", "ミリメートル", "毫米", "мм", "ملم", "مم"],
    "mp":    ["mp", "megapixel", "megapixels", "화소", "메가픽셀", "메가 픽셀", "画素",
              "メガピクセル", "百万像素", "мп", "ميجابكسل"],
    "gb":    ["gb", "기가바이트", "ギガバイト", "гб"],
    "tb":    ["tb", "테라바이트", "テラバイト", "тб"],
    "x":     ["x", "배", "倍", "х"],
    "px":    ["px", "pixels", "pixel", "픽셀", "ピクセル", "像素"],
    "atm":   ["atm"],
    # 환산 관계 단위(직접 정답 단위는 아니지만 발견 시 '확인' 등급 근거)
    "cm":    ["cm", "센티미터", "センチ", "センチメートル", "厘米", "公分", "см", "سم"],
}
# canonical 단위 표준화 (룰 DB unit 컬럼 표기 흔들림 흡수)
_UNIT_CANON = {
    "inch": "inch", "인치": "inch", "\"": "inch", "in": "inch",
    "hz": "hz", "nits": "nits", "nit": "nits", "mah": "mah", "w": "w",
    "hours": "hours", "hour": "hours", "hrs": "hours", "h": "hours",
    "g": "g", "mm": "mm", "mp": "mp", "gb": "gb", "tb": "tb",
    "x": "x", "px": "px", "atm": "atm", "cm": "cm",
}
# [V3.1] 오답 단정이 불가능한 범용 단위 — 라벨 동반 불일치도 FAIL 대신 확인(warn).
# 'x'(줌 배율): 광학 3배 외에 "광학 줌 수준의 2배"(센서 크롭)·"30배 스페이스 줌" 등
# 렌즈/주장별 정당한 값이 공존한다.
GENERIC_AMBIGUOUS_UNITS = {"x"}

# 단위 환산: 정답 단위 → {발견될 수 있는 다른 단위: 계수} (발견값 = 정답값 × 계수)
_UNIT_CONVERSIONS: Dict[str, Dict[str, float]] = {
    "inch": {"cm": 2.54, "mm": 25.4},
}
# 근사 마커 — 숫자 바로 앞뒤에 있으면 '확인' 등급 (※ '최대/up to'는 스펙 자체가
# 최대치이므로 근사가 아니다 — 포함하지 않는다)
_APPROX_RX = re.compile(
    r"(약|약\s|大約|大约|約|approx\.?|approximately|ca\.|circa|~|≈|environ|aprox\.?|"
    r"etwa|rund|대략|около|примерно|حوالي|ประมาณ|khoảng|sekitar)", re.I)


def canon_unit(u: str) -> str:
    u = normalize_text(u)
    return _UNIT_CANON.get(u, u)


def build_unit_synonyms(ruleset: Dict[str, Any]) -> Dict[str, List[str]]:
    """기본 테이블 ∪ Rule DB 엑셀 'UnitSynonym' 시트(ruleset['unit_synonyms']).
    운영자 엑셀 항목이 항상 추가·우선된다."""
    merged = {k: list(v) for k, v in DEFAULT_UNIT_SYNONYMS.items()}
    for canon, variants in (ruleset.get("unit_synonyms") or {}).items():
        c = canon_unit(canon)
        cur = merged.setdefault(c, [])
        for v in variants:
            nv = normalize_text(v)
            if nv and nv not in cur:
                cur.insert(0, nv)  # 운영자 표기를 우선 순위 앞에
    return merged


def _unit_alt(variants: List[str]) -> str:
    """단위 변형들 → 정규식 alternation (긴 것부터 — 'in.'이 'in'보다 먼저)."""
    vs = sorted({normalize_text(v) for v in variants if v}, key=len, reverse=True)
    return "|".join(re.escape(v) for v in vs)


# ── ③ 값 발견(hit) 스캔 ────────────────────────────────────────────────
def scan_unit_hits(blocks: List[str], unit: str,
                   unit_synonyms: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """블록 리스트에서 `숫자 + (공백?) + 단위표기` 패턴을 전부 수집.
    반환 hit: {value: float, unit, text: 매칭 원문, block: 블록 원문, approx: bool}
    · 붙여쓰기(2600nits/2600니트)와 띄어쓰기(2,600 nits) 모두 매칭.
    · 단위 표기 뒤에 글자가 이어지면 제외 (nits 뒤 알파벳 — 'nitsX' 방지). CJK 단위는
      뒤에 조사가 붙는 게 정상(니트의)이므로 라틴 단위만 뒤 경계를 요구한다."""
    cu = canon_unit(unit)
    variants = unit_synonyms.get(cu, [cu])
    alt = _unit_alt(variants)
    if not alt:
        return []
    # 범용 단위 'x'(줌 배율)는 '숫자 x 숫자'(해상도 2184 x 1968) 패턴을 제외해야 한다 —
    # 그렇지 않으면 해상도의 x가 줌 배율로 오인된다(회귀 테스트 L 고정).
    tail_guard = r"(?![a-z])" if cu != "x" else r"(?![a-z])(?!\s*\d)"
    rx = re.compile(r"(\d+(?:\.\d+)?)\s*(" + alt + r")" + tail_guard)
    out: List[Dict[str, Any]] = []
    for block in blocks:
        nb = normalize_text(block)
        for m in rx.finditer(nb):
            val = float(m.group(1))
            ctx_pre = nb[max(0, m.start() - 12):m.start()]
            approx = bool(_APPROX_RX.search(ctx_pre))
            out.append({"value": val, "unit": cu, "text": m.group(0),
                        "block": block, "block_norm": nb, "pos": m.start(),
                        "approx": approx})
    return out


def scan_conversion_hits(blocks: List[str], unit: str, accepted: List[float],
                         unit_synonyms: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """정답 단위의 환산 표기(inch 정답인데 cm로 적힘) 발견 — '확인' 등급 근거.
    환산값이 정답×계수의 ±2% 이내면 환산 표기로 인정한다."""
    cu = canon_unit(unit)
    out: List[Dict[str, Any]] = []
    for other, factor in _UNIT_CONVERSIONS.get(cu, {}).items():
        for h in scan_unit_hits(blocks, other, unit_synonyms):
            for a in accepted:
                target = a * factor
                if target and abs(h["value"] - target) / target <= 0.02:
                    out.append({**h, "converted_from": cu, "matches_accepted": a})
    return out


# ── ④ 정답 집합·한정어 파싱 ───────────────────────────────────────────
def parse_accepted(expected: str) -> List[str]:
    """'4400|4272' → ['4400','4272'] · '8.0' → ['8.0']  (option_match의 '/'와 별개)"""
    return [p.strip() for p in str(expected or "").split("|") if p.strip()]


def parse_qualifiers(qualifier: str) -> Dict[str, List[str]]:
    """'4400=typical,일반,標準;4272=rated,정격,定格'
       → {'4400': ['typical','일반','標準'], '4272': [...]} (값·키워드 모두 normalize)"""
    out: Dict[str, List[str]] = {}
    for part in re.split(r"[;\n]", str(qualifier or "")):
        if "=" not in part:
            continue
        val, kws = part.split("=", 1)
        v = normalize_text(val)
        if v:
            out[v] = [normalize_text(k) for k in kws.split(",") if normalize_text(k)]
    return out


# ── ⑤ 모델 귀속 (전작 비교 문구 인식) ─────────────────────────────────
def model_tokens(prev_models: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """previous_models → [(normalize된 토큰, 모델키)] — 긴 토큰 우선 매칭."""
    toks: List[Tuple[str, str]] = []
    for pm in prev_models or []:
        names = [pm.get("model", "")] + list(pm.get("aliases") or [])
        for n in names:
            nn = normalize_text(n)
            if nn:
                toks.append((nn, pm.get("model", "")))
    toks.sort(key=lambda t: len(t[0]), reverse=True)
    return toks


def attribute_block(block_norm: str, tokens: List[Tuple[str, str]]) -> Optional[str]:
    """블록에 전작 모델 토큰이 있으면 해당 모델키 반환 (없으면 None = 검수 대상 제품)."""
    for tok, model in tokens:
        if tok in block_norm:
            return model
    return None


def prev_accepted_for(prev_models: List[Dict[str, Any]], model: Optional[str],
                      unit: str, any_model: bool = False) -> Optional[List[float]]:
    """전작 모델의 해당 단위 정답 숫자 합집합. 스펙 정보가 없으면 None(판정 불가).
    any_model=True면 모델 구분 없이 전 전작의 합집합 — '전작 값 혼입' 검사용."""
    cu = canon_unit(unit)
    vals: List[float] = []
    found_any = False
    for pm in prev_models or []:
        if not any_model and pm.get("model") != model:
            continue
        for sp in pm.get("specs") or []:
            if canon_unit(sp.get("unit", "")) != cu:
                continue
            found_any = True
            for v in sp.get("values") or []:
                n = re.search(r"\d+(?:\.\d+)?", normalize_text(str(v)))
                if n:
                    vals.append(float(n.group()))
    return vals if found_any else None


# ── ⑥ 룰 하나에 대한 값 우선 판정 ─────────────────────────────────────
def evaluate_numeric(rule: Dict[str, Any], blocks: List[str],
                     unit_synonyms: Dict[str, List[str]],
                     prev_models: List[Dict[str, Any]],
                     unit_accepted_union: Dict[str, set],
                     label_in_block=None) -> Dict[str, Any]:
    """numeric_exact 룰의 V3 판정.
    반환: {status: pass|fail|warn|na, found, message, detail[], confidence}
      · pass — 정답 집합 값이 (한정어 모순 없이) 발견됨
      · fail — 틀린 값의 적극적 증거: 한정어 오짝 / 라벨 동반 불일치 / 전작 스펙과 불일치
      · warn — 근사·환산 표기, 또는 라벨 없는 단독 불일치 (사람 확인 필요)
      · na   — 이 단위의 숫자가 페이지에 없음 (오류 아님 — 표시·집계 제외)
    unit_accepted_union: 같은 단위를 쓰는 '모든' 룰의 정답 합집합 — RAM 12GB가
    Storage 룰에서 오답으로 잡히는 것을 막는다.
    label_in_block(block)->bool: 이 룰의 attribute 라벨/alias가 블록에 있는지 (오답의
    라벨 동반 여부 판단 — FAIL 승격 조건)."""
    unit = canon_unit(rule.get("unit", ""))
    accepted_str = parse_accepted(rule.get("expected", ""))
    accepted = []
    for a in accepted_str:
        m = re.search(r"\d+(?:\.\d+)?", normalize_text(a))
        if m:
            accepted.append(float(m.group()))
    quals = parse_qualifiers(rule.get("qualifier", ""))
    union = unit_accepted_union.get(unit, set(accepted))
    detail: List[str] = []

    hits = scan_unit_hits(blocks, unit, unit_synonyms)
    conv = scan_conversion_hits(blocks, unit, accepted, unit_synonyms) if accepted else []
    toks = model_tokens(prev_models)

    exact_pass_hit = None
    approx_hit = None
    qualifier_fail = None
    label_fail = None
    lone_mismatch = None
    prev_fail = None

    for h in hits:
        owner = attribute_block(h["block_norm"], toks)
        if owner:  # ── 전작 소속 숫자 ──
            pv = prev_accepted_for(prev_models, owner, unit)
            if pv is None:
                detail.append(f"'{owner}' 문장의 {_fmt_num(h['value'])}{unit} — 전작 스펙 미등록, 판정 보류")
                continue
            if h["value"] in pv or h["value"] in union:
                detail.append(f"'{owner}' 비교 문구의 {_fmt_num(h['value'])}{unit} — 전작 정답과 일치(정상)")
            else:
                prev_fail = (h, owner, pv)
            continue
        # ── 검수 대상 제품 소속 숫자 ──
        prev_all = prev_accepted_for(prev_models, None, unit, any_model=True) or []
        if h["value"] in accepted:
            if h["approx"]:
                approx_hit = approx_hit or h
                continue
            # 한정어 교차검증: 같은 블록에 '다른 정답값'의 한정어가 붙어 있으면 오짝
            mism = _qualifier_mismatch(h, accepted_str, quals)
            if mism:
                qualifier_fail = qualifier_fail or (h, mism)
            else:
                exact_pass_hit = exact_pass_hit or h
        elif h["value"] in prev_all and label_in_block and label_in_block(h["block"]):
            # [V3.2] 모델명 없이도 전작 정답값이 이 항목 라벨과 함께 적혀 있으면
            # 전작 값 혼입(예: Fold7 페이지에 "무게 239g") — 오기재로 승격
            label_fail = label_fail or h
        elif h["value"] in union:
            continue  # 같은 단위 다른 스펙의 정답(RAM 12 vs Storage 256 등) — 무관
        else:
            if label_in_block and label_in_block(h["block"]):
                # [V3.1] 범용 단위(x=줌 배율)는 라벨 동반이어도 FAIL로 단정하지 않는다 —
                # "광학 줌 수준의 2배"(센서 크롭 광학급 줌)처럼 렌즈/주장에 따라 정당한
                # 다른 값이 흔해 오답 단정이 불가 → 확인(warn) 등급으로만.
                if unit in GENERIC_AMBIGUOUS_UNITS:
                    lone_mismatch = lone_mismatch or h
                else:
                    label_fail = label_fail or h
            else:
                lone_mismatch = lone_mismatch or h

    # ── 우선순위대로 결론 ── (오짝/라벨 동반 오답 > 정답 발견 > 전작 오답 > 확인 > 없음)
    if qualifier_fail:
        h, mism = qualifier_fail
        return {"status": "fail", "found": h["block"][:120], "confidence": "high",
                "message": (f"한정어 오짝 — '{mism['keyword']}'는 {mism['should_be']}{unit}의 "
                            f"한정어인데 {_fmt_num(h['value'])}{unit}에 붙어 있음"),
                "detail": detail + [f"qualifier mismatch @ '{h['block'][:60]}'"]}
    if label_fail:
        h = label_fail
        return {"status": "fail", "found": h["block"][:120], "confidence": "high",
                "message": (f"오기재 — 정답 {'/'.join(accepted_str)}{unit}이 아닌 "
                            f"{_fmt_num(h['value'])}{unit}이 항목 라벨과 함께 표기됨"),
                "detail": detail + [f"labeled wrong value @ '{h['block'][:60]}'"]}
    if exact_pass_hit:
        st = {"status": "pass", "found": exact_pass_hit["text"], "confidence": "high",
              "message": "OK", "detail": detail}
        if prev_fail:  # 정답은 있는데 전작 문구의 전작 값이 틀림 — 별도로 오류 보고
            h, owner, pv = prev_fail
            st = {"status": "fail", "found": h["block"][:120], "confidence": "high",
                  "message": (f"전작 오기재 — '{owner}'의 {unit} 정답은 "
                              f"{'/'.join(_fmt_num(v) for v in pv)}인데 {_fmt_num(h['value'])}로 표기됨"),
                  "detail": detail + ["current value OK; predecessor value wrong"]}
        return st
    if prev_fail:
        h, owner, pv = prev_fail
        return {"status": "fail", "found": h["block"][:120], "confidence": "high",
                "message": (f"전작 오기재 — '{owner}'의 {unit} 정답은 "
                            f"{'/'.join(_fmt_num(v) for v in pv)}인데 {_fmt_num(h['value'])}로 표기됨"),
                "detail": detail}
    if approx_hit or conv:
        h = approx_hit or conv[0]
        kind = "근사 표기" if approx_hit else f"단위 환산 표기({h.get('text','')})"
        return {"status": "warn", "found": h["block"][:120], "confidence": "medium",
                "message": f"{kind} 발견 — 정답 {'/'.join(accepted_str)}{unit}과 상응하나 표기 방식 확인 필요",
                "detail": detail}
    if lone_mismatch:
        h = lone_mismatch
        return {"status": "warn", "found": h["block"][:120], "confidence": "medium",
                "message": (f"확인 필요 — 정답 집합 밖 {_fmt_num(h['value'])}{unit} 발견 "
                            f"(항목 라벨 미동반: 문맥상 다른 대상일 수 있음)"),
                "detail": detail}
    return {"status": "na", "found": "", "confidence": "",
            "message": f"{unit} 값이 페이지에 없음 (오류 아님)", "detail": detail}


def _qualifier_mismatch(hit: Dict[str, Any], accepted_str: List[str],
                        quals: Dict[str, List[str]]) -> Optional[Dict[str, str]]:
    """hit 블록에 '다른 정답값의 한정어'가 있으면 오짝 정보 반환."""
    if not quals:
        return None
    bn = hit["block_norm"]
    hv = _fmt_num(hit["value"])
    for val, kws in quals.items():
        vnum = re.search(r"\d+(?:\.\d+)?", val)
        if not vnum or _fmt_num(float(vnum.group())) == hv:
            continue  # 자기 자신의 한정어는 정상
        for kw in kws:
            if kw and kw in bn:
                # 단, 그 블록에 해당 정답값 자체도 함께 있으면(둘 다 표기) 정상으로 본다
                if re.search(r"(?<!\d)" + re.escape(val) + r"(?!\d)", bn):
                    continue
                return {"keyword": kw, "should_be": _fmt_num(float(vnum.group()))}
    return None


# ── ⑦ 값 우선 exact 검색 (해상도 '2184 x 1968', IP48, 제품명 등) ────────
def find_exact(blocks: List[str], expected_variants: List[str]) -> Optional[str]:
    """정규화 텍스트에서 expected(복수 정답 중 하나) 포함 블록 검색 — 숫자·고유 토큰은
    언어 불문이므로 값 자체 검색이 언어 중립적이다."""
    evs = [normalize_text(e) for e in expected_variants if normalize_text(e)]
    for block in blocks:
        nb = normalize_text(block)
        for ev in evs:
            if ev in nb:
                return block
    return None


def find_resolution_conflict(blocks: List[str], expected_variants: List[str],
                             prev_models: List[Dict[str, Any]],
                             label_in_block=None) -> Optional[Dict[str, str]]:
    """'NNNN x NNNN' 패턴 중 정답 집합·전작 정답에 없는 것이 라벨과 함께 있으면 충돌.
    (해상도류 exact 룰의 오답 탐지 — 라벨 미동반이면 다른 제품/맥락일 수 있어 보류)"""
    evs = {normalize_text(e) for e in expected_variants}
    prev_ok = set()
    for pm in prev_models or []:
        for sp in pm.get("specs") or []:
            for v in sp.get("values") or []:
                nv = normalize_text(str(v))
                if re.search(r"\d+\s*x\s*\d+", nv):
                    prev_ok.add(re.sub(r"\s*x\s*", " x ", nv))
    rx = re.compile(r"\d{3,4}\s*x\s*\d{3,4}")
    toks = model_tokens(prev_models)
    for block in blocks:
        nb = normalize_text(block)
        for m in rx.finditer(nb):
            token = re.sub(r"\s*x\s*", " x ", m.group(0))
            if any(token == re.sub(r"\s*x\s*", " x ", e) for e in evs):
                continue
            owner = attribute_block(nb, toks)
            if owner and token in prev_ok:
                continue
            if label_in_block and label_in_block(block) and not owner:
                return {"found_token": token, "block": block}
    return None
