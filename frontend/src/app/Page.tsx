function Page() {
  const [tab, setTab] = useState<"changes" | "compare">("changes");
  const [dataTab, setDataTab] = useState<"data" | "copy" | "visual">("data");
  const [report, setReport] = useState<Report | null>(null);
  const [runs, setRuns] = useState<Session[]>([]);
  const [sel, setSel] = useState<Change | null>(null);
  const [selPage, setSelPage] = useState<PageDetail | null>(null);
  const [pagesBySite, setPagesBySite] = useState<{ samsung: PageLite[]; apple: PageLite[] }>({
    samsung: [],
    apple: [],
  });
  const [crawling, setCrawling] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number; url: string } | null>(
    null,
  );
  const [showUrl, setShowUrl] = useState(false);
  const [showUrlList, setShowUrlList] = useState(false);
  const [allUrls, setAllUrls] = useState<{ url: string; tier_level?: number }[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);
  const [exampleMode, setExampleMode] = useState<"off" | "changes" | "nochange">("off");
  const [compare, setCompare] = useState<any>(null);
  const [legendOpen, setLegendOpen] = useState(false); // 요구사항 7: 기본 접힘
  const [emailSending, setEmailSending] = useState(false);
  const sse = useRef<EventSource | null>(null);

  const load = useCallback(async () => {
    try {
      const h = await fetch(`${API}/api/health`);
      if (!h.ok) throw 0;
      setOnline(true);
      try {
        const r = await fetch(`${API}/api/latest-report`);
        const j = await r.json();
        setReport(r.ok && j.has_data ? j : null);
      } catch {
        setReport(null);
      }
      try {
        const rr = await fetch(`${API}/api/runs`);
        setRuns((await rr.json()).sessions || []);
      } catch {
        setRuns([]);
      }
    } catch {
      setOnline(false);
      setReport(null);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (tab !== "compare") return;
    if (exampleMode === "nochange") return;
    (async () => {
      try {
        const r = await fetch(`${API}/api/compare`);
        setCompare(await r.json());
      } catch {
        setCompare({ status: "insufficient_data" });
      }
      try {
        const [rs, ra] = await Promise.all([
          fetch(`${API}/api/pages?site=samsung`)
            .then((r) => r.json())
            .catch(() => ({ pages: [] })),
          fetch(`${API}/api/pages?site=apple`)
            .then((r) => r.json())
            .catch(() => ({ pages: [] })),
        ]);
        setPagesBySite({ samsung: rs.pages || [], apple: ra.pages || [] });
      } catch {}
    })();
  }, [tab, exampleMode]);

  const loadUrlList = async () => {
    try {
      const r = await fetch(`${API}/api/urls`);
      const j = await r.json();
      setAllUrls(j.urls || []);
    } catch {}
  };
  useEffect(() => {
    if (showUrlList) loadUrlList();
  }, [showUrlList]);

  const startCrawl = async () => {
    if (!online) return;
    try {
      await fetch(`${API}/trigger-crawl/all`, { method: "POST" });
      setCrawling(true);
      setProgress({ done: 0, total: 45, url: "" });
      sse.current?.close();
      const es = new EventSource(`${API}/api/crawl-progress`);
      sse.current = es;
      let done = 0,
        total = 45;
      es.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          if (ev.type === "start") {
            total = ev.total || 45;
            setProgress({ done: 0, total, url: "" });
          } else if (ev.type === "page_done") {
            done++;
            setProgress({ done, total, url: ev.url || "" });
          } else if (ev.type === "status" && !ev.crawling) {
            es.close();
            setCrawling(false);
            setProgress(null);
            load();
          }
        } catch {}
      };
      es.onerror = () => {
        es.close();
        setCrawling(false);
        setProgress(null);
      };
    } catch {
      setCrawling(false);
    }
  };

  const loadSession = async (runId: string) => {
    if (!online) return;
    setExampleMode("off");
    setSel(null);
    setSelPage(null);
    try {
      const r = await fetch(`${API}/api/latest-report?run_id=${encodeURIComponent(runId)}`);
      const j = await r.json();
      setReport(j.has_data ? j : null);
    } catch {}
  };
  const delSession = async (ids: string[]) => {
    if (!online) {
      alert("백엔드 연결 후 삭제할 수 있습니다.");
      return;
    }
    setRuns((prev) => prev.filter((s) => !s.run_ids.some((r) => ids.includes(r))));
    let failed = false;
    for (const id of ids) {
      try {
        const r = await fetch(`${API}/api/runs/${id}`, { method: "DELETE" });
        if (!r.ok) failed = true;
      } catch {
        failed = true;
      }
    }
    if (failed) alert("일부 기록 삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    load();
  };

  /* 요구사항 5: URL 추가/삭제는 관리자 비밀번호(0108) 필요 */
  const addUrl = async () => {
    const el = document.getElementById("nu") as HTMLInputElement;
    const u = el?.value.trim();
    if (!u) return;
    const pw = window.prompt("관리자 비밀번호를 입력하세요");
    if (pw === null) return;
    const r = await fetch(`${API}/api/urls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: u, admin_password: pw }),
    });
    if (!r.ok) {
      alert("추가 실패: 비밀번호를 확인하세요.");
      return;
    }
    el.value = "";
    setShowUrl(false);
    if (showUrlList) loadUrlList();
  };
  const deleteUrl = async (u: string) => {
    const pw = window.prompt(`"${u}" 를 삭제합니다. 관리자 비밀번호를 입력하세요`);
    if (pw === null) return;
    const r = await fetch(
      `${API}/api/urls?url=${encodeURIComponent(u)}&admin_password=${encodeURIComponent(pw)}`,
      { method: "DELETE" },
    );
    if (!r.ok) {
      alert("삭제 실패: 비밀번호를 확인하세요.");
      return;
    }
    loadUrlList();
  };

  /* 요구사항 1: 현행 분석(현황 비교) 탭에서 페이지 클릭 시 DATA/COPY/VISUAL 상세 */
  const openPageDetail = async (url: string) => {
    setSel(null);
    try {
      const r = await fetch(`${API}/api/page-detail?url=${encodeURIComponent(url)}`);
      const j = await r.json();
      if (r.ok) setSelPage(j);
      else setSelPage(null);
    } catch {
      setSelPage(null);
    }
  };
  const openChangeDetail = (c: Change) => {
    setSelPage(null);
    setSel(c);
  };

  /* 요구사항 9: 이메일 발송 테스트 */
  const sendTestEmail = async () => {
    setEmailSending(true);
    try {
      const r = await fetch(`${API}/api/email/test`, { method: "POST" });
      const j = await r.json();
      alert(
        r.ok
          ? `메일 발송 완료 → ${j.recipient || ""}`
          : `발송 실패: ${j.detail || j.error || j.reason || "알 수 없는 오류"}`,
      );
    } catch {
      alert("발송 요청 실패 (네트워크 확인)");
    }
    setEmailSending(false);
  };

  const downloadCapture = async () => {
    const ensure = () =>
      new Promise<any>((res, rej) => {
        if ((window as any).html2canvas) return res((window as any).html2canvas);
        const sc = document.createElement("script");
        sc.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
        sc.onload = () => res((window as any).html2canvas);
        sc.onerror = () => rej(new Error("html2canvas load fail"));
        document.body.appendChild(sc);
      });
    try {
      const h2c = await ensure();
      const el = document.getElementById("capture-area") || document.body;
      const canvas = await h2c(el, { backgroundColor: "#F2F2F7", scale: 2, useCORS: true });
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = `apple-stalker_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, "")}.png`;
      a.click();
    } catch {
      alert("캡처에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    }
  };

  const changesData = exampleMode === "changes" ? CHANGES_EXAMPLE : report;
  const compareData = exampleMode === "nochange" ? COMPARE_EXAMPLE : compare;
  const isExample = exampleMode !== "off";
  const allChanges = changesData?.changes || [];
  const changes = allChanges.filter((c) => (BUCKET_OF[c.category] || "data") === dataTab);
  const byCat = changesData?.by_category || {};
  const appleN = changes.filter((c) => c.site === "apple").length;
  const samsungN = changes.filter((c) => c.site === "samsung").length;
  const highN = allChanges.filter((c) => c.level === "High").length;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "232px 1fr 360px",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      {/* 좌측 */}
      <aside
        style={{
          background: "var(--rail)",
          borderRight: "1px solid var(--line)",
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "20px 18px 8px" }}>
          <div
            style={{ fontSize: 19, fontWeight: 700, cursor: "pointer", userSelect: "none" }}
            title="처음 화면으로"
            onClick={() => {
              setExampleMode("off");
              setSel(null);
              setSelPage(null);
              setTab("changes");
              load();
            }}
          >
            <span style={{ marginRight: 6 }}>🍎</span>Apple Stalker
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--sec)", marginTop: 2 }}>
            경쟁사 웹 변화 감지
          </div>
          <ConnBadge online={online} />
        </div>

        {/* 요구사항 7: 중요도 기준 — 기본 접힘 */}
        <div style={{ padding: "12px 14px 4px" }}>
          <div
            onClick={() => setLegendOpen((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
              padding: "6px 4px",
              userSelect: "none",
            }}
          >
            <span style={{ fontSize: 11, color: "var(--sec)", fontWeight: 600 }}>
              중요도 기준{" "}
              <span style={{ fontWeight: 400 }}>· 무엇이 · 얼마나 바뀌었나로 정합니다</span>
            </span>
            <span
              style={{
                fontSize: 11,
                color: "var(--ter)",
                transform: legendOpen ? "rotate(180deg)" : "none",
                transition: "transform .15s",
              }}
            >
              ▾
            </span>
          </div>
          {legendOpen &&
            [
              [
                "High",
                "높음",
                "var(--high)",
                "스키마·페이지 구조(레이아웃) 변화, 여러 섹션 동시 변화 — AI 검색 노출에 직접 영향",
              ],
              [
                "Medium",
                "보통",
                "var(--med)",
                "메뉴·메타 변경, 문장·슬로건 카피 변경, 가격·구매 등 거래 변화",
              ],
              ["Low", "낮음", "var(--low)", "단어 몇 개·오타 등 미세 변화, 작은 이미지 변화"],
            ].map(([k, ko, c, d]) => (
              <div
                key={k as string}
                style={{
                  display: "flex",
                  gap: 9,
                  alignItems: "flex-start",
                  padding: "7px 0",
                  borderBottom: "1px solid var(--line)",
                }}
              >
                <span
                  style={{
                    width: 9,
                    height: 9,
                    borderRadius: 3,
                    background: c as string,
                    marginTop: 4,
                    flex: "0 0 auto",
                  }}
                />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 12 }}>{ko}</div>
                  <div
                    style={{ fontSize: 11, color: "var(--sec)", lineHeight: 1.45, marginTop: 1 }}
                  >
                    {d}
                  </div>
                </div>
              </div>
            ))}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 16px 6px",
          }}
        >
          <span style={{ fontSize: 11, color: "var(--sec)", fontWeight: 600 }}>크롤 이력</span>
          {online && (
            <button onClick={() => setShowUrl((v) => !v)} style={pillBtn}>
              ＋ URL
            </button>
          )}
        </div>
        {showUrl && online && (
          <div style={{ margin: "0 12px 8px", display: "flex", gap: 6 }}>
            <input
              id="nu"
              placeholder="https://…"
              className="mono"
              style={{
                flex: 1,
                border: "1px solid var(--line2)",
                borderRadius: 9,
                padding: "8px 10px",
                fontSize: 11,
              }}
            />
            <button
              onClick={addUrl}
              style={{
                background: "var(--blue)",
                color: "#fff",
                borderRadius: 9,
                padding: "0 12px",
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              추가
            </button>
          </div>
        )}
        <div style={{ padding: "0 10px 10px", flex: 1 }}>
          {!online && <Muted>백엔드 연결 후 표시됩니다</Muted>}
          {online && runs.length === 0 && <Muted>아직 크롤 기록이 없습니다</Muted>}
          {online &&
            runs.map((s) => (
              <div
                key={s.session}
                onClick={() => loadSession(s.run_ids[0])}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "8px 8px",
                  borderRadius: 9,
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(0,0,0,.04)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <div style={{ flex: 1 }}>
                  <div className="mono" style={{ fontSize: 11.5, fontWeight: 600 }}>
                    {s.timestamp}
                  </div>
                  <div style={{ fontSize: 10.5, color: "var(--sec)" }}>
                    {s.sites
                      .map((x) => (x === "apple" ? "애플" : x === "samsung" ? "삼성" : x))
                      .join("+")}{" "}
                    · {s.changes ? `${s.changes} 변화` : "변화 없음"}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    delSession(s.run_ids);
                  }}
                  title="삭제"
                  style={{ color: "var(--ter)", fontSize: 15, padding: "2px 5px" }}
                >
                  ×
                </button>
              </div>
            ))}
        </div>

        {/* 요구사항 5: URL 전체 리스트 (+URL 옆) */}
        <div style={{ padding: "10px 16px 6px", borderTop: "1px solid var(--line)" }}>
          <div
            onClick={() => setShowUrlList((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <span style={{ fontSize: 10.5, color: "var(--sec)", fontWeight: 600 }}>
              모니터링 URL 전체 {allUrls.length > 0 && `(${allUrls.length})`}
            </span>
            <span
              style={{
                fontSize: 11,
                color: "var(--ter)",
                transform: showUrlList ? "rotate(180deg)" : "none",
              }}
            >
              ▾
            </span>
          </div>
          {showUrlList && (
            <div style={{ marginTop: 6, maxHeight: 160, overflow: "auto" }}>
              {allUrls.length === 0 && <Muted>URL이 없습니다</Muted>}
              {allUrls.map((u) => (
                <div
                  key={u.url}
                  style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 2px" }}
                >
                  <span
                    className="mono"
                    style={{
                      flex: 1,
                      fontSize: 10,
                      color: "var(--sec)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={u.url}
                  >
                    {u.url}
                  </span>
                  <button
                    onClick={() => deleteUrl(u.url)}
                    title="삭제(관리자 비번 필요)"
                    style={{ color: "var(--ter)", fontSize: 13, flex: "0 0 auto" }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ padding: "10px 16px 6px", borderTop: "1px solid var(--line)" }}>
          <div style={{ fontSize: 10.5, color: "var(--sec)", fontWeight: 600, marginBottom: 6 }}>
            모니터링 대상
          </div>
          <div style={{ display: "flex", gap: 14 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5 }}>
              <span
                style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--samsung)" }}
              />
              <b>당사</b> Samsung
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5 }}>
              <span
                style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--apple)" }}
              />
              <b>경쟁사</b> Apple
            </span>
          </div>
        </div>

        {/* 요구사항 9: 이메일 발송 테스트 */}
        {online && (
          <div style={{ padding: "10px 16px 6px" }}>
            <button
              onClick={sendTestEmail}
              disabled={emailSending}
              style={{
                width: "100%",
                fontSize: 11,
                fontWeight: 600,
                padding: "8px 0",
                borderRadius: 9,
                background: "rgba(0,0,0,.045)",
                color: "var(--label2)",
              }}
            >
              {emailSending ? "발송 중…" : "📧 이메일 발송 테스트"}
            </button>
          </div>
        )}

        <div style={{ padding: "10px 14px 16px" }}>
          <div style={{ fontSize: 10.5, color: "var(--sec)", fontWeight: 600, marginBottom: 6 }}>
            예시 화면 (참고용)
          </div>
          <div style={{ display: "flex", gap: 5 }}>
            {[
              ["changes", "변화 있음"],
              ["nochange", "변화 없음(현행 분석)"],
            ].map(([k, label]) => (
              <button
                key={k}
                onClick={() => {
                  const next = exampleMode === k ? "off" : (k as "changes" | "nochange");
                  setExampleMode(next);
                  setSel(null);
                  setSelPage(null);
                  if (next === "changes") setTab("changes");
                  else if (next === "nochange") setTab("compare");
                }}
                style={{
                  flex: 1,
                  fontSize: 10.5,
                  fontWeight: 600,
                  padding: "7px 0",
                  borderRadius: 9,
                  color: exampleMode === k ? "#fff" : "var(--label2)",
                  background: exampleMode === k ? "var(--blue)" : "rgba(0,0,0,.045)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 10, color: "var(--ter)", marginTop: 6 }}>
            실제 데이터가 없을 때 참고용 (이전 값은 예시용 가상)
          </div>
        </div>
      </aside>

      {/* 중앙 */}
      <main style={{ overflow: "auto" }}>
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 5,
            background: "rgba(242,242,247,.78)",
            backdropFilter: "saturate(180%) blur(20px)",
            borderBottom: "1px solid var(--line)",
          }}
        >
          <div
            style={{
              padding: "13px 24px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                display: "inline-flex",
                background: "rgba(118,118,128,.12)",
                borderRadius: 11,
                padding: 3,
                gap: 2,
              }}
            >
              <Seg on={tab === "changes"} onClick={() => setTab("changes")}>
                변경점
              </Seg>
              <Seg on={tab === "compare"} onClick={() => setTab("compare")}>
                현황 비교
              </Seg>
            </div>
            <span style={{ flex: 1 }} />
            {(isExample || report) && (
              <button onClick={downloadCapture} style={ghost}>
                화면 캡처
              </button>
            )}
            {online && !isExample && (
              <a href={`${API}/api/export/xlsx`} style={ghost}>
                Excel
              </a>
            )}
            {online && !isExample && (
              <a href={`${API}/api/export/pptx`} style={ghost}>
                PPTX
              </a>
            )}
            <button
              onClick={startCrawl}
              disabled={!online || crawling}
              style={{
                ...ghost,
                background: online && !crawling ? "var(--blue)" : "var(--line2)",
                color: "#fff",
                cursor: online && !crawling ? "pointer" : "default",
              }}
            >
              {crawling ? "크롤 중…" : "크롤 실행"}
            </button>
          </div>

          {/* 요구사항 1.1/2: DATA · COPY · VISUAL 분리 탭 — 변경점/현황비교 양쪽 공통 */}
          <div style={{ padding: "0 24px 10px", display: "flex", gap: 6 }}>
            {DTABS.map((d) => (
              <button
                key={d.key}
                onClick={() => setDataTab(d.key)}
                style={{
                  fontSize: 11.5,
                  fontWeight: 700,
                  padding: "6px 13px",
                  borderRadius: 9,
                  color: dataTab === d.key ? "#fff" : "var(--label2)",
                  background: dataTab === d.key ? "var(--blue)" : "rgba(0,0,0,.045)",
                }}
              >
                {d.icon} {d.label}
              </button>
            ))}
          </div>

          {crawling && progress && (
            <div style={{ padding: "0 24px 12px" }}>
              <div
                style={{
                  height: 6,
                  background: "rgba(118,118,128,.18)",
                  borderRadius: 4,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${Math.round((progress.done / progress.total) * 100)}%`,
                    background: "var(--blue)",
                    transition: "width .3s",
                  }}
                />
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 11,
                  color: "var(--sec)",
                  marginTop: 5,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {progress.done}/{progress.total} 수집 중 · {progress.url || "시작…"}
              </div>
            </div>
          )}
        </div>

        {tab === "compare" ? (
          <Compare
            data={compareData}
            online={online}
            isExample={exampleMode === "nochange"}
            dataTab={dataTab}
            pagesBySite={pagesBySite}
            onPickPage={openPageDetail}
            selPageUrl={selPage?.url}
          />
        ) : !online ? (
          <Empty
            title="백엔드에 연결되지 않았습니다"
            desc="프론트엔드 설정(NEXT_PUBLIC_API_URL)에 백엔드 주소를 넣고 다시 배포하세요. 왼쪽 아래 '예시 화면 보기'로 미리 둘러볼 수 있습니다."
          />
        ) : !changesData ? (
          <Empty
            title="아직 수집된 변화가 없습니다"
            desc="오른쪽 위 [크롤 실행]을 누르면 애플·삼성 페이지를 수집해 변화를 찾아냅니다. (페이지가 많아 몇 분 걸립니다)"
            cta={startCrawl}
          />
        ) : (
          <Changes
            data={changesData}
            changes={changes}
            byCat={byCat}
            appleN={appleN}
            samsungN={samsungN}
            highN={highN}
            sel={sel}
            setSel={openChangeDetail}
            isExample={exampleMode === "changes"}
            dataTab={dataTab}
          />
        )}
      </main>

      {/* 우측 */}
      <aside
        style={{
          background: "var(--rail)",
          borderLeft: "1px solid var(--line)",
          overflow: "auto",
          padding: "16px 14px",
        }}
      >
        {selPage ? (
          <PageDetailPanel d={selPage} />
        ) : sel ? (
          <Detail c={sel} />
        ) : (
          <DetailDefault data={tab === "compare" ? null : changesData} online={online} tab={tab} />
        )}
      </aside>
    </div>
  );
}