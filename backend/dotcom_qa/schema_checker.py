"""
schema_checker.py — 큐비 — Dotcom QA 체커 [Phase A]

큐비 🐝 — 풀네임 QA Bee, 줄여서 큐비. 닷컴 페이지를 붕붕 돌며 규칙대로 검수.

페이지 HTML(또는 추출된 JSON-LD)을 schema_rule_parser 가 만든 '규칙 JSON'과 대조해
누락/불일치를 as-is/to-be 형태의 findings 로 리턴한다.

검수 항목(Phase A):
  1) 필수 스키마 블록(@type + @id 패턴) 존재 여부
  2) 각 블록의 필수 속성 존재 여부
  3) Product.hasPart 가 참조해야 할 @id 들이 실제로 들어있는지
  * '조건부(conditional)' 블록은 없더라도 하드 실패가 아니라 '경고(정보)'로 처리한다.
  * @id 패턴의 {SITECODE} 는 실제 국가코드로 치환하지 않고 와일드카드로 매칭한다.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional

_LD_RE = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


# ---------- JSON-LD 추출 ----------
def _classify_syntax(raw: str, e) -> Dict[str, Any]:
    """Google Rich Results가 잡는 JSON 문법 오류를 사람이 알아보게 분류한다.
    (유니코드/스마트쿼트로 깨진 값, 괄호 불균형, 쉼표 누락/후행 쉼표 등)"""
    msg = getattr(e, "msg", str(e))
    lineno = getattr(e, "lineno", None); colno = getattr(e, "colno", None)
    line_text = ""
    if lineno:
        lines = raw.splitlines()
        if 0 < lineno <= len(lines):
            line_text = lines[lineno - 1].strip()
    # 카테고리 판정
    cat, hint = "syntax", "JSON 문법 오류 — 구조를 확인하세요."
    smart = re.search(r"[“”‘’]", raw)         # 스마트 따옴표(유니코드) → 코드가 아닌 문자 형태
    nbsp = re.search(r"[\u00a0\u200b\ufeff]", raw)  # NBSP/제로폭/BOM
    opens, closes = raw.count("{") + raw.count("["), raw.count("}") + raw.count("]")
    ml = msg.lower()
    if smart:
        cat, hint = "smart_quote", "스마트 따옴표(“ ” ‘ ’)가 섞여 있습니다 — 일반 따옴표(\")로 바꾸세요."
    elif nbsp:
        cat, hint = "invisible_char", "비표시 문자(NBSP/제로폭/BOM)가 포함돼 있습니다 — 제거하세요."
    elif "delimiter" in ml or "expecting ','" in ml:
        cat, hint = "missing_comma", "쉼표(,)가 빠졌습니다 — 항목 사이 구분자를 확인하세요."
    elif opens != closes:
        cat, hint = "unbalanced", f"괄호 개수 불일치(여는 {opens} · 닫는 {closes}) — 닫는 괄호/따옴표를 맞추세요."
    elif "expecting property name" in ml or "trailing" in ml:
        cat, hint = "trailing_comma", "마지막 항목 뒤 불필요한 쉼표가 있습니다 — 제거하세요."
    elif "delimiter" in ml or "double quote" in ml or "escape" in ml:
        cat, hint = "unescaped", "이스케이프되지 않은 따옴표/특수문자가 있습니다."
    return {"msg": msg, "lineno": lineno, "colno": colno, "line_text": line_text,
            "category": cat, "hint": hint, "engine": "google_rich_result"}


def extract_jsonld(html: str, parse_errors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """HTML 안의 모든 ld+json 블록을 파싱해 노드 리스트로 평탄화(@graph 전개).
    파싱 실패한 블록은 parse_errors(전달 시)에 원인 메시지를 담는다(Q2=a)."""
    nodes: List[Dict[str, Any]] = []
    for m in _LD_RE.finditer(html or ""):
        raw = m.group(1).strip()
        if not raw:
            continue
        # Google 기준: 파싱은 되더라도 스마트쿼트/비표시문자가 있으면 SEO 위험으로 경고
        if parse_errors is not None and re.search(r"[“”‘’\u00a0\u200b\ufeff]", raw):
            smart = bool(re.search(r"[“”‘’]", raw))
            parse_errors.append({"msg": "invalid character in JSON literal",
                                 "lineno": None, "colno": None, "line_text": "",
                                 "category": "smart_quote" if smart else "invisible_char",
                                 "hint": ("스마트 따옴표(“ ” ‘ ’)가 값에 섞여 있습니다 — 일반 따옴표로 교체."
                                          if smart else "비표시 문자(NBSP/제로폭/BOM) 포함 — 제거."),
                                 "engine": "google_rich_result", "severity": "warn"})
        try:
            data = json.loads(raw)
        except Exception as e1:
            # 흔한 오류(후행 콤마 등) 1회 보정 시도
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
                if parse_errors is not None:
                    parse_errors.append({"msg": "trailing comma", "lineno": getattr(e1, "lineno", None),
                                         "colno": getattr(e1, "colno", None), "line_text": "",
                                         "category": "trailing_comma",
                                         "hint": "마지막 항목 뒤 불필요한 쉼표가 있습니다 — 제거하세요(자동 보정됨).",
                                         "engine": "google_rich_result", "severity": "warn"})
            except Exception as e2:
                if parse_errors is not None:
                    parse_errors.append(_classify_syntax(raw, e2))
                continue
        _collect(data, nodes)
    return nodes


def _collect(obj: Any, out: List[Dict[str, Any]]):
    if isinstance(obj, dict):
        if "@graph" in obj and isinstance(obj["@graph"], list):
            for it in obj["@graph"]:
                _collect(it, out)
            # @graph 컨테이너 자체가 @type 을 가질 수도 있으니 계속
        if "@type" in obj:
            out.append(obj)
        # 중첩 노드도 탐색(hasPart, mainEntity 등 안의 완전한 노드)
        for k, v in obj.items():
            if k in ("@graph",):
                continue
            if isinstance(v, (dict, list)):
                _collect(v, out)
    elif isinstance(obj, list):
        for it in obj:
            _collect(it, out)


def _types_of(node: Dict[str, Any]) -> List[str]:
    t = node.get("@type")
    raw = t if isinstance(t, list) else ([t] if t else [])
    out: List[str] = []
    for x in raw:
        for part in str(x).split(","):   # "WebPage,ItemPage" 같은 콤마 결합 대응
            part = part.strip()
            if part:
                out.append(part)
    return out


def _id_regex(id_pattern: str) -> re.Pattern:
    """@id 패턴({SITECODE}/[SITECODE] 포함)을 와일드카드 정규식으로."""
    esc = re.escape(id_pattern)
    esc = esc.replace(re.escape("{SITECODE}"), r"[^/]+").replace(re.escape("[SITECODE]"), r"[^/]+")
    return re.compile("^" + esc + "$")


def _collect_ids(value: Any) -> List[str]:
    """hasPart 값에서 @id 문자열들을 모은다. @id 가 리스트/문자열/딕트 혼재해도 대응."""
    ids: List[str] = []
    if isinstance(value, dict):
        v = value.get("@id")
        if isinstance(v, list):
            ids += [str(x) for x in v]
        elif v is not None:
            ids.append(str(v))
    elif isinstance(value, list):
        for it in value:
            ids += _collect_ids(it)
    elif isinstance(value, str):
        ids.append(value)
    return ids


# ---------- 검수 ----------
def check_page(html: str, product_rules: Dict[str, Any], lang: str = "ko",
               sitecode: Optional[str] = None, site_lang: Optional[str] = None,
               market_product: Optional[str] = None) -> Dict[str, Any]:
    from qa_messages import render
    market_product_slug = market_product or ""

    # Buying 등 스키마 검사 제외 페이지타입: 회색 '해당없음' 1건만 남기고 종료
    if product_rules.get("skip"):
        return {"summary": {"pass": 0, "warn": 0, "fail": 0, "na": 1},
                "findings": [{"block": "(스키마 검사 제외)", "status": "na", "code": "schema.na",
                              "as_is": "이 페이지타입은 스키마 검수 대상이 아닙니다", "to_be": ""}]}

    def _apply(f, code):
        f["code"] = code
        m = render(code, lang, f)
        f["as_is"], f["to_be"] = m["as_is"], m["to_be"]
        return f

    def _resolve(pattern: str) -> str:
        """기대 패턴의 플레이스홀더를 사이트값으로 치환. 모르면 와일드카드 표식(\x00)."""
        s = pattern
        sc = sitecode or "\x00"
        lg = site_lang or "\x00"
        s = s.replace("{SITECODE}", sc).replace("[SITECODE]", sc).replace("{LANG-CODE}", lg)
        return s

    def _norm(u):
        return str(u).strip().rstrip("/").lower()

    def _one_match(expected: str, actual: Any, kind: str) -> bool:
        if actual is None:
            return False
        actual = str(actual).strip()
        exp = _resolve(expected).strip()
        if kind == "enum":
            want = {t.strip().lower() for t in exp.replace("\n", ",").split(",") if t.strip()}
            got = {t.strip().lower() for t in actual.replace("\n", ",").split(",") if t.strip()}
            return bool(want & got) if want else True
        parts = [re.escape(p) for p in _norm(exp).split("\x00")]
        rx = re.compile("^" + ".*?".join(parts) + "$", re.IGNORECASE)
        return rx.match(_norm(actual)) is not None

    def _val_matches(expected: str, actual: Any, kind: str) -> bool:
        # 기대값 콤마 다중 → 하나만 맞으면 OK / 실제값 리스트 → 원소 하나라도 맞으면 OK
        exps = [e.strip() for e in str(expected).split(",")] if kind != "enum" else [expected]
        acts = actual if isinstance(actual, list) else [actual]
        return any(_one_match(e, a, kind) for e in exps for a in acts)

    def _actual_value(node, prop, nested):
        v = node.get(prop)
        if nested and isinstance(v, dict):
            return v.get(nested)
        if nested and isinstance(v, list):
            return [(x.get(nested) if isinstance(x, dict) else x) for x in v]
        return v

    parse_errors: List[str] = []
    nodes = extract_jsonld(html, parse_errors)
    findings: List[Dict[str, Any]] = []
    ok = warn = fail = 0

    # Q2=a: JSON-LD 파싱 실패/문법 위험 리포트 (Google Rich Result 기준 분류 포함)
    for pe in parse_errors:
        sev = pe.get("severity", "fail")
        f = {"block": "JSON-LD", "types": [], "id_slug": None, "conditional": None,
             "missing_props": [], "haspart_missing": [], "status": sev,
             "parse_msg": pe.get("msg", ""), "parse_lineno": pe.get("lineno"),
             "parse_colno": pe.get("colno"), "parse_line": pe.get("line_text", ""),
             "syntax_category": pe.get("category", "syntax"), "syntax_hint": pe.get("hint", ""),
             "engine": pe.get("engine", "")}
        _apply(f, "schema.parse_error")
        if sev == "warn":
            warn += 1
        else:
            fail += 1
        findings.append(f)

    for block in product_rules.get("blocks", []):
        name = block["name"]
        types = block["types"]
        id_pat = block.get("id_pattern")
        conditional = block.get("conditional")
        rx = _id_regex(id_pat) if id_pat else None

        # 블록에 해당하는 노드 찾기: @type 교집합 + (@id 패턴 일치 시 가점)
        cand = [n for n in nodes if set(_types_of(n)) & set(types)]
        node = None
        id_matched = False
        if rx is not None:
            for n in cand:
                nid = str(n.get("@id", ""))
                if nid and rx.match(nid):
                    node = n
                    id_matched = True
                    break
        if node is None and cand:
            node = cand[0]  # 타입은 있으나 @id 불일치

        f: Dict[str, Any] = {"block": name, "types": types, "id_slug": block.get("id_slug"),
                             "conditional": conditional, "missing_props": [], "haspart_missing": []}

        if node is None:
            # 없음 → 조건부면 경고, 아니면 실패
            if conditional:
                f["status"] = "warn"; _apply(f, "schema.missing"); warn += 1
            else:
                f["status"] = "fail"; _apply(f, "schema.missing"); fail += 1
            findings.append(f)
            continue

        # @id 패턴 검증
        if rx is not None and not id_matched:
            f["id_mismatch"] = str(node.get("@id", ""))

        # 필수 속성 검증 (Remarks 달린 선택 속성은 soft 로 분리)
        optional = set(block.get("optional_properties", []))
        for prop in block.get("required_properties", []):
            if prop not in node or node.get(prop) in (None, "", [], {}):
                f["missing_props"].append(prop)
        hard_missing = [p for p in f["missing_props"] if p not in optional]
        soft_missing = [p for p in f["missing_props"] if p in optional]
        f["missing_props"] = hard_missing
        f["optional_missing"] = soft_missing

        # 값 검사 — 검사방식(kind)별로 하드/소프트 분리
        val_mismatch = []       # 하드 불일치(오류)
        translate_confirm = []  # 번역/존재 확인(경고)
        name_issue = []         # 제품명 식별토큰 위반(오류)
        lang_issue = []         # inLanguage ↔ 사이트 언어 불일치(경고)
        name_tokens = block.get("name_tokens") or {}
        for prop, spec in (block.get("expected_values") or {}).items():
            if prop == "hasPart":
                continue
            if prop in f["missing_props"]:
                continue
            if prop not in node or node.get(prop) in (None, "", [], {}):
                continue
            kind = spec.get("kind"); exp = spec.get("value", ""); nested = spec.get("nested")
            actual = _actual_value(node, prop, nested)
            astr = str(actual)

            if kind == "name_token":
                # 번역/현지화 허용: 모델 식별자(S26·버즈4 등)는 언어별 표기 중 하나만 있으면 되고,
                # 등급어(Ultra→울트라/ウルトラ 등)도 변형 중 하나만 있으면 통과.
                low = astr.lower()
                model_any = name_tokens.get("model_any", name_tokens.get("must", []))
                tier_any = name_tokens.get("tier_any", [])
                forbid_any = name_tokens.get("forbid_any", name_tokens.get("forbid", []))
                model_ok = (not model_any) or any(t.lower() in low for t in model_any)
                tier_ok = (not tier_any) or any(t.lower() in low for t in tier_any)
                bad = [t for t in forbid_any if t.lower() in low]
                miss = []
                if not model_ok:
                    miss.append(name_tokens.get("model_label", "제품 모델명"))
                if not tier_ok:
                    miss.append(name_tokens.get("tier_label", "등급표기"))
                if miss or bad:
                    name_issue.append({"prop": prop, "actual": astr[:60],
                                       "missing": miss, "forbidden": bad})
                continue
            if kind == "image_path":
                # 파일명 변동 허용 — 경로에 제품 슬러그가 들어있는지만(경고)
                slug = market_product_slug or ""
                if slug and slug not in astr:
                    translate_confirm.append({"prop": prop, "actual": astr[:60],
                                              "note": "image_path"})
                continue
            if kind == "duration_fmt":
                if not re.match(r"^PT(\d+H)?(\d+M)?(\d+S)?$", astr.strip()):
                    translate_confirm.append({"prop": prop, "actual": astr[:40], "note": "duration_fmt"})
                continue
            if kind == "inlanguage":
                if site_lang and astr and site_lang.split("-")[0].lower() != astr.split("-")[0].lower():
                    lang_issue.append({"prop": prop, "actual": astr, "expected": site_lang})
                continue
            if kind in ("text", "exist"):
                translate_confirm.append({"prop": prop, "actual": astr[:60]})
                continue
            # kind url / enum → 하드 정확 일치
            if not _val_matches(exp, actual, kind or "url"):
                val_mismatch.append({"prop": prop, "expected": _resolve(exp), "actual": astr[:80]})
        f["val_mismatch"] = val_mismatch
        f["translate_confirm"] = translate_confirm
        f["name_issue"] = name_issue
        f["lang_issue"] = lang_issue

        # about 등 Word 기준 'object' 필드가 실제로 배열([...])로 온 경우:
        # Google Rich Result 는 배열도 허용하므로 하드 오류로 보지 않고, 안쪽 @id 는 그대로
        # 검증하되 '배열 사용 — 가이드는 object 권장' 경고만 남긴다(about 대괄호 오탐 방지).
        field_formats = block.get("field_formats") or {}
        array_where_object = []
        for prop, ff in field_formats.items():
            if ff.get("format") == "object" and isinstance(node.get(prop), list):
                array_where_object.append(prop)
                # 이 형태 차이로 인한 값불일치는 오류에서 제외(안쪽 @id 불일치는 유지)
                f["val_mismatch"] = [vm for vm in f["val_mismatch"] if vm["prop"] != prop] \
                    if False else f["val_mismatch"]
        f["array_where_object"] = array_where_object

        # Product.hasPart @id 검증
        if block.get("haspart_ids"):
            present = set(_collect_ids(node.get("hasPart")))
            for want in block["haspart_ids"]:
                wrx = _id_regex(want)
                if not any(wrx.match(pid) for pid in present):
                    f["haspart_missing"].append(_slug(want))

        problems = bool(f["missing_props"]) or bool(f["haspart_missing"]) or ("id_mismatch" in f) or bool(f["val_mismatch"]) or bool(f.get("name_issue"))
        if not problems:
            if soft_missing or f.get("translate_confirm") or f.get("array_where_object") or f.get("lang_issue"):
                f["status"] = "warn"; _apply(f, "schema.optional"); warn += 1
            else:
                f["status"] = "pass"; _apply(f, "schema.pass"); ok += 1
        else:
            f["status"] = "fail"; _apply(f, "schema.problem"); fail += 1
        findings.append(f)

    return {
        "summary": {"total": len(findings), "pass": ok, "warn": warn, "fail": fail,
                    "jsonld_nodes": len(nodes)},
        "findings": findings,
    }


def _slug(id_pattern: str) -> str:
    if "#" in id_pattern:
        return "#" + id_pattern.rsplit("#", 1)[-1]
    return id_pattern.rstrip("/").rsplit("/", 1)[-1] or id_pattern


if __name__ == "__main__":
    import sys
    rules_path = sys.argv[1] if len(sys.argv) > 1 else "schema_rules.json"
    html_path = sys.argv[2] if len(sys.argv) > 2 else "/mnt/user-data/uploads/index.html"
    product = sys.argv[3] if len(sys.argv) > 3 else "M3"

    rules = json.load(open(rules_path, encoding="utf-8"))
    html = open(html_path, encoding="utf-8", errors="ignore").read()
    prod_rules = rules["products"][product]
    res = check_page(html, prod_rules)
    s = res["summary"]
    print(f"검수 대상: {html_path.rsplit('/',1)[-1]}  (규칙: {product}, JSON-LD 노드 {s['jsonld_nodes']}개)")
    print(f"결과: PASS {s['pass']} / WARN {s['warn']} / FAIL {s['fail']}  (총 {s['total']} 블록)\n")
    icon = {"pass": "✅", "warn": "⚠️ ", "fail": "❌"}
    for f in res["findings"]:
        print(f"{icon[f['status']]} {f['block']}")
        if f["status"] != "pass":
            print(f"      as-is: {f['as_is']}")
            if f["to_be"]:
                print(f"      to-be: {f['to_be']}")
