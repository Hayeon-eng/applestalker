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
def extract_jsonld(html: str) -> List[Dict[str, Any]]:
    """HTML 안의 모든 ld+json 블록을 파싱해 노드 리스트로 평탄화(@graph 전개)."""
    nodes: List[Dict[str, Any]] = []
    for m in _LD_RE.finditer(html or ""):
        raw = m.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            # 흔한 오류(후행 콤마 등) 1회 보정 시도
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
            except Exception:
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
def check_page(html: str, product_rules: Dict[str, Any], lang: str = "ko") -> Dict[str, Any]:
    from qa_messages import render

    def _apply(f, code):
        f["code"] = code
        m = render(code, lang, f)
        f["as_is"], f["to_be"] = m["as_is"], m["to_be"]
        return f

    nodes = extract_jsonld(html)
    findings: List[Dict[str, Any]] = []
    ok = warn = fail = 0

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

        # Product.hasPart @id 검증
        if block.get("haspart_ids"):
            present = set(_collect_ids(node.get("hasPart")))
            for want in block["haspart_ids"]:
                wrx = _id_regex(want)
                if not any(wrx.match(pid) for pid in present):
                    f["haspart_missing"].append(_slug(want))

        problems = bool(f["missing_props"]) or bool(f["haspart_missing"]) or ("id_mismatch" in f)
        if not problems:
            if soft_missing:
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
