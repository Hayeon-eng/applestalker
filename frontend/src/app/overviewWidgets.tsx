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
  return (
    <div className="card watchPointCard">
      <p className="cardTitle">Overview</p>
      <p className="overviewLead">
        {changes.length > 0
          ? `이번 수집에서 ${changes.length}건의 변경이 잡혔습니다. 아래는 사이트별로 무엇이 바뀌었고, 삼성 입장에서 왜 봐야 하는지 정리한 요약입니다.`
          : "이번 수집에서는 변경점이 없습니다. 대신 현재 각 사이트가 어떤 구조·카피·비주얼 전략을 쓰는지 기준선을 요약합니다."}
      </p>
      {topChanges.length > 0 && (
        <div className="overviewChangeList">
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
          const summary = scopedMetrics.map((m) => siteMetricSummary(site, m, dcv?.[m]?.[site], siteChanges.filter((c) => bucketOf(c) === m)));
          return (
            <div key={site} className="overviewSiteCard">
              <div className="overviewSiteHead">
                <span className={`badge ${siteClass(site)}`}>{siteName(site)}</span>
                <span className={siteChanges.length ? "changeState changed" : hasAnyBlock ? "changeState stable" : "changeState pending"}>
                  {siteChanges.length ? `변경 ${siteChanges.length}건` : hasAnyBlock ? "변경 없음" : "근거 부족"}
                </span>
              </div>
              <ul>
                {summary.map((x, i) => <li key={i}>{compactSummary(x, 230)}</li>)}
              </ul>
              <p className="overviewAction">
                {siteChanges.length
                  ? `예의주시: ${compactSummary(actionForChange(siteChanges[0]), 120)}`
                  : hasAnyBlock
                  ? "예의주시: 변경은 없지만 현재 구조가 기준선입니다. 다음 수집에서 카피/CTA/Schema/alt.copy가 이탈하는지 확인하세요."
                  : "예의주시: 아직 비교 근거가 없으므로 먼저 수집 성공 여부를 확인해야 합니다. 이 상태에서는 경쟁사 전략을 단정하지 않습니다."}
              </p>
            </div>
          );
        })}
      </div>
      {changedSites.size === 0 && (
        <p className="overviewFootnote">변경이 없을 때도 이 Overview는 무의미하지 않습니다. 각 사이트의 현재 Schema 적용률, 카피 구체성, alt/src 기반 visual tactic이 다음 주 변화 감지의 baseline으로 쓰입니다.</p>
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
