"use client";

import { useState } from "react";
import {
  MetricTab, MetricView, SiteKey, Change, Report,
  METRICS, orderedSiteKeys, siteName, siteClass, levelKo, levelClass,
  shortUrl, bucketOf, actionForChange, pageRoleFromUrl, pageRoleKo, pageRoleFromText,
} from "./shared";
import {
  firstNarrativeLine, siteMetricSummary, compactSummary, siteMatchesQuery,
} from "./sectionCommon";

export function WatchPointPanel({ changes, dcv, metricTab, expectedSites = [] }: { changes: Change[]; dcv?: Report["dcv"]; metricTab: MetricView; expectedSites?: SiteKey[] }) {
  const scopedMetrics = metricTab === "all" ? (["data", "copy", "visual"] as MetricTab[]) : [metricTab];
  const allSites = orderedSiteKeys([
    ...expectedSites,
    ...scopedMetrics.flatMap((m) => Object.keys(dcv?.[m] || {})),
    ...changes.map((c) => c.site || ""),
  ]);
  const changedSites = new Set(changes.map((c) => c.site).filter(Boolean));
  const topChanges = changes.slice(0, 5);
  const collectedSites = allSites.filter((site) => scopedMetrics.some((m) => !!dcv?.[m]?.[site]));
  const pendingSites = allSites.filter((site) => !scopedMetrics.some((m) => !!dcv?.[m]?.[site]));
  const headline = changes.length > 0
    ? `${changes.length}건 변경 감지`
    : "변경 없음 · 기준선 확인";
  const primaryAction = changes.length
    ? compactSummary(actionForChange(changes[0]), 120)
    : "변경은 없지만 PF/PDP/Buying의 카피·CTA·Schema·alt.copy가 다음 수집에서 달라지는지 확인";
  return (
    <div className="card watchPointCard overviewBoard">
      <div className="overviewBoardHead">
        <div>
          <p className="summaryEyebrow">Overview</p>
          <h2>{headline}</h2>
          <p>
            {changes.length > 0
              ? "사이트별 변화와 삼성 관점 액션을 먼저 보여줍니다. 아래 카드는 ‘무엇이 바뀌었나 → 왜 봐야 하나’를 한눈에 읽는 용도입니다."
              : "이번 수집에서는 변경점이 없습니다. 대신 수집된 사이트의 현재 구조를 다음 주 비교 기준선으로 정리합니다."}
          </p>
        </div>
        <div className="overviewHeroStats">
          <b>{allSites.length || 0}</b><span>관리 Site</span>
          <b>{collectedSites.length}</b><span>근거 있음</span>
          <b>{pendingSites.length}</b><span>근거 부족</span>
        </div>
      </div>

      <div className="overviewHeroGrid">
        <div className="overviewHeroBox primary">
          <span>핵심 상태</span>
          <strong>{headline}</strong>
          <p>{changes.length ? `상위 변경: ${compactSummary(topChanges[0]?.summary || topChanges[0]?.field || "변경 세부 확인 필요", 120)}` : "새 변경은 없고, 현재 DATA/COPY/VISUAL 기준선을 유지합니다."}</p>
        </div>
        <div className="overviewHeroBox">
          <span>수집 커버리지</span>
          <strong>{collectedSites.length}/{allSites.length || 0} sites</strong>
          <p>{pendingSites.length ? `근거 부족: ${pendingSites.slice(0, 4).map(siteName).join(", ")}${pendingSites.length > 4 ? " 외" : ""}` : "관리 대상 Site 모두 근거가 있습니다."}</p>
        </div>
        <div className="overviewHeroBox action">
          <span>삼성 액션</span>
          <strong>예의주시</strong>
          <p>{primaryAction}</p>
        </div>
      </div>

      {topChanges.length > 0 && (
        <div className="overviewChangeList prominent">
          {topChanges.map((c) => (
            <div key={c.id} className="overviewChangeItem">
              <span className={`badge ${siteClass(c.site)}`}>{siteName(c.site)}</span>
              <span className={`sevBadge ${levelClass(c.level)}`}>{levelKo(c.level)}</span>
              <p>{c.summary || c.field}<small>{shortUrl(c.url)} · 삼성 액션: {actionForChange(c)}</small></p>
            </div>
          ))}
        </div>
      )}
      <div className="overviewSiteGrid">
        {allSites.length === 0 ? <p className="muted">수집 데이터가 쌓이면 사이트별 Overview가 표시됩니다.</p> : allSites.map((site) => {
          const siteChanges = changes.filter((c) => c.site === site);
          const hasAnyBlock = scopedMetrics.some((m) => !!dcv?.[m]?.[site]);
          const summary = scopedMetrics.map((m) => ({
            metric: m,
            text: siteMetricSummary(site, m, dcv?.[m]?.[site], siteChanges.filter((c) => bucketOf(c) === m)),
          }));
          return (
            <div key={site} className={`overviewSiteCard ${siteChanges.length ? "hasChange" : hasAnyBlock ? "hasBaseline" : "isPending"}`}>
              <div className="overviewSiteHead">
                <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                <span className={siteChanges.length ? "changeState changed" : hasAnyBlock ? "changeState stable" : "changeState pending"}>
                  {siteChanges.length ? `변경 ${siteChanges.length}건` : hasAnyBlock ? "기준선 있음" : "근거 부족"}
                </span>
              </div>
              <p className="overviewSiteTakeaway">
                {siteChanges.length
                  ? `바뀐 점: ${compactSummary(siteChanges[0].summary || siteChanges[0].field || "변경 확인 필요", 100)}`
                  : hasAnyBlock
                  ? "변경 없음. 현재 구조를 다음 수집의 비교 기준으로 사용합니다."
                  : "아직 수집 근거가 없어 전략 판단 전 크롤 성공 여부부터 봐야 합니다."}
              </p>
              <div className="overviewMetricRows">
                {summary.map((x) => (
                  <div key={x.metric}>
                    <b>{METRICS[x.metric].label}</b>
                    <span>{compactSummary(x.text, 150)}</span>
                  </div>
                ))}
              </div>
              <p className="overviewAction">
                {siteChanges.length
                  ? `삼성 체크: ${compactSummary(actionForChange(siteChanges[0]), 120)}`
                  : hasAnyBlock
                  ? "삼성 체크: 다음 수집에서 CTA 위치, hero copy, Product/FAQ schema, alt.copy 변화 여부를 비교하세요."
                  : "삼성 체크: 수집 실패/차단/JS 렌더링 여부 확인 후 인사이트에 포함하세요."}
              </p>
            </div>
          );
        })}
      </div>
      {changedSites.size === 0 && (
        <p className="overviewFootnote">변경이 없을 때의 핵심은 ‘좋다/나쁘다’ 판단이 아니라 baseline 확보입니다. 다음 수집에서 각 사이트의 PF/PDP/Buying 구조, CTA, 스키마, alt.copy가 어떻게 이탈하는지 비교합니다.</p>
      )}
    </div>
  );
}

export function InsightChat({ dcv, changes, expectedSites = [] }: { dcv?: Report["dcv"]; changes: Change[]; expectedSites?: SiteKey[] }) {
  const presets = [
    "이번 주 변경된 페이지는?",
    "삼성은 뭘 예의주시해야 해?",
    "Apple PDP에서 copy 의미있는 차이는?",
    "Xiaomi tablet PDP에서 image 인사이트는?",
    "스키마에서 의미 있는 차이는?",
    "PF/PDP/Buying 중 어디가 약해?",
  ];
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState("preset을 누르거나, ‘Apple PDP copy’, ‘Xiaomi tablet image’처럼 사이트·페이지·지표를 넣어 물어보세요.");

  const answerFor = (query: string) => {
    const raw = query.trim().toLowerCase();
    if (!raw) return;
    const metricExplicit: MetricTab | undefined = /schema|data|html|h-?tag|스키마|데이터/.test(raw)
      ? "data" : /visual|image|alt|비주얼|이미지/.test(raw)
      ? "visual" : /copy|카피|문구|tone|faq|cta/.test(raw)
      ? "copy" : undefined;
    const metric: MetricTab = metricExplicit || "copy";
    const role = pageRoleFromText(raw);
    const allMetricSites = orderedSiteKeys([...expectedSites, ...Object.keys(dcv?.[metric] || {}), ...changes.map((c) => c.site || "")]);
    const site = allMetricSites.find((s) => siteMatchesQuery(s, raw));
    const filteredChanges = changes.filter((c) => {
      if (bucketOf(c) !== metric) return false;
      if (site && c.site !== site) return false;
      if (role && pageRoleFromUrl(c.url) !== role) return false;
      return true;
    });

    if (/이번|변경|바뀐|changed|change/.test(raw) && !/의미|insight|인사이트/.test(raw)) {
      if (filteredChanges.length) {
        setAnswer(filteredChanges.slice(0, 5).map((c) => `- ${siteName(c.site)} ${pageRoleKo(pageRoleFromUrl(c.url))} ${METRICS[bucketOf(c)].label}: ${c.summary || c.field} (${shortUrl(c.url)})`).join("\n"));
        return;
      }
      setAnswer("조건에 맞는 변경점은 없습니다. 변경이 없는 사이트는 현재 상태를 baseline으로 두고, 다음 수집에서 Schema/CTA/카피/alt.copy가 달라지는지 확인하면 됩니다.");
      return;
    }

    if (/삼성|samsung|예의주시|watch|action/.test(raw)) {
      if (changes.length) {
        setAnswer(changes.slice(0, 5).map((c) => `- ${siteName(c.site)} ${levelKo(c.level)}: ${c.summary || c.field}\n  → 삼성 액션: ${actionForChange(c)}`).join("\n"));
        return;
      }
      setAnswer("이번 수집에서는 변경점이 없습니다. 예의주시 포인트는 ① 경쟁사의 Product/FAQ schema 변화 ② PF/PDP/Buying CTA 위치 변화 ③ hero copy의 톤 변화 ④ alt.copy 보강 여부입니다.");
      return;
    }

    if (/pf|pdp|buying|구매|약해/.test(raw)) {
      const blocks = dcv?.copy || {};
      const lines = orderedSiteKeys([...expectedSites, ...Object.keys(blocks)]).map((s) => {
        const block = blocks[s];
        const f: any = block?.facts || {};
        if (!block) return `- ${siteName(s)}: 아직 COPY 근거가 없습니다. 관리 URL은 있으므로 수집 성공 후 PF/PDP/Buying별로 판단할 수 있습니다.`;
        const roles = f.page_inventory?.by_page_role || {};
        const roleText = Object.entries(roles).map(([k, v]) => `${pageRoleKo(k)} ${v}p`).join(", ") || "역할 정보 없음";
        const line = firstNarrativeLine(block);
        return `- ${siteName(s)}: 수집 기준 ${roleText}. ${compactSummary(line, 160)}`;
      });
      setAnswer(lines.length ? lines.join("\n") : "PF/PDP/Buying 역할별 COPY 근거가 아직 부족합니다.");
      return;
    }

    const targetSites = site ? [site] : allMetricSites;
    const answers = targetSites.slice(0, 5).map((s) => {
      const block = dcv?.[metric]?.[s];
      const siteChanges = changes.filter((c) => bucketOf(c) === metric && c.site === s && (!role || pageRoleFromUrl(c.url) === role));
      const roleText = role ? `${pageRoleKo(role)} ` : "";
      if (siteChanges.length) {
        return `- ${siteName(s)} ${roleText}${METRICS[metric].label} 변경: ${siteChanges.slice(0, 2).map((c) => `${c.summary || c.field} (${shortUrl(c.url)})`).join(" / ")}`;
      }
      if (!block) return `- ${siteName(s)} ${roleText}${METRICS[metric].label}: 현재 리포트에 근거가 없습니다. 수집 실패/차단/JS 렌더링 여부를 확인해야 합니다.`;
      return `- ${siteName(s)} ${roleText}${METRICS[metric].label}: 변경점 없음. 현재 근거: ${compactSummary(firstNarrativeLine(block), 180)}`;
    });
    setAnswer(answers.length ? answers.join("\n") : "현재 리포트에서 해당 사이트/페이지/지표 조합에 대한 근거가 없습니다.");
  };

  return (
    <div className={`floatingChat ${open ? "open" : ""}`}>
      {!open && <button className="chatToggle" onClick={() => setOpen(true)}>Q&A</button>}
      {open && (
        <div className="chatPanel">
          <div className="chatPanelHead">
            <b>간단 Q&A</b>
            <button onClick={() => setOpen(false)} title="닫기">×</button>
          </div>
          <div className="presetGrid">
            {presets.map((p) => <button key={p} onClick={() => { setQ(p); answerFor(p); }}>{p}</button>)}
          </div>
          <div className="chatInputRow">
            <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") answerFor(q); }} placeholder="예: OPPO PDP copy 차이는?" />
            <button onClick={() => answerFor(q)}>질문</button>
          </div>
          <pre>{answer}</pre>
          <p className="muted">현재 수집된 facts/changes 안에서만 rule-based로 답합니다.</p>
        </div>
      )}
    </div>
  );
}
