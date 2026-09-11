"""
page_doc.py — 큐비 — 페이지 HTML 파싱 1회 공유 [2026-09 · 속도]

배경: 페이지 1건을 검수할 때 copy_checker / html_qa_scoring / seo_checker / spec_extractor 가 각자
BeautifulSoup(html, "lxml") 을 다시 만들었다(4.7MB 렌더 HTML 기준 0.67s × 4 ≈ 2.7s — 페이지당 계산 4.5s 의 60%).
여기서 한 번만 파싱해 공유한다. 공유 soup 은 **읽기 전용** 으로 다룬다(각 모듈은 decompose/extract 를 하지 않고
텍스트 추출 시 script/style/noscript 를 건너뛴다).

캐시는 "직전 1건"만 기억한다(동시성은 페이지 단위 태스크가 각자 다른 html 문자열을 넘기므로 키 충돌 없음).
"""
from __future__ import annotations
import threading
from typing import Optional

from bs4 import BeautifulSoup

_SKIP = ("script", "style", "noscript", "template")
_lock = threading.Lock()
_cache = {"key": None, "soup": None}


def soup_for(html: str) -> BeautifulSoup:
    """같은 html 문자열(동일 객체 또는 동일 내용)에 대해 파싱 결과를 재사용."""
    key = (id(html), len(html or ""), hash(html[:2000]) if html else 0)
    with _lock:
        if _cache["key"] == key and _cache["soup"] is not None:
            return _cache["soup"]
    soup = BeautifulSoup(html or "", "lxml")
    with _lock:
        _cache["key"], _cache["soup"] = key, soup
    return soup


def text_of(el, sep: str = " ") -> str:
    """script/style/noscript 안의 문자열을 제외한 텍스트(공유 soup 을 훼손하지 않기 위한 대체)."""
    parts = []
    for s in el.strings:
        p = s.parent
        if p is not None and p.name in _SKIP:
            continue
        t = str(s).strip()
        if t:
            parts.append(t)
    return sep.join(parts)


def visible_strings(soup: BeautifulSoup, exclude_pred=None):
    """script/style 제외 + exclude_pred(element)->bool 가 True 인 조상을 가진 문자열 제외."""
    for s in soup.find_all(string=True):
        p = s.parent
        if p is None or p.name in _SKIP:
            continue
        if exclude_pred is not None:
            skip = False
            for anc in s.parents:
                if anc is None or anc.name is None:
                    break
                if exclude_pred(anc):
                    skip = True
                    break
            if skip:
                continue
        yield s
