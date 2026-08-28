import { type FormEvent, useCallback, useEffect, useState } from "react";
import { ServiceApiError, loadServiceSnapshot, serviceApi } from "./api";
import { ServiceEmpty, ServiceError, ServiceLoading, ServiceTable, StatusChip } from "./components";
import type { Finding, Investigation, ProductRole, ServiceSnapshot } from "./types";

type ServicePage = "home" | "cities" | "data" | "analysis" | "measures" | "review" | "evidence";

const NAVIGATION: Array<{ id: ServicePage; label: string; description: string }> = [
  { id: "home", label: "Home", description: "担当と都市状況" },
  { id: "cities", label: "Cities", description: "都市ワークスペース" },
  { id: "data", label: "Data", description: "登録・品質・年度" },
  { id: "analysis", label: "Analysis", description: "Findingと分析" },
  { id: "measures", label: "Measures", description: "Scenario比較" },
  { id: "review", label: "Review", description: "調査・現地・判断" },
  { id: "evidence", label: "Evidence", description: "根拠とReport" }
];

const ROLE_LABELS: Record<ProductRole, string> = {
  viewer: "閲覧者",
  analyst: "分析担当",
  planner: "企画・計画担当",
  field_staff: "現地確認担当",
  data_manager: "データ管理担当",
  administrator: "管理者"
};

function initialPage(): ServicePage {
  if (typeof window === "undefined") return "home";
  const value = new URLSearchParams(window.location.search).get("servicePage") as ServicePage | null;
  return NAVIGATION.some((item) => item.id === value) ? value! : "home";
}

function formatDate(value: unknown): string {
  if (!value) return "—";
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.valueOf()) ? String(value) : new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function permits(roles: ProductRole[], allowed: ProductRole[]): boolean {
  return roles.includes("administrator") || roles.some((role) => allowed.includes(role));
}

function updateUrl(page: ServicePage, cityKey?: string) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set("servicePage", page);
  if (cityKey) url.searchParams.set("city", cityKey);
  window.history.replaceState({}, "", url);
}

export function ServiceApp({ initialSnapshot }: { initialSnapshot?: ServiceSnapshot }) {
  const [snapshot, setSnapshot] = useState<ServiceSnapshot | null>(initialSnapshot ?? null);
  const [page, setPageState] = useState<ServicePage>(initialPage);
  const [selectedCity, setSelectedCity] = useState<string>(() => typeof window === "undefined" ? initialSnapshot?.cityHome?.city.city_key ?? "" : new URLSearchParams(window.location.search).get("city") ?? initialSnapshot?.cityHome?.city.city_key ?? "");
  const [loading, setLoading] = useState(!initialSnapshot);
  const [error, setError] = useState<{ message: string; requestId?: string | null } | null>(null);
  const [reload, setReload] = useState(0);
  const [findingFilter, setFindingFilter] = useState("open");
  const [findingFormOpen, setFindingFormOpen] = useState(false);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<Record<string, unknown> | null>(null);
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    if (initialSnapshot) return;
    let cancelled = false;
    setLoading(true); setError(null);
    loadServiceSnapshot().then((result) => {
      if (cancelled) return;
      setSnapshot(result);
      const requested = new URLSearchParams(window.location.search).get("city");
      const city = result.cities.find((item) => item.city_key === requested)?.city_key ?? result.cityHome?.city.city_key ?? "";
      setSelectedCity(city);
      setLoading(false);
    }).catch((reason: unknown) => {
      if (cancelled) return;
      const apiError = reason instanceof ServiceApiError ? reason : null;
      setError({ message: reason instanceof Error ? reason.message : "不明な読み込みエラー", requestId: apiError?.requestId });
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [initialSnapshot, reload]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const setPage = useCallback((next: ServicePage) => {
    setPageState(next); updateUrl(next, selectedCity);
  }, [selectedCity]);

  const refreshCity = useCallback(async (cityKey = selectedCity) => {
    if (!snapshot || !cityKey) return;
    const data = await serviceApi.loadCity(cityKey);
    setSnapshot((current) => current ? { ...current, ...data } : current);
    setMutationMessage("最新状態へ更新しました");
  }, [selectedCity, snapshot]);

  const changeCity = useCallback(async (cityKey: string) => {
    setSelectedCity(cityKey); updateUrl(page, cityKey); setLoading(true); setError(null);
    try { await refreshCity(cityKey); }
    catch (reason) {
      const apiError = reason instanceof ServiceApiError ? reason : null;
      setError({ message: reason instanceof Error ? reason.message : "都市を切り替えられませんでした", requestId: apiError?.requestId });
    } finally { setLoading(false); }
  }, [page, refreshCity]);

  const openCase = useCallback(async (id: string) => {
    setCaseId(id); setCaseDetail(null);
    try { setCaseDetail(await serviceApi.request<Record<string, unknown>>(`/api/v1/investigations/${id}`)); }
    catch (reason) { setMutationMessage(reason instanceof Error ? reason.message : "調査を読み込めませんでした"); }
  }, []);

  const mutate = useCallback(async (path: string, method: "POST" | "PATCH", body: unknown, success: string) => {
    setMutationMessage(null);
    try {
      await serviceApi.request(path, { method, body: JSON.stringify(body) });
      setMutationMessage(success);
      await refreshCity();
      if (caseId) await openCase(caseId);
      return true;
    } catch (reason) {
      const apiError = reason instanceof ServiceApiError ? reason : null;
      setMutationMessage(`${reason instanceof Error ? reason.message : "操作に失敗しました"}${apiError?.requestId ? `（Request ID: ${apiError.requestId}）` : ""}`);
      return false;
    }
  }, [caseId, openCase, refreshCity]);

  const search = useCallback(async (event: FormEvent) => {
    event.preventDefault(); if (!searchQuery.trim()) return;
    try {
      const city = selectedCity ? `&city=${encodeURIComponent(selectedCity)}` : "";
      const result = await serviceApi.request<{ items: Array<Record<string, unknown>> }>(`/api/v1/search?q=${encodeURIComponent(searchQuery.trim())}${city}`);
      setSearchResults(result.items);
    } catch (reason) { setMutationMessage(reason instanceof Error ? reason.message : "検索できませんでした"); }
  }, [searchQuery, selectedCity]);

  if (loading && !snapshot) return <ServiceLoading />;
  if (error && !snapshot) return <ServiceError message={error.message} requestId={error.requestId} onRetry={() => setReload((value) => value + 1)} />;
  if (!snapshot) return null;

  const roles = snapshot.profile.roles;
  const visibleFindings = snapshot.findings.filter((finding) => findingFilter === "all" || (findingFilter === "open" ? !["resolved", "dismissed", "archived"].includes(finding.status) : finding.status === findingFilter));
  const primaryRole = roles[0] ?? "viewer";

  return <div className="municipal-service" data-page={page}>
    <aside className="service-sidebar">
      <a className="service-brand" href="?servicePage=home" onClick={(event) => { event.preventDefault(); setPage("home"); }}><strong>CITY GAP</strong><span>Municipal Urban Intelligence</span></a>
      <div className="service-organization"><span>ORGANIZATION</span><strong>{snapshot.profile.organization.name}</strong><small>{snapshot.profile.organization.organization_key}</small></div>
      <nav aria-label="サービスナビゲーション">{NAVIGATION.map((item) => <button type="button" key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}><span>{item.label}</span><small>{item.description}</small></button>)}</nav>
      <footer><span className="human-boundary">人がレビューし、人が判断を記録</span><small>分析結果は候補であり行政判断ではありません</small></footer>
    </aside>
    <section className="service-shell">
      <header className="service-topbar">
        <label><span>CITY WORKSPACE</span><select value={selectedCity} onChange={(event) => void changeCity(event.target.value)}><option value="">都市を選択</option>{snapshot.cities.map((item) => <option key={item.city_id} value={item.city_key}>{item.name}</option>)}</select></label>
        <button className="service-search-trigger" type="button" onClick={() => setSearchOpen(true)}>検索 <kbd>⌘K</kbd></button>
        <div className="service-user"><span>{snapshot.profile.user?.display_name ?? snapshot.profile.actor}</span><small>{roles.map((role) => ROLE_LABELS[role]).join(" / ")}</small></div>
      </header>
      {mutationMessage && <div className="service-toast" role="status">{mutationMessage}<button type="button" onClick={() => setMutationMessage(null)}>閉じる</button></div>}
      {error && <div className="service-banner" role="alert">{error.message}<button type="button" onClick={() => setError(null)}>閉じる</button></div>}
      <main className="service-content">
        {page === "home" && <HomePage snapshot={snapshot} primaryRole={primaryRole} onNavigate={setPage} />}
        {page === "cities" && <CitiesPage snapshot={snapshot} onCity={(cityKey) => void changeCity(cityKey)} />}
        {page === "data" && <DataPage snapshot={snapshot} roles={roles} mutate={mutate} />}
        {page === "analysis" && <AnalysisPage snapshot={snapshot} roles={roles} findings={visibleFindings} filter={findingFilter} onFilter={setFindingFilter} formOpen={findingFormOpen} onFormOpen={setFindingFormOpen} mutate={mutate} />}
        {page === "measures" && <MeasuresPage snapshot={snapshot} />}
        {page === "review" && <ReviewPage snapshot={snapshot} roles={roles} selectedId={caseId} detail={caseDetail} onSelect={(id) => void openCase(id)} mutate={mutate} />}
        {page === "evidence" && <EvidencePage snapshot={snapshot} />}
      </main>
    </section>
    {searchOpen && <div className="service-search-backdrop" onMouseDown={() => setSearchOpen(false)}><section className="service-global-search" onMouseDown={(event) => event.stopPropagation()}><form onSubmit={(event) => void search(event)}><span>⌕</span><input autoFocus value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="都市、Finding、Investigation、Scenario、IDを検索" /><button type="button" onClick={() => setSearchOpen(false)}>閉じる</button></form><div>{searchResults.length === 0 ? <ServiceEmpty title="検索語を入力してください" detail="技術IDは検索できますが、通常画面では必要な場合だけ表示します。" /> : searchResults.map((result) => <button key={String(result.entity_id)} type="button" onClick={() => { if (result.entity_type === "investigation") { setPage("review"); void openCase(String(result.entity_id)); } setSearchOpen(false); }}><span>{String(result.entity_type)}</span><strong>{String(result.title)}</strong><small>{String(result.subtitle ?? "")}</small></button>)}</div></section></div>}
  </div>;
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="service-page-header"><div><span>{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}

function HomePage({ snapshot, primaryRole, onNavigate }: { snapshot: ServiceSnapshot; primaryRole: ProductRole; onNavigate(page: ServicePage): void }) {
  const summary = snapshot.cityHome?.summary;
  const roleLead: Record<ProductRole, string> = {
    viewer: "都市の更新状況とレビュー済み記録を確認できます。",
    analyst: "未整理のFindingから調査を開始し、再現可能な分析を実行します。",
    planner: "レビュー待ちの調査を確認し、人の判断をDecision Recordへ記録します。",
    field_staff: "割り当てられた現地確認をオフライン対応の記録へ残します。",
    data_manager: "データの品質検証、受入、分析可能化、昇格を管理します。",
    administrator: "テナント、利用者、ジョブ、データ更新とサービス状態を管理します。"
  };
  if (!snapshot.cityHome) return <><PageHeader eyebrow="SERVICE HOME" title="自治体サービスを開始" description={roleLead[primaryRole]} /><ServiceEmpty title="都市がまだ登録されていません" detail="管理者がOrganizationへCityを登録すると、City Homeとデータオンボーディングが利用できます。" /></>;
  return <><PageHeader eyebrow={`${ROLE_LABELS[primaryRole]} HOME`} title={`${snapshot.cityHome.city.name}の業務状況`} description={roleLead[primaryRole]} /><div className="service-kpis"><button type="button" onClick={() => onNavigate("analysis")}><span>OPEN FINDINGS</span><strong>{summary?.open_findings ?? 0}</strong><small>追加調査候補</small></button><button type="button" onClick={() => onNavigate("review")}><span>INVESTIGATIONS</span><strong>{summary?.active_investigations ?? 0}</strong><small>進行中の調査</small></button><button type="button" onClick={() => onNavigate("review")}><span>REVIEWS</span><strong>{summary?.pending_reviews ?? 0}</strong><small>レビュー待ち</small></button><button type="button" onClick={() => onNavigate("review")}><span>FIELD CHECKS</span><strong>{summary?.pending_field_checks ?? 0}</strong><small>現地確認待ち</small></button></div><div className="service-home-grid"><section className="service-panel"><header><div><span>MY WORK</span><h2>担当と通知</h2></div><b>{snapshot.workQueue.assignments.length + snapshot.workQueue.notifications.filter((item) => !item.read_at).length}</b></header>{snapshot.workQueue.unregistered_identity ? <ServiceEmpty title="このIdentityの担当情報は未登録です" detail="開発用Identityでは架空の担当者を作成しません。管理者が実利用者をOrganizationへ登録してください。" /> : snapshot.workQueue.assignments.length === 0 ? <ServiceEmpty title="現在の担当はありません" detail="新しい割当が作成されると、ここへ表示されます。" /> : snapshot.workQueue.assignments.map((item) => <article className="work-item" key={item.id}><StatusChip value={item.status} /><strong>{item.assignment_type.replaceAll("_", " ")}</strong><small>期限 {item.due_date ?? "未設定"}</small></article>)}</section><section className="service-panel"><header><div><span>RECENT ACTIVITY</span><h2>最近の業務履歴</h2></div></header>{snapshot.cityHome.recent_activity.length === 0 ? <ServiceEmpty title="Activityはまだありません" detail="データ更新、調査、レビュー、現地確認、Decision Recordを人が操作した履歴だけを表示します。" /> : snapshot.cityHome.recent_activity.map((item) => <article className="activity-item" key={`${item.resource_type}-${item.resource_id}-${item.occurred_at}`}><i /><div><strong>{item.summary}</strong><small>{item.actor_label} · {formatDate(item.occurred_at)}</small></div></article>)}</section></div></>;
}

function CitiesPage({ snapshot, onCity }: { snapshot: ServiceSnapshot; onCity(city: string): void }) {
  return <><PageHeader eyebrow="CITIES" title="都市ワークスペース" description="Organization内の都市、利用可能な機能、進行中の業務を確認します。" /><ServiceTable caption="都市一覧" empty="登録された都市がありません" rows={snapshot.cities as unknown as Array<Record<string, unknown>>} rowKey={(row) => String(row.city_id)} onRow={(row) => onCity(String(row.city_key))} columns={[{ key: "name", label: "都市" }, { key: "service_status", label: "状態", render: (row) => <StatusChip value={String(row.service_status)} /> }, { key: "available_capabilities", label: "機能", render: (row) => `${Number(row.available_capabilities ?? 0)} / ${Number(row.capability_count ?? 0)}` }, { key: "open_findings", label: "Finding" }, { key: "active_investigations", label: "Investigation" }, { key: "latest_activity_at", label: "最終更新", render: (row) => formatDate(row.latest_activity_at) }]} /></>;
}

function DataPage({ snapshot, roles, mutate }: { snapshot: ServiceSnapshot; roles: ProductRole[]; mutate: (path: string, method: "POST" | "PATCH", body: unknown, success: string) => Promise<boolean> }) {
  const hub = snapshot.dataHub;
  if (!hub) return <><PageHeader eyebrow="DATA HUB" title="データオンボーディング" description="登録、検証、受入、取込、分析可能化、昇格を明示的に管理します。" /><ServiceEmpty title="都市を選択してください" detail="データはアップロードだけで分析対象へ昇格しません。" /></>;
  const canManage = permits(roles, ["data_manager"]);
  const nextStatus: Record<string, string> = { registered: "validating", validating: "validated", validated: "accepted", accepted: "ingesting", ingesting: "analysis_ready", analysis_ready: "promoted", rejected: "validating", failed: "validating" };
  return <><PageHeader eyebrow="DATA HUB" title={`${hub.city.name}のデータ`} description="年度、出典、品質、Capability、PLATEAU収録モデルを一つのライフサイクルで管理します。" /><section className="service-panel full"><header><div><span>DATASET VERSIONS</span><h2>データとバージョン</h2></div></header><ServiceTable caption="データセットバージョン" empty="データセットが登録されていません" rows={hub.datasets as unknown as Array<Record<string, unknown>>} rowKey={(row) => String(row.version_id ?? row.dataset_id)} columns={[{ key: "title", label: "データ" }, { key: "dataset_year", label: "年度" }, { key: "version_key", label: "Version" }, { key: "service_status", label: "Service状態", render: (row) => <StatusChip value={String(row.service_status)} /> }, { key: "quality_status", label: "品質", render: (row) => <StatusChip value={String(row.quality_status)} /> }, { key: "data_classification", label: "分類" }, { key: "action", label: "次の操作", render: (row) => canManage && nextStatus[String(row.service_status)] ? <button className="table-action" type="button" onClick={(event) => { event.stopPropagation(); const proposed = nextStatus[String(row.service_status)]; void mutate(`/api/v1/dataset-versions/${String(row.version_id)}/status`, "PATCH", { expected_status: row.service_status, proposed_status: proposed, note: "Data Hubで人がライフサイクルを確認" }, `${proposed}へ更新しました`); }}>{nextStatus[String(row.service_status)]}</button> : <span>—</span> }]} /></section><div className="service-two-column"><section className="service-panel"><header><div><span>QUALITY</span><h2>品質チェック</h2></div></header>{hub.quality_checks.length === 0 ? <ServiceEmpty title="品質チェックは未登録です" detail="geometry、CRS、属性、件数、欠損、コード、年度整合、公開制約を記録します。" /> : hub.quality_checks.map((check) => <article className="quality-row" key={`${check.dataset_version_id}-${check.check_key}-${check.checked_at}`}><StatusChip value={check.status} /><div><strong>{check.check_key.replaceAll("_", " ")}</strong><small>{check.explanation}</small></div></article>)}</section><section className="service-panel"><header><div><span>PLATEAU MODEL</span><h2>収録モデル</h2></div></header>{hub.plateau_model.length === 0 ? <ServiceEmpty title="PLATEAU Model Inventoryはありません" detail="実際に取込済みのCityGML objectのみを表示します。" /> : hub.plateau_model.map((model) => <article className="quality-row" key={`${model.plateau_dataset_version_id}-${model.theme}`}><StatusChip value={`${model.feature_count}`} /><div><strong>{model.theme}</strong><small>LOD {model.available_lods.join(", ") || "—"} · geometry {model.geometry_count}</small></div></article>)}</section></div></>;
}

function AnalysisPage({ snapshot, roles, findings, filter, onFilter, formOpen, onFormOpen, mutate }: { snapshot: ServiceSnapshot; roles: ProductRole[]; findings: Finding[]; filter: string; onFilter(value: string): void; formOpen: boolean; onFormOpen(value: boolean): void; mutate: (path: string, method: "POST" | "PATCH", body: unknown, success: string) => Promise<boolean> }) {
  const canWrite = permits(roles, ["analyst", "planner"]); const city = snapshot.cityHome?.city.city_key;
  const submitFinding = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!city) return; const data = new FormData(event.currentTarget); void mutate(`/api/v1/cities/${encodeURIComponent(city)}/findings`, "POST", { finding_type: data.get("finding_type"), title: data.get("title"), summary: data.get("summary"), urban_state_id: data.get("urban_state_id") || null }, "Findingを登録しました"); onFormOpen(false); };
  const startInvestigation = async (finding: Finding) => {
    if (!city || !finding.urban_state_id) return;
    if (finding.status === "new") {
      const triaged = await mutate(`/api/v1/findings/${finding.id}/status`, "PATCH", { expected_status: "new", proposed_status: "triaged" }, "Findingをtriageしました");
      if (!triaged) return;
    }
    await mutate(`/api/v1/cities/${encodeURIComponent(city)}/investigations`, "POST", { urban_state_id: finding.urban_state_id, title: `調査: ${finding.title}`, objective: finding.summary, finding_ids: [finding.id], spatial_state: {} }, "Investigationを開始しました");
  };
  return <><PageHeader eyebrow="ANALYSIS" title="Finding Queueと分析カタログ" description="Findingは追加調査候補です。深刻度や政策優先順位、問題認定を自動付与しません。" action={canWrite ? <button className="primary-action" type="button" onClick={() => onFormOpen(!formOpen)}>Findingを登録</button> : undefined} />{formOpen && <form className="service-form" onSubmit={submitFinding}><label>種類<select name="finding_type" required><option value="accessibility_gap">Accessibility Gap</option><option value="network_criticality">Network Criticality</option><option value="planning_context">Planning Context</option><option value="temporal_change">Temporal Change</option><option value="resilience_impact">Resilience Impact</option><option value="data_quality_issue">Data Quality Issue</option></select></label><label>タイトル<input name="title" required maxLength={500} /></label><label className="wide">説明<textarea name="summary" required maxLength={5000} /></label><label>Urban State ID<input name="urban_state_id" inputMode="text" placeholder="実在するUUID（任意）" /></label><button className="primary-action" type="submit">候補として登録</button></form>}<div className="service-tabs" role="tablist"><button type="button" className={filter === "open" ? "active" : ""} onClick={() => onFilter("open")}>Open</button>{["new", "triaged", "investigating", "review_required", "resolved", "dismissed", "all"].map((status) => <button type="button" key={status} className={filter === status ? "active" : ""} onClick={() => onFilter(status)}>{status.replaceAll("_", " ")}</button>)}</div><ServiceTable caption="Finding Queue" empty="該当するFindingはありません" rows={findings as unknown as Array<Record<string, unknown>>} rowKey={(row) => String(row.id)} columns={[{ key: "title", label: "Finding" }, { key: "finding_type", label: "種類", render: (row) => String(row.finding_type).replaceAll("_", " ") }, { key: "status", label: "状態", render: (row) => <StatusChip value={String(row.status)} /> }, { key: "validation_status", label: "検証", render: (row) => <StatusChip value={String(row.validation_status)} /> }, { key: "created_at", label: "登録", render: (row) => formatDate(row.created_at) }, { key: "action", label: "次の操作", render: (row) => { const finding = row as unknown as Finding; return canWrite && ["new", "triaged"].includes(finding.status) ? <button className="table-action" type="button" disabled={!finding.urban_state_id} title={finding.urban_state_id ? "人の操作で調査を開始" : "Urban Stateが必要です"} onClick={() => void startInvestigation(finding)}>Investigation開始</button> : <span>—</span>; }}]} /><section className="service-panel full catalog"><header><div><span>ANALYSIS CATALOG</span><h2>再現可能な分析定義</h2></div></header><div className="catalog-grid">{snapshot.analyses.map((analysis) => <article key={`${analysis.id}-${analysis.version}`}><div><StatusChip value={`v${analysis.version}`} /><small>{analysis.required_capabilities.join(" · ")}</small></div><h3>{analysis.name}</h3><p>{analysis.purpose}</p><footer><strong>断定しない範囲</strong><span>{analysis.claim_boundary}</span></footer></article>)}</div></section></>;
}

function MeasuresPage({ snapshot }: { snapshot: ServiceSnapshot }) {
  return <><PageHeader eyebrow="MEASURES" title="Scenario Library" description="複数案を同じUrban Stateと明示した仮定で比較します。最良案や採用案を自動決定しません。" /><ServiceTable caption="Scenario Library" empty="この都市にはScenarioがありません" rows={snapshot.scenarios as unknown as Array<Record<string, unknown>>} rowKey={(row) => String(row.id)} columns={[{ key: "title", label: "Scenario" }, { key: "objective_mode", label: "比較軸" }, { key: "site_count", label: "地点数" }, { key: "lifecycle_status", label: "状態", render: (row) => <StatusChip value={String(row.lifecycle_status)} /> }, { key: "review_status", label: "Review", render: (row) => <StatusChip value={String(row.review_status)} /> }, { key: "generated_at", label: "生成", render: (row) => formatDate(row.generated_at) }]} /><div className="service-boundary-note"><strong>比較の境界</strong><p>費用は自治体が登録したversion付き外部データだけを利用します。災害Stress Testは明示した利用不可仮定の比較であり、災害予測ではありません。</p></div></>;
}

function ReviewPage({ snapshot, roles, selectedId, detail, onSelect, mutate }: { snapshot: ServiceSnapshot; roles: ProductRole[]; selectedId: string | null; detail: Record<string, unknown> | null; onSelect(id: string): void; mutate: (path: string, method: "POST" | "PATCH", body: unknown, success: string) => Promise<boolean> }) {
  const canReview = permits(roles, ["planner"]); const canField = permits(roles, ["field_staff", "planner"]); const investigation = detail?.investigation as Investigation | undefined; const reviews = (detail?.reviews ?? []) as Array<Record<string, unknown>>;
  const fieldSubmit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!selectedId) return; const data = new FormData(event.currentTarget); void mutate(`/api/v1/investigations/${selectedId}/field-observations`, "POST", { observation_type: data.get("observation_type"), notes: data.get("notes"), observed_at: new Date().toISOString() }, "現地観察を記録しました"); };
  const decisionSubmit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!selectedId) return; const data = new FormData(event.currentTarget); void mutate(`/api/v1/investigations/${selectedId}/decisions`, "POST", { review_request_id: data.get("review_request_id"), decision: data.get("decision"), reason: data.get("reason"), related_evidence_ids: String(data.get("evidence_ids") ?? "").split(",").map((item) => item.trim()).filter(Boolean) }, "Decision Recordを人の操作で記録しました"); };
  return <><PageHeader eyebrow="REVIEW" title="Investigation Case Workflow" description="Findingから調査、Scenario、Review、Field、Decisionへ一つのCaseとして引き継ぎます。" /><div className="case-layout"><section className="service-panel case-list"><header><div><span>INVESTIGATIONS</span><h2>調査一覧</h2></div></header>{snapshot.investigations.length === 0 ? <ServiceEmpty title="Investigationはありません" detail="AnalystがFindingをtriageして調査を開始すると表示されます。" /> : snapshot.investigations.map((item) => <button type="button" key={item.id} className={selectedId === item.id ? "active" : ""} onClick={() => onSelect(item.id)}><div><strong>{item.title}</strong><small>{item.objective}</small></div><StatusChip value={item.status} /></button>)}</section><section className="service-panel case-detail"><header><div><span>CASE DETAIL</span><h2>{investigation?.title ?? "調査を選択"}</h2></div></header>{!selectedId ? <ServiceEmpty title="Investigationを選択してください" detail="技術IDではなく、調査タイトルと業務状態を中心に表示します。" /> : !detail ? <div className="inline-loading">Caseを読み込んでいます</div> : <div className="case-workflow"><ol><li className="done">Finding</li><li className={investigation?.status !== "open" ? "done" : "current"}>Investigation</li><li className={reviews.length ? "done" : ""}>Review</li><li className={((detail.field_observations ?? []) as unknown[]).length ? "done" : ""}>Field</li><li className={((detail.decisions ?? []) as unknown[]).length ? "done" : ""}>Decision</li></ol><p>{investigation?.objective}</p><div className="case-actions">{canReview && investigation?.status !== "closed" && <button type="button" onClick={() => void mutate(`/api/v1/investigations/${selectedId}/reviews`, "POST", { request_note: "Case画面からレビューを依頼" }, "レビューを依頼しました")}>Reviewを依頼</button>}{canReview && reviews.map((review) => review.status === "requested" ? <button key={String(review.id)} type="button" onClick={() => void mutate(`/api/v1/reviews/${String(review.id)}/status`, "PATCH", { expected_status: "requested", proposed_status: "in_review", review_note: "" }, "レビューを開始しました")}>Review開始</button> : review.status === "in_review" ? <button key={String(review.id)} type="button" onClick={() => void mutate(`/api/v1/reviews/${String(review.id)}/status`, "PATCH", { expected_status: "in_review", proposed_status: "reviewed", review_note: "根拠と限界を確認" }, "レビュー済みとして記録しました")}>Review完了</button> : null)}</div>{canField && <form className="case-form" onSubmit={fieldSubmit}><h3>現地観察</h3><label>観察種別<input name="observation_type" required defaultValue="access_check" /></label><label>記録<textarea name="notes" required /></label><button type="submit">現地記録を追加</button></form>}{canReview && investigation?.status === "decision_pending" && <form className="case-form decision" onSubmit={decisionSubmit}><h3>Decision Record</h3><label>Review<select name="review_request_id" required>{reviews.filter((review) => review.status === "reviewed").map((review) => <option key={String(review.id)} value={String(review.id)}>Reviewed · {formatDate(review.reviewed_at)}</option>)}</select></label><label>判断<select name="decision"><option value="adopted">adopted</option><option value="on_hold">on hold</option><option value="rejected">rejected</option><option value="additional_investigation">additional investigation</option></select></label><label>理由<textarea name="reason" required /></label><label>Evidence ID（カンマ区切り）<input name="evidence_ids" required /></label><button type="submit">人の判断として記録</button></form>}</div>}</section></div></>;
}

function EvidencePage({ snapshot }: { snapshot: ServiceSnapshot }) {
  const datasets = snapshot.cityHome?.datasets ?? [];
  return <><PageHeader eyebrow="EVIDENCE CENTER" title="根拠・検証・Report" description="出典、version、アルゴリズム、検証、現地記録、Decision Recordを再現可能なmanifestへまとめます。" /><div className="service-evidence-grid"><section className="service-panel"><header><div><span>SOURCE LINEAGE</span><h2>現在参照するデータ</h2></div></header>{datasets.length === 0 ? <ServiceEmpty title="根拠対象データがありません" detail="Data Hubでpromotedになった実データだけがEvidenceの入力になります。" /> : datasets.map((dataset) => <article className="evidence-source" key={dataset.version_id}><StatusChip value={dataset.data_classification} /><div><strong>{dataset.title} · {dataset.dataset_year}</strong><small>{dataset.dataset_key} / {dataset.version_key} · {dataset.quality_status}</small></div></article>)}</section><section className="service-panel"><header><div><span>EXPORT BOUNDARY</span><h2>公開と内部の分離</h2></div></header><div className="evidence-policy"><strong>Internal</strong><p>担当者、コメント、現地添付、内部Decision、restrictedデータを含められます。</p><strong>Public</strong><p>public分類の集計・出典・検証済み成果だけを含み、個人情報・内部注記を除外します。</p></div></section></div><div className="service-boundary-note"><strong>決定論的Report</strong><p>Reportは保存済みのversion付き入力とmanifestから再生成し、artifact SHA-256を記録します。画面表示の都合で数値や出典を作りません。</p></div></>;
}
