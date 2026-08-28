import {
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  applySyncResponse,
  cacheSelectedFieldPackage,
  queueFieldOperation,
  queuedFieldOperations,
  saveFieldOperation,
  type QueuedFieldOperation,
} from "../lib/fieldOffline";
import { ServiceApiError, loadServiceSnapshot, serviceApi } from "./api";
import { ROLE_HOME_LEAD, ROLE_LABELS, SERVICE_NAVIGATION } from "./copy";
import {
  MunicipalSpatialWorkspace,
  type MunicipalSpatialEntity,
  type MunicipalViewport,
} from "./MunicipalSpatialWorkspace";
import {
  ServiceEmpty,
  ServiceError,
  ServiceLoading,
  ServiceTable,
  StatusChip,
} from "./components";
import type {
  Finding,
  FieldOfflinePackage,
  Investigation,
  ProductRole,
  ServiceSnapshot,
} from "./types";

type ServicePage = (typeof SERVICE_NAVIGATION)[number]["id"];
type DataHubView =
  | "sources"
  | "datasets"
  | "coverage"
  | "quality"
  | "updates"
  | "review"
  | "licenses"
  | "dependencies";

function initialPage(): ServicePage {
  if (typeof window === "undefined") return "home";
  const value = new URLSearchParams(window.location.search).get(
    "servicePage",
  ) as ServicePage | null;
  return SERVICE_NAVIGATION.some((item) => item.id === value) ? value! : "home";
}

function formatDate(value: unknown): string {
  if (!value) return "—";
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.valueOf())
    ? String(value)
    : new Intl.DateTimeFormat("ja-JP", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(parsed);
}

function permits(roles: ProductRole[], allowed: ProductRole[]): boolean {
  return (
    roles.includes("administrator") ||
    roles.some((role) => allowed.includes(role))
  );
}

function updateUrl(page: ServicePage, cityKey?: string) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set("servicePage", page);
  if (cityKey) url.searchParams.set("city", cityKey);
  window.history.replaceState({}, "", url);
}

export function ServiceApp({
  initialSnapshot,
}: {
  initialSnapshot?: ServiceSnapshot;
}) {
  const [snapshot, setSnapshot] = useState<ServiceSnapshot | null>(
    initialSnapshot ?? null,
  );
  const [page, setPageState] = useState<ServicePage>(initialPage);
  const [selectedCity, setSelectedCity] = useState<string>(() =>
    typeof window === "undefined"
      ? (initialSnapshot?.cityHome?.city.city_key ?? "")
      : (new URLSearchParams(window.location.search).get("city") ??
        initialSnapshot?.cityHome?.city.city_key ??
        ""),
  );
  const [loading, setLoading] = useState(!initialSnapshot);
  const [error, setError] = useState<{
    message: string;
    requestId?: string | null;
  } | null>(null);
  const [reload, setReload] = useState(0);
  const [findingFilter, setFindingFilter] = useState("open");
  const [findingFormOpen, setFindingFormOpen] = useState(false);
  const [caseId, setCaseId] = useState<string | null>(() =>
    typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("investigation"),
  );
  const [caseDetail, setCaseDetail] = useState<Record<string, unknown> | null>(
    null,
  );
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<
    Array<Record<string, unknown>>
  >([]);

  useEffect(() => {
    if (initialSnapshot) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    loadServiceSnapshot()
      .then((result) => {
        if (cancelled) return;
        setSnapshot(result);
        const requested = new URLSearchParams(window.location.search).get(
          "city",
        );
        const city =
          result.cities.find((item) => item.city_key === requested)?.city_key ??
          result.cityHome?.city.city_key ??
          "";
        setSelectedCity(city);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        const apiError = reason instanceof ServiceApiError ? reason : null;
        setError({
          message:
            reason instanceof Error ? reason.message : "不明な読み込みエラー",
          requestId: apiError?.requestId,
        });
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [initialSnapshot, reload]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const setPage = useCallback(
    (next: ServicePage) => {
      setPageState(next);
      updateUrl(next, selectedCity);
    },
    [selectedCity],
  );

  const refreshCity = useCallback(
    async (cityKey = selectedCity) => {
      if (!snapshot || !cityKey) return;
      const data = await serviceApi.loadCity(cityKey);
      setSnapshot((current) => (current ? { ...current, ...data } : current));
      setMutationMessage("最新状態へ更新しました");
    },
    [selectedCity, snapshot],
  );

  const changeCity = useCallback(
    async (cityKey: string) => {
      setSelectedCity(cityKey);
      updateUrl(page, cityKey);
      setLoading(true);
      setError(null);
      try {
        await refreshCity(cityKey);
      } catch (reason) {
        const apiError = reason instanceof ServiceApiError ? reason : null;
        setError({
          message:
            reason instanceof Error
              ? reason.message
              : "都市を切り替えられませんでした",
          requestId: apiError?.requestId,
        });
      } finally {
        setLoading(false);
      }
    },
    [page, refreshCity],
  );

  const openCase = useCallback(async (id: string) => {
    setCaseId(id);
    setCaseDetail(null);
    try {
      setCaseDetail(
        await serviceApi.request<Record<string, unknown>>(
          `/api/v1/investigations/${id}`,
        ),
      );
    } catch (reason) {
      setMutationMessage(
        reason instanceof Error ? reason.message : "調査を読み込めませんでした",
      );
    }
  }, []);

  useEffect(() => {
    if (caseId && !caseDetail) void openCase(caseId);
  }, [caseDetail, caseId, openCase]);

  const mutate = useCallback(
    async (
      path: string,
      method: "POST" | "PATCH",
      body: unknown,
      success: string,
    ) => {
      setMutationMessage(null);
      try {
        await serviceApi.request(path, { method, body: JSON.stringify(body) });
        setMutationMessage(success);
        await refreshCity();
        if (caseId) await openCase(caseId);
        return true;
      } catch (reason) {
        const apiError = reason instanceof ServiceApiError ? reason : null;
        setMutationMessage(
          `${reason instanceof Error ? reason.message : "操作に失敗しました"}${apiError?.requestId ? `（Request ID: ${apiError.requestId}）` : ""}`,
        );
        return false;
      }
    },
    [caseId, openCase, refreshCity],
  );

  const createCity = useCallback(async (body: Record<string, unknown>) => {
    setMutationMessage(null);
    try {
      const city = await serviceApi.request<{ city_key: string }>(
        "/api/v1/cities",
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      );
      const updated = await loadServiceSnapshot();
      setSnapshot(updated);
      setSelectedCity(city.city_key);
      updateUrl("data", city.city_key);
      setPageState("data");
      setMutationMessage(
        "都市を登録しました。Data Hubで実データを登録してください",
      );
      return true;
    } catch (reason) {
      const apiError = reason instanceof ServiceApiError ? reason : null;
      setMutationMessage(
        `${reason instanceof Error ? reason.message : "都市を登録できませんでした"}${apiError?.requestId ? `（Request ID: ${apiError.requestId}）` : ""}`,
      );
      return false;
    }
  }, []);

  const search = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      if (!searchQuery.trim()) return;
      try {
        const city = selectedCity
          ? `&city=${encodeURIComponent(selectedCity)}`
          : "";
        const result = await serviceApi.request<{
          items: Array<Record<string, unknown>>;
        }>(`/api/v1/search?q=${encodeURIComponent(searchQuery.trim())}${city}`);
        setSearchResults(result.items);
      } catch (reason) {
        setMutationMessage(
          reason instanceof Error ? reason.message : "検索できませんでした",
        );
      }
    },
    [searchQuery, selectedCity],
  );

  if (loading && !snapshot) return <ServiceLoading />;
  if (error && !snapshot)
    return (
      <ServiceError
        message={error.message}
        requestId={error.requestId}
        onRetry={() => setReload((value) => value + 1)}
      />
    );
  if (!snapshot) return null;

  const roles = snapshot.profile.roles;
  const visibleNavigation = SERVICE_NAVIGATION.filter(
    (item) =>
      item.id !== "operations" ||
      permits(roles, ["data_manager", "administrator"]),
  );
  const visibleFindings = snapshot.findings.filter(
    (finding) =>
      findingFilter === "all" ||
      (findingFilter === "open"
        ? !["resolved", "dismissed", "archived"].includes(finding.status)
        : finding.status === findingFilter),
  );
  const primaryRole = roles[0] ?? "viewer";

  return (
    <div className="municipal-service" data-page={page}>
      <aside className="service-sidebar">
        <a
          className="service-brand"
          href="?servicePage=home"
          onClick={(event) => {
            event.preventDefault();
            setPage("home");
          }}
        >
          <strong>CITY GAP</strong>
          <span>Municipal Urban Intelligence</span>
        </a>
        <div className="service-organization">
          <span>ORGANIZATION</span>
          <strong>{snapshot.profile.organization.name}</strong>
          <small>{snapshot.profile.organization.organization_key}</small>
        </div>
        <nav aria-label="サービスナビゲーション">
          {visibleNavigation.map((item) => (
            <button
              type="button"
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => setPage(item.id)}
            >
              <span>{item.label}</span>
              <small>{item.description}</small>
            </button>
          ))}
        </nav>
        <footer>
          <span className="human-boundary">人がレビューし、人が判断を記録</span>
          <small>分析結果は候補であり行政判断ではありません</small>
        </footer>
      </aside>
      <section className="service-shell">
        <header className="service-topbar">
          <label>
            <span>CITY WORKSPACE</span>
            <select
              value={selectedCity}
              onChange={(event) => void changeCity(event.target.value)}
            >
              <option value="">都市を選択</option>
              {snapshot.cities.map((item) => (
                <option key={item.city_id} value={item.city_key}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="service-search-trigger"
            type="button"
            onClick={() => setSearchOpen(true)}
          >
            検索 <kbd>⌘K</kbd>
          </button>
          <div className="service-user">
            <span>
              {snapshot.profile.user?.display_name ?? snapshot.profile.actor}
            </span>
            <small>{roles.map((role) => ROLE_LABELS[role]).join(" / ")}</small>
          </div>
        </header>
        {mutationMessage && (
          <div className="service-toast" role="status">
            {mutationMessage}
            <button type="button" onClick={() => setMutationMessage(null)}>
              閉じる
            </button>
          </div>
        )}
        {error && (
          <div className="service-banner" role="alert">
            {error.message}
            <button type="button" onClick={() => setError(null)}>
              閉じる
            </button>
          </div>
        )}
        <main className="service-content">
          {page === "home" && (
            <HomePage
              snapshot={snapshot}
              primaryRole={primaryRole}
              onNavigate={setPage}
            />
          )}
          {page === "cities" && (
            <CitiesPage
              snapshot={snapshot}
              roles={roles}
              onCity={(cityKey) => void changeCity(cityKey)}
              onCreate={createCity}
            />
          )}
          {page === "data" && (
            <DataPage snapshot={snapshot} roles={roles} mutate={mutate} />
          )}
          {page === "analysis" && (
            <AnalysisPage
              snapshot={snapshot}
              roles={roles}
              findings={visibleFindings}
              filter={findingFilter}
              onFilter={setFindingFilter}
              formOpen={findingFormOpen}
              onFormOpen={setFindingFormOpen}
              mutate={mutate}
            />
          )}
          {page === "measures" && (
            <MeasuresPage snapshot={snapshot} roles={roles} mutate={mutate} />
          )}
          {page === "review" && (
            <ReviewPage
              snapshot={snapshot}
              roles={roles}
              selectedId={caseId}
              detail={caseDetail}
              onSelect={(id) => void openCase(id)}
              mutate={mutate}
            />
          )}
          {page === "evidence" && (
            <EvidencePage snapshot={snapshot} roles={roles} mutate={mutate} />
          )}
          {page === "operations" && (
            <OperationsPage snapshot={snapshot} roles={roles} mutate={mutate} />
          )}
        </main>
      </section>
      {searchOpen && (
        <div
          className="service-search-backdrop"
          onMouseDown={() => setSearchOpen(false)}
        >
          <section
            className="service-global-search"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <form onSubmit={(event) => void search(event)}>
              <span>⌕</span>
              <input
                autoFocus
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="都市、データセット、ソース、Finding、Investigation、Scenario、IDを検索"
              />
              <button type="button" onClick={() => setSearchOpen(false)}>
                閉じる
              </button>
            </form>
            <div>
              {searchResults.length === 0 ? (
                <ServiceEmpty
                  title="検索語を入力してください"
                  detail="技術IDは検索できますが、通常画面では必要な場合だけ表示します。"
                />
              ) : (
                searchResults.map((result) => (
                  <button
                    key={String(result.entity_id)}
                    type="button"
                    onClick={() => {
                      if (result.entity_type === "investigation") {
                        setPage("review");
                        void openCase(String(result.entity_id));
                      }
                      setSearchOpen(false);
                    }}
                  >
                    <span>{String(result.entity_type)}</span>
                    <strong>{String(result.title)}</strong>
                    <small>{String(result.subtitle ?? "")}</small>
                  </button>
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="service-page-header">
      <div>
        <span>{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}

function HomePage({
  snapshot,
  primaryRole,
  onNavigate,
}: {
  snapshot: ServiceSnapshot;
  primaryRole: ProductRole;
  onNavigate(page: ServicePage): void;
}) {
  const summary = snapshot.cityHome?.summary;
  if (!snapshot.cityHome)
    return (
      <>
        <PageHeader
          eyebrow="SERVICE HOME"
          title="自治体サービスを開始"
          description={ROLE_HOME_LEAD[primaryRole]}
        />
        <ServiceEmpty
          title="都市がまだ登録されていません"
          detail="管理者がOrganizationへCityを登録すると、City Homeとデータオンボーディングが利用できます。"
        />
      </>
    );
  return (
    <>
      <PageHeader
        eyebrow={`${ROLE_LABELS[primaryRole]} HOME`}
        title={`${snapshot.cityHome.city.name}の業務状況`}
        description={ROLE_HOME_LEAD[primaryRole]}
      />
      <div className="service-kpis">
        <button type="button" onClick={() => onNavigate("analysis")}>
          <span>OPEN FINDINGS</span>
          <strong>{summary?.open_findings ?? 0}</strong>
          <small>追加調査候補</small>
        </button>
        <button type="button" onClick={() => onNavigate("review")}>
          <span>INVESTIGATIONS</span>
          <strong>{summary?.active_investigations ?? 0}</strong>
          <small>進行中の調査</small>
        </button>
        <button type="button" onClick={() => onNavigate("review")}>
          <span>REVIEWS</span>
          <strong>{summary?.pending_reviews ?? 0}</strong>
          <small>レビュー待ち</small>
        </button>
        <button type="button" onClick={() => onNavigate("review")}>
          <span>FIELD CHECKS</span>
          <strong>{summary?.pending_field_checks ?? 0}</strong>
          <small>現地確認待ち</small>
        </button>
      </div>
      <section className="service-panel full city-data-readiness">
        <header>
          <div>
            <span>CITY DATA</span>
            <h2>この都市で使えるデータ</h2>
          </div>
          <button className="table-action" type="button" onClick={() => onNavigate("data")}>
            Data Hubを開く
          </button>
        </header>
        <div>
          <article>
            <span>最新の都市状態</span>
            <strong>{snapshot.cityHome.latest_state?.label ?? "未登録"}</strong>
            <small>
              {snapshot.cityHome.latest_state
                ? `${snapshot.cityHome.latest_state.effective_date} · ${snapshot.cityHome.latest_state.lifecycle_status}`
                : "観測済みUrban Stateがありません"}
            </small>
          </article>
          <article>
            <span>利用可能</span>
            <strong>{summary?.coverage_available ?? 0}</strong>
            <small>Dataset family</small>
          </article>
          <article>
            <span>部分利用</span>
            <strong>{summary?.coverage_partial ?? 0}</strong>
            <small>制約を確認</small>
          </article>
          <article>
            <span>カバレッジ不足</span>
            <strong>{summary?.coverage_gaps ?? 0}</strong>
            <small>不足・未確認・要レビュー</small>
          </article>
          <article>
            <span>更新あり</span>
            <strong>{summary?.update_available ?? 0}</strong>
            <small>昇格は人が確認</small>
          </article>
        </div>
      </section>
      <div className="service-home-grid">
        <section className="service-panel">
          <header>
            <div>
              <span>MY WORK</span>
              <h2>担当と通知</h2>
            </div>
            <b>
              {snapshot.workQueue.assignments.length +
                snapshot.workQueue.notifications.filter((item) => !item.read_at)
                  .length}
            </b>
          </header>
          {snapshot.workQueue.unregistered_identity ? (
            <ServiceEmpty
              title="このIdentityの担当情報は未登録です"
              detail="開発用Identityでは架空の担当者を作成しません。管理者が実利用者をOrganizationへ登録してください。"
            />
          ) : snapshot.workQueue.assignments.length === 0 ? (
            <ServiceEmpty
              title="現在の担当はありません"
              detail="新しい割当が作成されると、ここへ表示されます。"
            />
          ) : (
            snapshot.workQueue.assignments.map((item) => (
              <article className="work-item" key={item.id}>
                <StatusChip value={item.status} />
                <strong>{item.assignment_type.replaceAll("_", " ")}</strong>
                <small>期限 {item.due_date ?? "未設定"}</small>
              </article>
            ))
          )}
        </section>
        <section className="service-panel">
          <header>
            <div>
              <span>RECENT ACTIVITY</span>
              <h2>最近の業務履歴</h2>
            </div>
          </header>
          {snapshot.cityHome.recent_activity.length === 0 ? (
            <ServiceEmpty
              title="Activityはまだありません"
              detail="データ更新、調査、レビュー、現地確認、Decision Recordを人が操作した履歴だけを表示します。"
            />
          ) : (
            snapshot.cityHome.recent_activity.map((item) => (
              <article
                className="activity-item"
                key={`${item.resource_type}-${item.resource_id}-${item.occurred_at}`}
              >
                <i />
                <div>
                  <strong>{item.summary}</strong>
                  <small>
                    {item.actor_label} · {formatDate(item.occurred_at)}
                  </small>
                </div>
              </article>
            ))
          )}
        </section>
      </div>
    </>
  );
}

function CitiesPage({
  snapshot,
  roles,
  onCity,
  onCreate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  onCity(city: string): void;
  onCreate(body: Record<string, unknown>): Promise<boolean>;
}) {
  const [formOpen, setFormOpen] = useState(snapshot.cities.length === 0);
  const canCreate = permits(roles, ["administrator"]);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const created = await onCreate({
      city_code: data.get("city_code"),
      city_key: data.get("city_key"),
      name: data.get("name"),
      prefecture_code: data.get("prefecture_code"),
      prefecture_name: data.get("prefecture_name"),
      analysis_crs: data.get("analysis_crs"),
    });
    if (created) setFormOpen(false);
  };
  return (
    <>
      <PageHeader
        eyebrow="CITIES"
        title="都市ワークスペース"
        description="Organization内の都市、利用可能な機能、進行中の業務を確認します。"
        action={
          canCreate ? (
            <button
              className="primary-action"
              type="button"
              onClick={() => setFormOpen((value) => !value)}
            >
              都市を登録
            </button>
          ) : undefined
        }
      />
      {canCreate && formOpen && (
        <form className="service-form" onSubmit={(event) => void submit(event)}>
          <label>
            市区町村コード
            <input
              name="city_code"
              required
              pattern="[0-9]{5}"
              placeholder="26202"
            />
          </label>
          <label>
            City key
            <input name="city_key" required pattern="[a-z0-9][a-z0-9-]+" />
          </label>
          <label>
            都市名
            <input name="name" required />
          </label>
          <label>
            都道府県コード
            <input name="prefecture_code" required pattern="[0-9]{2}" />
          </label>
          <label>
            都道府県名
            <input name="prefecture_name" required />
          </label>
          <label>
            分析座標系
            <input name="analysis_crs" required pattern="EPSG:[0-9]{4,6}" />
          </label>
          <button className="primary-action" type="submit">
            onboardingを開始
          </button>
        </form>
      )}
      <ServiceTable
        caption="都市一覧"
        empty="登録された都市がありません"
        rows={snapshot.cities as unknown as Array<Record<string, unknown>>}
        rowKey={(row) => String(row.city_id)}
        onRow={(row) => onCity(String(row.city_key))}
        columns={[
          { key: "name", label: "都市" },
          {
            key: "service_status",
            label: "状態",
            render: (row) => <StatusChip value={String(row.service_status)} />,
          },
          {
            key: "available_capabilities",
            label: "機能",
            render: (row) =>
              `${Number(row.available_capabilities ?? 0)} / ${Number(row.capability_count ?? 0)}`,
          },
          { key: "open_findings", label: "Finding" },
          { key: "active_investigations", label: "Investigation" },
          {
            key: "latest_activity_at",
            label: "データ基準日",
            render: (row) => String(row.latest_reference_date ?? "未確認"),
          },
          { key: "failed_jobs", label: "失敗Job" },
          { key: "data_review_backlog", label: "要確認" },
        ]}
      />
    </>
  );
}

function DataPage({
  snapshot,
  roles,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const [datasetFormOpen, setDatasetFormOpen] = useState(false);
  const [stateFormOpen, setStateFormOpen] = useState(false);
  const [annualUpdateFormOpen, setAnnualUpdateFormOpen] = useState(false);
  const [dataView, setDataView] = useState<DataHubView>("sources");
  const [taskNotes, setTaskNotes] = useState<Record<string, string>>({});
  const hub = snapshot.dataHub;
  if (!hub)
    return (
      <>
        <PageHeader
          eyebrow="DATA HUB"
          title="データオンボーディング"
          description="登録、検証、受入、取込、分析可能化、昇格を明示的に管理します。"
        />
        <ServiceEmpty
          title="都市を選択してください"
          detail="データはアップロードだけで分析対象へ昇格しません。"
        />
      </>
    );
  const canManage = permits(roles, ["data_manager"]);
  const canField = permits(roles, ["field_staff", "planner"]);
  const city = hub.city.city_key;
  const registerDataset = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/datasets`,
      "POST",
      {
        dataset_key: data.get("dataset_key"),
        title: data.get("title"),
        provider: data.get("provider"),
        dataset_category: data.get("dataset_category"),
        data_classification: data.get("data_classification"),
        version_key: data.get("version_key"),
        dataset_year: Number(data.get("dataset_year")),
        data_format: data.get("data_format"),
        source_url: data.get("source_url") || null,
        license: data.get("license") || null,
        declared_source_crs: data.get("declared_source_crs") || null,
      },
      "Dataset Versionをregisteredとして登録しました",
    );
    setDatasetFormOpen(false);
  };
  const createUrbanState = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/urban-states`,
      "POST",
      {
        state_key: data.get("state_key"),
        label: data.get("label"),
        effective_date: data.get("effective_date"),
        state_type: "observed",
        primary_dataset_version_id: data.get("primary_dataset_version_id"),
        source_verified: true,
      },
      "Urban Stateをdraftとして登録しました",
    );
    setStateFormOpen(false);
  };
  const createAnnualUpdate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/annual-updates`,
      "POST",
      {
        from_urban_state_id: data.get("from_urban_state_id"),
        to_urban_state_id: data.get("to_urban_state_id"),
        algorithm_version: "citygap-state-diff@1.0.0",
      },
      "旧年度記録を保持したまま年次差分Jobを登録しました",
    );
    setAnnualUpdateFormOpen(false);
  };
  const nextStatus: Record<string, string> = {
    registered: "validating",
    validating: "validated",
    validated: "accepted",
    accepted: "ingesting",
    ingesting: "analysis_ready",
    analysis_ready: "promoted",
    rejected: "validating",
    failed: "validating",
  };
  const stateTransitions: Record<string, string> = {
    draft: "validated",
    validated: "current",
  };
  const onboardingLabels: Record<string, string> = {
    city_registration: "都市を登録",
    official_source_discovery: "公式ソースを探索",
    license_review: "利用条件を確認",
    source_selection: "利用候補を選択",
    dataset_validation: "品質を検証",
    immutable_ingestion: "原本を保存・取込",
    capability_activation: "分析機能を有効化",
    first_urban_state: "最初のUrban State",
    catalog_ready: "データカタログ準備完了",
    first_analysis: "最初の分析",
  };
  return (
    <>
      <PageHeader
        eyebrow="DATA HUB"
        title={`${hub.city.name}のデータ`}
        description="年度、出典、品質、Capability、PLATEAU収録モデルを一つのライフサイクルで管理します。"
        action={
          canManage ? (
            <div className="page-actions">
              <button
                className="primary-action"
                type="button"
                onClick={() => setDatasetFormOpen((value) => !value)}
              >
                Datasetを登録
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => setStateFormOpen((value) => !value)}
              >
                Urban Stateを作成
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => setAnnualUpdateFormOpen((value) => !value)}
              >
                年次更新を開始
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() =>
                  void mutate(
                    "/api/v1/sources/discover",
                    "POST",
                    { city, source_keys: [] },
                    "公式カタログの候補探索を登録しました。採用はまだ行っていません",
                  )
                }
              >
                公式ソースを探す
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() =>
                  void mutate(
                    "/api/v1/sources/metadata-checks/schedule",
                    "POST",
                    { city, limit: 25 },
                    "提供元への負荷を抑えた更新確認を予約しました",
                  )
                }
              >
                更新確認を予約
              </button>
            </div>
          ) : undefined
        }
      />
      {snapshot.onboarding && (
        <section className="service-panel full onboarding-progress">
          <header>
            <div>
              <span>ONBOARDING</span>
              <h2>導入状況</h2>
            </div>
          </header>
          <div>
            {snapshot.onboarding.steps.map((step) => (
              <article key={step.key}>
                <StatusChip value={step.status} />
                <strong>{onboardingLabels[step.key] ?? step.key.replaceAll("_", " ")}</strong>
                <small>{step.promoted_versions ?? step.count ?? 0} ready</small>
              </article>
            ))}
          </div>
        </section>
      )}
      {datasetFormOpen && (
        <form className="service-form" onSubmit={registerDataset}>
          <label>
            種別
            <select name="dataset_category" required>
              <option value="plateau">PLATEAU</option>
              <option value="population">人口</option>
              <option value="facilities">施設</option>
              <option value="transport">交通</option>
              <option value="hazard">災害</option>
              <option value="planning">都市計画</option>
              <option value="municipal_custom">自治体独自</option>
            </select>
          </label>
          <label>
            Dataset key
            <input name="dataset_key" required />
          </label>
          <label>
            表示名
            <input name="title" required />
          </label>
          <label>
            提供者
            <input name="provider" required />
          </label>
          <label>
            Version
            <input name="version_key" required />
          </label>
          <label>
            年度
            <input
              name="dataset_year"
              type="number"
              min="1900"
              max="2200"
              required
            />
          </label>
          <label>
            形式
            <input
              name="data_format"
              required
              placeholder="CityGML / CSV / GeoJSON"
            />
          </label>
          <label>
            Source URL
            <input name="source_url" type="url" />
          </label>
          <label>
            License
            <input name="license" />
          </label>
          <label>
            Source CRS
            <input name="declared_source_crs" placeholder="EPSG:6697" />
          </label>
          <label>
            データ分類
            <select name="data_classification" defaultValue="internal">
              <option value="public">public</option>
              <option value="internal">internal</option>
              <option value="restricted">restricted</option>
            </select>
          </label>
          <button className="primary-action" type="submit">
            registeredとして保存
          </button>
        </form>
      )}
      {stateFormOpen && (
        <form className="service-form" onSubmit={createUrbanState}>
          <label>
            State key
            <input name="state_key" required />
          </label>
          <label>
            表示名
            <input name="label" required />
          </label>
          <label>
            基準日
            <input name="effective_date" type="date" required />
          </label>
          <label className="wide">
            Primary Dataset Version
            <select name="primary_dataset_version_id" required>
              <option value="">promoted versionを選択</option>
              {hub.datasets
                .filter((dataset) => dataset.service_status === "promoted")
                .map((dataset) => (
                  <option key={dataset.version_id} value={dataset.version_id}>
                    {dataset.title} · {dataset.dataset_year} ·{" "}
                    {dataset.version_key}
                  </option>
                ))}
            </select>
          </label>
          <button className="primary-action" type="submit">
            draftを作成
          </button>
        </form>
      )}
      {annualUpdateFormOpen && (
        <form className="service-form" onSubmit={createAnnualUpdate}>
          <label>
            更新前のUrban State
            <select name="from_urban_state_id" required>
              <option value="">validated/current/supersededを選択</option>
              {hub.urban_states
                .filter((state) =>
                  ["validated", "current", "superseded"].includes(
                    state.lifecycle_status,
                  ),
                )
                .map((state) => (
                  <option key={`from-${state.id}`} value={state.id}>
                    {state.label} · {state.effective_date}
                  </option>
                ))}
            </select>
          </label>
          <label>
            更新後のUrban State
            <select name="to_urban_state_id" required>
              <option value="">validated/currentを選択</option>
              {hub.urban_states
                .filter((state) =>
                  ["validated", "current"].includes(state.lifecycle_status),
                )
                .map((state) => (
                  <option key={`to-${state.id}`} value={state.id}>
                    {state.label} · {state.effective_date}
                  </option>
                ))}
            </select>
          </label>
          <button className="primary-action" type="submit">
            差分Jobを登録
          </button>
          <p className="form-boundary">
            更新後Stateは検証済みで、更新前より新しい基準日が必要です。旧年度のInvestigation・分析・Report参照は変更しません。
          </p>
        </form>
      )}
      <div className="service-tabs data-hub-tabs" role="tablist" aria-label="Data Hub views">
        {(
          [
            ["sources", "Sources"],
            ["datasets", "Datasets"],
            ["coverage", "Coverage"],
            ["quality", "Quality"],
            ["updates", "Updates"],
            ["review", "Feedback / Overrides"],
            ["licenses", "Licenses"],
            ["dependencies", "Dependencies"],
          ] as Array<[DataHubView, string]>
        ).map(([view, label]) => (
          <button
            type="button"
            role="tab"
            aria-selected={dataView === view}
            className={dataView === view ? "active" : ""}
            key={view}
            onClick={() => setDataView(view)}
          >
            {label}
          </button>
        ))}
      </div>
      {dataView === "sources" && (
        <>
          <section className="service-panel full">
            <header>
              <div>
                <span>SOURCE INVENTORY</span>
                <h2>公式・自治体データソース</h2>
              </div>
              <b>{hub.sources.length}</b>
            </header>
            <ServiceTable
              caption="データソース一覧"
              empty="確認済みソースはありません"
              rows={hub.sources as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => String(row.id)}
              columns={[
                {
                  key: "title",
                  label: "ソース",
                  render: (row) => (
                    <a href={String(row.source_url)} target="_blank" rel="noreferrer">
                      {String(row.title)}
                    </a>
                  ),
                },
                { key: "provider", label: "提供者" },
                { key: "dataset_family", label: "Family" },
                {
                  key: "availability",
                  label: "利用状況",
                  render: (row) => <StatusChip value={String(row.availability)} />,
                },
                { key: "review_status", label: "確認" },
                {
                  key: "reference_date",
                  label: "基準日",
                  render: (row) => String(row.reference_date ?? "期間表記を参照"),
                },
                { key: "license_name", label: "利用条件" },
                {
                  key: "action",
                  label: "更新確認",
                  render: (row) =>
                    canManage ? (
                      <button
                        className="table-action"
                        type="button"
                        onClick={() =>
                          void mutate(
                            `/api/v1/sources/${String(row.id)}/metadata-checks`,
                            "POST",
                            { reason: "Data Hubで担当者が更新確認を承認" },
                            "メタデータだけを確認するJobを登録しました",
                          )
                        }
                      >
                        確認を予約
                      </button>
                    ) : (
                      <span>—</span>
                    ),
                },
              ]}
            />
          </section>
          <div className="service-two-column data-source-detail-grid">
            <section className="service-panel">
              <header>
                <div>
                  <span>SOURCE TIMELINE</span>
                  <h2>混在する基準時点</h2>
                </div>
              </header>
              {hub.source_timeline.map((entry) => (
                <article className="source-timeline-row" key={entry.id}>
                  <time>{entry.reference_period}</time>
                  <div>
                    <strong>{entry.label}</strong>
                    <small>{entry.temporal_note}</small>
                  </div>
                </article>
              ))}
            </section>
            <section className="service-panel">
              <header>
                <div>
                  <span>COMPARISON & CONFLICT</span>
                  <h2>ソース差分と未解決競合</h2>
                </div>
              </header>
              {hub.comparisons.length === 0 && hub.conflicts.length === 0 ? (
                <ServiceEmpty
                  title="比較記録はありません"
                  detail="比較は総合点や自動勝者を生成しません。"
                />
              ) : (
                <>
                  {hub.comparisons.map((comparison) => (
                    <article className="source-comparison" key={comparison.id}>
                      <StatusChip value="reviewed" />
                      <div>
                        <strong>
                          {comparison.left_source_title} ↔ {comparison.right_source_title}
                        </strong>
                        <small>{comparison.conclusion}</small>
                        <details>
                          <summary>比較ディメンション</summary>
                          <pre>{JSON.stringify(comparison.dimensions, null, 2)}</pre>
                        </details>
                      </div>
                    </article>
                  ))}
                  {hub.conflicts.map((conflict) => (
                    <article className="source-comparison" key={conflict.id}>
                      <StatusChip value={conflict.status} />
                      <div>
                        <strong>
                          {conflict.conflict_key} · {conflict.conflict_count ?? "—"}件
                        </strong>
                        <small>{conflict.explanation}</small>
                      </div>
                    </article>
                  ))}
                </>
              )}
            </section>
          </div>
        </>
      )}
      {dataView === "coverage" && (
        <>
          <div className="service-kpis data-coverage-kpis">
            <button type="button">
              <span>AVAILABLE</span>
              <strong>{hub.coverage_summary.available}</strong>
              <small>検証済み利用可能</small>
            </button>
            <button type="button">
              <span>PARTIAL</span>
              <strong>{hub.coverage_summary.partial}</strong>
              <small>制約付き・部分利用</small>
            </button>
            <button type="button">
              <span>GAPS</span>
              <strong>{hub.coverage_summary.gaps}</strong>
              <small>不足・未確認・要レビュー</small>
            </button>
            <button type="button">
              <span>MIXED / STALE</span>
              <strong>{hub.coverage_summary.mixed_or_stale}</strong>
              <small>年次差を明示</small>
            </button>
          </div>
          <ServiceTable
            caption="都市データカバレッジ"
            empty="カバレッジ評価はありません"
            rows={hub.coverage as unknown as Array<Record<string, unknown>>}
            rowKey={(row) => String(row.dataset_family)}
            columns={[
              { key: "dataset_family", label: "Dataset family" },
              {
                key: "status",
                label: "状態",
                render: (row) => <StatusChip value={String(row.status)} />,
              },
              { key: "temporal_alignment", label: "時点整合" },
              { key: "source_title", label: "根拠ソース" },
              { key: "explanation", label: "説明" },
              { key: "unavailable_reason", label: "不足理由" },
            ]}
          />
        </>
      )}
      {dataView === "review" && (
        <>
          <div className="claim-boundary">
            Feedbackとlocal overrideは自治体のreview layerです。公式raw・標準化済みrecordを直接変更せず、
            公式更新が届いた場合もoverrideを自動削除せず照合候補を作ります。
          </div>
          <section className="service-panel full">
            <header>
              <div>
                <span>SOURCE FEEDBACK</span>
                <h2>現地・庁内からの確認情報</h2>
              </div>
              <b>{(hub.source_feedback ?? []).length}</b>
            </header>
            <ServiceTable
              caption="公開データへのfeedback"
              empty="Feedbackはありません"
              rows={(hub.source_feedback ?? []) as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => String(row.id)}
              columns={[
                { key: "source_title", label: "公式ソース" },
                { key: "feedback_type", label: "種別" },
                { key: "statement", label: "確認内容" },
                {
                  key: "status",
                  label: "状態",
                  render: (row) => <StatusChip value={String(row.status)} />,
                },
                {
                  key: "field_task_status",
                  label: "現地確認",
                  render: (row) => String(row.field_task_status ?? "未作成"),
                },
                {
                  key: "action",
                  label: "次の操作",
                  render: (row) =>
                    canField &&
                    !row.field_task_id &&
                    ["submitted", "triaged"].includes(String(row.status)) ? (
                      <button
                        type="button"
                        className="table-action"
                        onClick={() =>
                          void mutate(
                            `/api/v1/source-feedback/${String(row.id)}/field-task`,
                            "POST",
                            {
                              expected_feedback_status: row.status,
                              title: `${String(row.source_title)}の現地確認`,
                              checklist: ["対象と位置を確認", "確認日時と根拠を記録"],
                            },
                            "公式データを変更せず、現地確認タスクを作成しました",
                          )
                        }
                      >
                        現地確認へ
                      </button>
                    ) : (
                      <span>—</span>
                    ),
                },
              ]}
            />
          </section>
          <section className="service-panel full">
            <header>
              <div>
                <span>FIELD VERIFICATION</span>
                <h2>公開データ確認タスク</h2>
              </div>
            </header>
            <ServiceTable
              caption="Feedbackから作成した現地確認タスク"
              empty="現地確認タスクはありません"
              rows={(hub.field_tasks ?? []) as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => String(row.id)}
              columns={[
                { key: "title", label: "タスク" },
                { key: "source_title", label: "ソース" },
                {
                  key: "status",
                  label: "状態",
                  render: (row) => <StatusChip value={String(row.status)} />,
                },
                { key: "assigned_to", label: "担当" },
                { key: "due_date", label: "期限" },
                { key: "resolution_note", label: "確認結果" },
              ]}
            />
          </section>
          <section className="service-panel full">
            <header>
              <div>
                <span>LOCAL OVERRIDES</span>
                <h2>期限付き自治体補正layer</h2>
              </div>
            </header>
            <ServiceTable
              caption="Local overrideと公式更新の照合候補"
              empty="Local overrideはありません"
              rows={(hub.local_overrides ?? []) as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => String(row.id)}
              columns={[
                { key: "display_name", label: "対象" },
                { key: "reason", label: "理由" },
                { key: "effective_date", label: "適用日" },
                { key: "expires_at", label: "見直し期限" },
                {
                  key: "review_status",
                  label: "Review",
                  render: (row) => <StatusChip value={String(row.review_status)} />,
                },
                {
                  key: "candidate_count",
                  label: "公式更新候補",
                  render: (row) => `${Number(row.candidate_count ?? 0)}件`,
                },
              ]}
            />
          </section>
          <section className="service-panel full">
            <header>
              <div>
                <span>PUBLIC TRANSPARENCY</span>
                <h2>公開済みの出典・限界</h2>
              </div>
            </header>
            <ServiceTable
              caption="公開透明性記録"
              empty="公開済み記録はありません"
              rows={(hub.public_transparency ?? []) as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => String(row.id)}
              columns={[
                { key: "title", label: "公開項目" },
                {
                  key: "source_citations",
                  label: "出典",
                  render: (row) =>
                    `${Array.isArray(row.source_citations) ? row.source_citations.length : 0}件`,
                },
                {
                  key: "limitations",
                  label: "限界",
                  render: (row) =>
                    `${Array.isArray(row.limitations) ? row.limitations.length : 0}件`,
                },
                {
                  key: "published_at",
                  label: "公開日時",
                  render: (row) => formatDate(row.published_at),
                },
              ]}
            />
          </section>
        </>
      )}
      {dataView === "licenses" && (
        <ServiceTable
          caption="利用条件"
          empty="利用条件は登録されていません"
          rows={hub.licenses as unknown as Array<Record<string, unknown>>}
          rowKey={(row) => String(row.license_id)}
          columns={[
            {
              key: "license_name",
              label: "利用条件",
              render: (row) => (
                <a href={String(row.license_url)} target="_blank" rel="noreferrer">
                  {String(row.license_name)}
                </a>
              ),
            },
            { key: "license_id", label: "ID" },
            {
              key: "commercial_use",
              label: "商用",
              render: (row) => row.commercial_use == null ? "要確認" : row.commercial_use ? "可" : "不可",
            },
            {
              key: "redistribution",
              label: "再配布",
              render: (row) => row.redistribution == null ? "要確認" : row.redistribution ? "可" : "不可",
            },
            {
              key: "attribution_required",
              label: "帰属表示",
              render: (row) => row.attribution_required == null ? "要確認" : row.attribution_required ? "必要" : "不要",
            },
            {
              key: "unknown_terms",
              label: "未確認条件",
              render: (row) => row.unknown_terms ? "あり" : "なし",
            },
          ]}
        />
      )}
      {dataView === "dependencies" && (
        <ServiceTable
          caption="分析とデータ依存関係"
          empty="分析依存関係はありません"
          rows={hub.dependencies as unknown as Array<Record<string, unknown>>}
          rowKey={(row) => `${String(row.analysis_id)}:${String(row.analysis_version)}:${String(row.dataset_family)}`}
          columns={[
            { key: "analysis_name", label: "分析" },
            { key: "dataset_family", label: "Dataset family" },
            { key: "requirement_level", label: "要件" },
            {
              key: "coverage_status",
              label: "カバレッジ",
              render: (row) => <StatusChip value={String(row.coverage_status ?? "unknown")} />,
            },
            {
              key: "effect",
              label: "実行Tierへの影響",
              render: (row) => <StatusChip value={String(row.effect)} />,
            },
            { key: "rule_version", label: "選定方針" },
          ]}
        />
      )}
      {dataView === "datasets" && (
        <>
      <section className="service-panel full">
        <header>
          <div>
            <span>DATASET VERSIONS</span>
            <h2>データとバージョン</h2>
          </div>
        </header>
        <ServiceTable
          caption="データセットバージョン"
          empty="データセットが登録されていません"
          rows={hub.datasets as unknown as Array<Record<string, unknown>>}
          rowKey={(row) => String(row.version_id ?? row.dataset_id)}
          columns={[
            { key: "title", label: "データ" },
            { key: "dataset_category", label: "種別" },
            { key: "dataset_year", label: "年度" },
            { key: "version_key", label: "Version" },
            {
              key: "service_status",
              label: "Service状態",
              render: (row) => (
                <StatusChip value={String(row.service_status)} />
              ),
            },
            {
              key: "quality_status",
              label: "品質",
              render: (row) => (
                <StatusChip value={String(row.quality_status)} />
              ),
            },
            { key: "data_classification", label: "分類" },
            {
              key: "action",
              label: "次の操作",
              render: (row) =>
                canManage && nextStatus[String(row.service_status)] ? (
                  <button
                    className="table-action"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      const proposed = nextStatus[String(row.service_status)];
                      const explicitAction =
                        proposed === "validating"
                          ? {
                              path: `/api/v1/datasets/${String(row.dataset_id)}/validate`,
                              method: "POST" as const,
                              body: {
                                version_id: row.version_id,
                                expected_status: row.service_status,
                                note: "Data Hubで担当者が品質検証を開始",
                              },
                            }
                          : proposed === "promoted"
                            ? {
                                path: `/api/v1/datasets/${String(row.dataset_id)}/promote`,
                                method: "POST" as const,
                                body: {
                                  version_id: row.version_id,
                                  expected_status: "analysis_ready",
                                  note: "出典・品質・利用条件を確認して分析利用を承認",
                                },
                              }
                            : {
                                path: `/api/v1/dataset-versions/${String(row.version_id)}/status`,
                                method: "PATCH" as const,
                                body: {
                                  expected_status: row.service_status,
                                  proposed_status: proposed,
                                  note: "Data Hubで人がライフサイクルを確認",
                                },
                              };
                      void mutate(
                        explicitAction.path,
                        explicitAction.method,
                        explicitAction.body,
                        proposed === "promoted"
                          ? "分析に使用中へ更新し、Capability再評価を予約しました"
                          : proposed === "validating"
                            ? "品質検証を予約しました"
                            : `${proposed}へ更新しました`,
                      );
                    }}
                  >
                    {nextStatus[String(row.service_status)] === "promoted"
                      ? "分析に使用する"
                      : nextStatus[String(row.service_status)] === "validating"
                        ? "品質を検証"
                        : nextStatus[String(row.service_status)]}
                  </button>
                ) : (
                  <span>—</span>
                ),
            },
          ]}
        />
      </section>
        </>
      )}
      {dataView === "updates" && (
        <>
          <section className="service-panel full">
            <header>
              <div>
                <span>SOURCE UPDATES</span>
                <h2>メタデータ更新確認</h2>
              </div>
            </header>
            <ServiceTable
              caption="ソース更新確認"
              empty="更新確認履歴はまだありません"
              rows={hub.updates as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => `${String(row.city_source_id)}:${String(row.checked_at)}`}
              columns={[
                { key: "source_title", label: "ソース" },
                {
                  key: "result",
                  label: "結果",
                  render: (row) => <StatusChip value={String(row.result)} />,
                },
                {
                  key: "checked_at",
                  label: "確認日時",
                  render: (row) => formatDate(row.checked_at),
                },
                {
                  key: "next_check_after",
                  label: "次回以降",
                  render: (row) => formatDate(row.next_check_after),
                },
              ]}
            />
          </section>
          <section className="service-panel full">
            <header>
              <div>
                <span>DATA MANAGER TASKS</span>
                <h2>更新・品質・利用条件の対応</h2>
              </div>
              <b>
                {
                  (hub.data_tasks ?? []).filter((task) =>
                    ["open", "in_progress"].includes(task.status),
                  ).length
                }
              </b>
            </header>
            <ServiceTable
              caption="データ管理タスク"
              empty="対応が必要なデータタスクはありません"
              rows={(hub.data_tasks ?? []) as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => String(row.id)}
              columns={[
                { key: "title", label: "タスク" },
                { key: "task_type", label: "種別" },
                { key: "source_title", label: "ソース" },
                { key: "dataset_year", label: "年度" },
                {
                  key: "status",
                  label: "状態",
                  render: (row) => <StatusChip value={String(row.status)} />,
                },
                {
                  key: "created_at",
                  label: "登録",
                  render: (row) => formatDate(row.created_at),
                },
                {
                  key: "action",
                  label: "担当者の判断",
                  render: (row) => {
                    if (!canManage || ["resolved", "dismissed"].includes(String(row.status)))
                      return <span>—</span>;
                    if (row.status === "open")
                      return (
                        <button
                          className="table-action"
                          type="button"
                          onClick={() =>
                            void mutate(
                              `/api/v1/data-tasks/${String(row.id)}`,
                              "PATCH",
                              {
                                expected_status: "open",
                                proposed_status: "in_progress",
                                resolution_note: null,
                              },
                              "データタスクの対応を開始しました",
                            )
                          }
                        >
                          対応を開始
                        </button>
                      );
                    const note = taskNotes[String(row.id)] ?? "";
                    return (
                      <div className="table-inline-action">
                        <input
                          aria-label={`${String(row.title)}の対応記録`}
                          value={note}
                          placeholder="確認内容を記録"
                          onChange={(event) =>
                            setTaskNotes((current) => ({
                              ...current,
                              [String(row.id)]: event.target.value,
                            }))
                          }
                        />
                        <button
                          className="table-action"
                          type="button"
                          disabled={!note.trim()}
                          onClick={() =>
                            void mutate(
                              `/api/v1/data-tasks/${String(row.id)}`,
                              "PATCH",
                              {
                                expected_status: "in_progress",
                                proposed_status: "resolved",
                                resolution_note: note.trim(),
                              },
                              "判断根拠を残してタスクを完了しました",
                            )
                          }
                        >
                          対応済み
                        </button>
                      </div>
                    );
                  },
                },
              ]}
            />
          </section>
      <section className="service-panel full">
        <header>
          <div>
            <span>URBAN STATES</span>
            <h2>都市状態と年度</h2>
          </div>
        </header>
        <ServiceTable
          caption="Urban State一覧"
          empty="Urban Stateはまだありません"
          rows={hub.urban_states as unknown as Array<Record<string, unknown>>}
          rowKey={(row) => String(row.id)}
          columns={[
            { key: "label", label: "都市状態" },
            { key: "effective_date", label: "基準日" },
            { key: "state_type", label: "種別" },
            {
              key: "lifecycle_status",
              label: "状態",
              render: (row) => (
                <StatusChip value={String(row.lifecycle_status)} />
              ),
            },
            {
              key: "source_verified",
              label: "出典確認",
              render: (row) => (row.source_verified ? "確認済み" : "未確認"),
            },
            {
              key: "action",
              label: "次の操作",
              render: (row) => {
                if (!canManage) return <span>—</span>;
                const next = stateTransitions[String(row.lifecycle_status)];
                return next ? (
                  <button
                    className="table-action"
                    type="button"
                    onClick={() =>
                      void mutate(
                        `/api/v1/urban-states/${String(row.id)}/status`,
                        "PATCH",
                        {
                          expected_status: row.lifecycle_status,
                          proposed_status: next,
                          note: "Data Hubで出典・品質・年度を確認",
                        },
                        `Urban Stateを${next}へ更新しました`,
                      )
                    }
                  >
                    {next}
                  </button>
                ) : (
                  <span>—</span>
                );
              },
            },
          ]}
        />
      </section>
      <section className="service-panel full">
        <header>
          <div>
            <span>ANNUAL UPDATE</span>
            <h2>年次差分と再計算Job</h2>
          </div>
        </header>
        <ServiceTable
          caption="年次更新履歴"
          empty="年次更新はまだ登録されていません"
          rows={
            (hub.annual_updates ?? []) as unknown as Array<
              Record<string, unknown>
            >
          }
          rowKey={(row) => String(row.id)}
          columns={[
            { key: "from_label", label: "更新前" },
            { key: "to_label", label: "更新後" },
            { key: "algorithm_version", label: "差分Version" },
            {
              key: "job_state",
              label: "Job",
              render: (row) => (
                <StatusChip value={String(row.job_state ?? row.status)} />
              ),
            },
            { key: "job_stage", label: "Stage" },
            {
              key: "created_at",
              label: "登録",
              render: (row) => formatDate(row.created_at),
            },
          ]}
        />
      </section>
        </>
      )}
      {dataView === "quality" && (
        <>
          <section className="service-panel full">
            <header>
              <div>
                <span>FAMILY GATES</span>
                <h2>データ種別ごとの品質ルール</h2>
              </div>
            </header>
            <ServiceTable
              caption="データファミリー品質ゲート"
              empty="品質ゲート方針はありません"
              rows={hub.quality_gate_policies as unknown as Array<Record<string, unknown>>}
              rowKey={(row) => `${String(row.dataset_family)}:${String(row.gate_key)}:${String(row.policy_version)}`}
              columns={[
                { key: "dataset_family", label: "Dataset family" },
                { key: "dimension", label: "Dimension" },
                { key: "gate_key", label: "Gate" },
                { key: "requirement", label: "要件" },
                { key: "failure_action", label: "失敗時" },
                { key: "policy_version", label: "Version" },
              ]}
            />
          </section>
      <div className="service-two-column">
        <section className="service-panel">
          <header>
            <div>
              <span>QUALITY</span>
              <h2>品質チェック</h2>
            </div>
          </header>
          {hub.quality_checks.length === 0 ? (
            <ServiceEmpty
              title="品質チェックは未登録です"
              detail="geometry、CRS、属性、件数、欠損、コード、年度整合、公開制約を記録します。"
            />
          ) : (
            hub.quality_checks.map((check) => (
              <article
                className="quality-row"
                key={`${check.dataset_version_id}-${check.check_key}-${check.checked_at}`}
              >
                <StatusChip value={check.status} />
                <div>
                  <strong>{check.check_key.replaceAll("_", " ")}</strong>
                  <small>{check.explanation}</small>
                </div>
              </article>
            ))
          )}
        </section>
        <section className="service-panel">
          <header>
            <div>
              <span>PLATEAU MODEL</span>
              <h2>収録モデル</h2>
            </div>
          </header>
          {hub.plateau_model.length === 0 ? (
            <ServiceEmpty
              title="PLATEAU Model Inventoryはありません"
              detail="実際に取込済みのCityGML objectのみを表示します。"
            />
          ) : (
            hub.plateau_model.map((model) => (
              <article
                className="quality-row"
                key={`${model.plateau_dataset_version_id}-${model.theme}`}
              >
                <StatusChip value={`${model.feature_count}`} />
                <div>
                  <strong>{model.theme}</strong>
                  <small>
                    LOD {model.available_lods.join(", ") || "—"} · geometry{" "}
                    {model.geometry_count}
                  </small>
                </div>
              </article>
            ))
          )}
        </section>
      </div>
        </>
      )}
    </>
  );
}

function AnalysisPage({
  snapshot,
  roles,
  findings,
  filter,
  onFilter,
  formOpen,
  onFormOpen,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  findings: Finding[];
  filter: string;
  onFilter(value: string): void;
  formOpen: boolean;
  onFormOpen(value: boolean): void;
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const canWrite = permits(roles, ["analyst", "planner"]);
  const city = snapshot.cityHome?.city.city_key;
  const submitFinding = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!city) return;
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/findings`,
      "POST",
      {
        finding_type: data.get("finding_type"),
        title: data.get("title"),
        summary: data.get("summary"),
        urban_state_id: data.get("urban_state_id") || null,
      },
      "Findingを登録しました",
    );
    onFormOpen(false);
  };
  const startInvestigation = async (finding: Finding) => {
    if (!city || !finding.urban_state_id) return;
    if (finding.status === "new") {
      const triaged = await mutate(
        `/api/v1/findings/${finding.id}/status`,
        "PATCH",
        { expected_status: "new", proposed_status: "triaged" },
        "Findingをtriageしました",
      );
      if (!triaged) return;
    }
    await mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/investigations`,
      "POST",
      {
        urban_state_id: finding.urban_state_id,
        title: `調査: ${finding.title}`,
        objective: finding.summary,
        finding_ids: [finding.id],
        spatial_state: {},
      },
      "Investigationを開始しました",
    );
  };
  return (
    <>
      <PageHeader
        eyebrow="ANALYSIS"
        title="Finding Queueと分析カタログ"
        description="Findingは追加調査候補です。深刻度や政策優先順位、問題認定を自動付与しません。"
        action={
          canWrite ? (
            <button
              className="primary-action"
              type="button"
              onClick={() => onFormOpen(!formOpen)}
            >
              Findingを登録
            </button>
          ) : undefined
        }
      />
      <AnalysisRunPanel snapshot={snapshot} canRun={canWrite} mutate={mutate} />
      {(snapshot.dataHub?.missing_data.length ?? 0) > 0 && (
        <section className="service-panel full missing-data-panel">
          <header>
            <div>
              <span>MISSING DATA BESIDE FINDINGS</span>
              <h2>分析候補の解釈に必要な不足データ</h2>
            </div>
            <b>{snapshot.dataHub?.missing_data.length ?? 0}</b>
          </header>
          <div>
            {snapshot.dataHub?.missing_data.map((dependency) => (
              <article
                key={`${dependency.analysis_id}:${dependency.analysis_version}:${dependency.dataset_family}`}
              >
                <StatusChip value={dependency.coverage_status ?? "unknown"} />
                <div>
                  <strong>
                    {dependency.analysis_name} · {dependency.dataset_family}
                  </strong>
                  <small>
                    {dependency.requirement_level} → {dependency.effect}
                    {dependency.unavailable_reason
                      ? ` · ${dependency.unavailable_reason}`
                      : ""}
                  </small>
                </div>
              </article>
            ))}
          </div>
          <p className="service-panel-note">
            不足はFindingの深刻度や政策優先順位を意味しません。required不足は分析をUNAVAILABLE、enhancement不足はBASEとして明示します。
          </p>
        </section>
      )}
      {formOpen && (
        <form className="service-form" onSubmit={submitFinding}>
          <label>
            種類
            <select name="finding_type" required>
              <option value="accessibility_gap">Accessibility Gap</option>
              <option value="care_access_review_candidate">
                Care Access Review Candidate
              </option>
              <option value="activity_service_gap_candidate">
                Activity Service Gap Candidate
              </option>
              <option value="network_criticality">Network Criticality</option>
              <option value="planning_context">Planning Context</option>
              <option value="temporal_change">Temporal Change</option>
              <option value="resilience_impact">Resilience Impact</option>
              <option value="data_quality_issue">Data Quality Issue</option>
            </select>
          </label>
          <label>
            タイトル
            <input name="title" required maxLength={500} />
          </label>
          <label className="wide">
            説明
            <textarea name="summary" required maxLength={5000} />
          </label>
          <label>
            Urban State ID
            <input
              name="urban_state_id"
              inputMode="text"
              placeholder="実在するUUID（任意）"
            />
          </label>
          <button className="primary-action" type="submit">
            候補として登録
          </button>
        </form>
      )}
      <div className="service-tabs" role="tablist">
        <button
          type="button"
          className={filter === "open" ? "active" : ""}
          onClick={() => onFilter("open")}
        >
          Open
        </button>
        {[
          "new",
          "triaged",
          "investigating",
          "review_required",
          "resolved",
          "dismissed",
          "all",
        ].map((status) => (
          <button
            type="button"
            key={status}
            className={filter === status ? "active" : ""}
            onClick={() => onFilter(status)}
          >
            {status.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      <ServiceTable
        caption="Finding Queue"
        empty="該当するFindingはありません"
        rows={findings as unknown as Array<Record<string, unknown>>}
        rowKey={(row) => String(row.id)}
        columns={[
          { key: "title", label: "Finding" },
          {
            key: "finding_type",
            label: "種類",
            render: (row) => String(row.finding_type).replaceAll("_", " "),
          },
          {
            key: "status",
            label: "状態",
            render: (row) => <StatusChip value={String(row.status)} />,
          },
          {
            key: "validation_status",
            label: "検証",
            render: (row) => (
              <StatusChip value={String(row.validation_status)} />
            ),
          },
          {
            key: "created_at",
            label: "登録",
            render: (row) => formatDate(row.created_at),
          },
          {
            key: "action",
            label: "次の操作",
            render: (row) => {
              const finding = row as unknown as Finding;
              return canWrite && ["new", "triaged"].includes(finding.status) ? (
                <button
                  className="table-action"
                  type="button"
                  disabled={!finding.urban_state_id}
                  title={
                    finding.urban_state_id
                      ? "人の操作で調査を開始"
                      : "Urban Stateが必要です"
                  }
                  onClick={() => void startInvestigation(finding)}
                >
                  Investigation開始
                </button>
              ) : (
                <span>—</span>
              );
            },
          },
        ]}
      />
      <section className="service-panel full catalog">
        <header>
          <div>
            <span>ANALYSIS CATALOG</span>
            <h2>再現可能な分析定義</h2>
          </div>
        </header>
        <div className="catalog-grid">
          {snapshot.analyses.map((analysis) => (
            <article key={`${analysis.id}-${analysis.version}`}>
              <div>
                <StatusChip value={`v${analysis.version}`} />
                <small>{analysis.required_capabilities.join(" · ")}</small>
              </div>
              <h3>{analysis.name}</h3>
              <p>{analysis.purpose}</p>
              {analysis.dataset_requirements.length > 0 && (
                <dl className="catalog-requirements">
                  {(["required", "optional", "enhancement"] as const).map(
                    (level) => {
                      const families = analysis.dataset_requirements
                        .filter(
                          (requirement) =>
                            requirement.requirement_level === level,
                        )
                        .map((requirement) => requirement.dataset_family);
                      return families.length > 0 ? (
                        <div key={level}>
                          <dt>{level}</dt>
                          <dd>{families.join(" · ")}</dd>
                        </div>
                      ) : null;
                    },
                  )}
                </dl>
              )}
              <footer>
                <strong>断定しない範囲</strong>
                <span>{analysis.claim_boundary}</span>
              </footer>
            </article>
          ))}
        </div>
      </section>
      <section className="service-panel full run-history">
        <header>
          <div>
            <span>ANALYSIS RUNS</span>
            <h2>Version固定の実行履歴</h2>
          </div>
        </header>
        <ServiceTable
          caption="分析実行履歴"
          empty="この都市で実行された分析はありません"
          rows={
            snapshot.analysisRuns as unknown as Array<Record<string, unknown>>
          }
          rowKey={(row) => String(row.id)}
          columns={[
            { key: "analysis_type", label: "分析" },
            { key: "algorithm_version", label: "Version" },
            {
              key: "job_state",
              label: "Job",
              render: (row) => (
                <StatusChip value={String(row.job_state ?? row.status)} />
              ),
            },
            { key: "job_stage", label: "現在Stage" },
            {
              key: "dataset_version_ids",
              label: "入力Version数",
              render: (row) =>
                Array.isArray(row.dataset_version_ids)
                  ? row.dataset_version_ids.length
                  : 0,
            },
            {
              key: "started_at",
              label: "登録",
              render: (row) => formatDate(row.started_at),
            },
          ]}
        />
      </section>
    </>
  );
}

function AnalysisRunPanel({
  snapshot,
  canRun,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  canRun: boolean;
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const [definitionKey, setDefinitionKey] = useState(
    snapshot.analyses[0]
      ? `${snapshot.analyses[0].id}@${snapshot.analyses[0].version}`
      : "",
  );
  const definition = snapshot.analyses.find(
    (item) => `${item.id}@${item.version}` === definitionKey,
  );
  const city = snapshot.cityHome?.city.city_key;
  const promoted =
    snapshot.dataHub?.datasets.filter(
      (dataset) => dataset.version_id && dataset.service_status === "promoted",
    ) ?? [];
  const states = snapshot.dataHub?.urban_states ?? [];
  const datasetRoles = definition?.input_contract.dataset_roles ?? [];

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!city || !definition) return;
    const data = new FormData(event.currentTarget);
    const datasetVersions = Object.fromEntries(
      datasetRoles.map((role) => [role, String(data.get(`dataset:${role}`))]),
    );
    const parameters = Object.fromEntries(
      definition.parameters.map((parameter) => {
        const raw = String(
          data.get(`parameter:${parameter.parameter_key}`) ?? "",
        );
        const value =
          parameter.value_type === "integer"
            ? Number.parseInt(raw, 10)
            : parameter.value_type === "number"
              ? Number(raw)
              : parameter.value_type === "boolean"
                ? raw === "true"
                : raw;
        return [parameter.parameter_key, value];
      }),
    );
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/analysis-runs`,
      "POST",
      {
        analysis_id: definition.id,
        analysis_version: definition.version,
        urban_state_id: data.get("urban_state_id"),
        dataset_versions: datasetVersions,
        parameters,
      },
      "Version固定の分析Jobを登録しました",
    );
  };

  return (
    <section className="service-panel full analysis-runner">
      <header>
        <div>
          <span>RUN ANALYSIS</span>
          <h2>明示したUrban StateとDataset Versionで実行</h2>
        </div>
      </header>
      {!canRun ? (
        <ServiceEmpty
          title="閲覧権限で表示しています"
          detail="分析の実行はAnalyst、Planner、Administratorが行えます。"
        />
      ) : !definition || !city ? (
        <ServiceEmpty
          title="分析定義または都市がありません"
          detail="管理者が実在する都市と有効な分析定義を登録してください。"
        />
      ) : states.length === 0 || promoted.length === 0 ? (
        <ServiceEmpty
          title="実行条件が揃っていません"
          detail="Data HubでUrban Stateとpromoted済みDataset Versionを準備してください。"
        />
      ) : (
        <form className="service-form analysis-run-form" onSubmit={submit}>
          <label>
            分析定義
            <select
              value={definitionKey}
              onChange={(event) => setDefinitionKey(event.target.value)}
            >
              {snapshot.analyses.map((analysis) => (
                <option
                  key={`${analysis.id}@${analysis.version}`}
                  value={`${analysis.id}@${analysis.version}`}
                >
                  {analysis.name} · v{analysis.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            Urban State
            <select name="urban_state_id" required>
              {states.map((state) => (
                <option key={state.id} value={state.id}>
                  {state.label} · {state.effective_date} ·{" "}
                  {state.lifecycle_status}
                </option>
              ))}
            </select>
          </label>
          {datasetRoles.map((role) => (
            <label key={role}>
              Dataset role: {role}
              <select name={`dataset:${role}`} required>
                <option value="">Versionを選択</option>
                {promoted.map((dataset) => (
                  <option
                    key={`${role}-${dataset.version_id}`}
                    value={dataset.version_id}
                  >
                    {dataset.title} · {dataset.dataset_year} ·{" "}
                    {dataset.version_key}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {definition.parameters.map((parameter) => (
            <label key={parameter.parameter_key}>
              {parameter.description}
              {parameter.value_type === "boolean" ? (
                <select
                  name={`parameter:${parameter.parameter_key}`}
                  defaultValue={String(parameter.default_value)}
                >
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : (
                <input
                  name={`parameter:${parameter.parameter_key}`}
                  type={
                    ["integer", "number"].includes(parameter.value_type)
                      ? "number"
                      : "text"
                  }
                  defaultValue={String(parameter.default_value)}
                  min={parameter.minimum ?? undefined}
                  max={parameter.maximum ?? undefined}
                  step={parameter.value_type === "integer" ? 1 : undefined}
                  required
                />
              )}
            </label>
          ))}
          <button className="primary-action" type="submit">
            分析Jobを登録
          </button>
          <p className="form-boundary">
            必須Capabilityと入力VersionはAPIでも再検証されます。実行結果は候補であり行政判断ではありません。
          </p>
        </form>
      )}
    </section>
  );
}

function MeasuresPage({
  snapshot,
  roles,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const canCompare = permits(roles, ["analyst", "planner"]);
  const city = snapshot.cityHome?.city.city_key;
  const toggle = (id: string) => {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : current.length < 3
          ? [...current, id]
          : current,
    );
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!city || selected.length < 2 || selected.length > 3) return;
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/scenario-comparisons`,
      "POST",
      {
        title: data.get("title"),
        scenario_run_ids: selected,
        comparison_dimensions: [
          { key: "metrics", label: "指標" },
          { key: "assumptions", label: "仮定" },
          { key: "validation", label: "検証" },
          { key: "field_checks", label: "現地確認" },
        ],
      },
      "Scenario Comparisonを保存しました",
    );
    setSelected([]);
  };
  return (
    <>
      <PageHeader
        eyebrow="MEASURES"
        title="Scenario Library"
        description="複数案を同じUrban Stateと明示した仮定で比較します。最良案や採用案を自動決定しません。"
      />
      <ServiceTable
        caption="Scenario Library"
        empty="この都市にはScenarioがありません"
        rows={snapshot.scenarios as unknown as Array<Record<string, unknown>>}
        rowKey={(row) => String(row.id)}
        columns={[
          {
            key: "select",
            label: "比較",
            render: (row) => (
              <input
                type="checkbox"
                aria-label={`${String(row.title)}を比較`}
                checked={selected.includes(String(row.id))}
                disabled={
                  !canCompare ||
                  (!selected.includes(String(row.id)) && selected.length >= 3)
                }
                onChange={() => toggle(String(row.id))}
              />
            ),
          },
          { key: "title", label: "Scenario" },
          { key: "objective_mode", label: "比較軸" },
          { key: "site_count", label: "地点数" },
          {
            key: "lifecycle_status",
            label: "状態",
            render: (row) => (
              <StatusChip value={String(row.lifecycle_status)} />
            ),
          },
          {
            key: "review_status",
            label: "Review",
            render: (row) => <StatusChip value={String(row.review_status)} />,
          },
          {
            key: "generated_at",
            label: "生成",
            render: (row) => formatDate(row.generated_at),
          },
          {
            key: "action",
            label: "再利用",
            render: (row) =>
              canCompare ? (
                <button
                  className="table-action"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    void mutate(
                      `/api/v1/scenarios/${String(row.id)}/clone`,
                      "POST",
                      { title: `${String(row.title)} の複製` },
                      "計算結果を変えず、現地確認をリセットしたdraftとして複製しました",
                    );
                  }}
                >
                  Clone
                </button>
              ) : (
                <span>—</span>
              ),
          },
        ]}
      />
      {canCompare && selected.length >= 2 && (
        <form className="service-form comparison-form" onSubmit={submit}>
          <label className="wide">
            比較名
            <input name="title" required maxLength={500} />
          </label>
          <div className="comparison-selection">
            {selected.length}案を選択中（最大3案）
          </div>
          <button className="primary-action" type="submit">
            比較を保存
          </button>
        </form>
      )}
      <section className="service-panel full comparison-library">
        <header>
          <div>
            <span>COMPARISON LIBRARY</span>
            <h2>保存済み比較</h2>
          </div>
        </header>
        <ServiceTable
          caption="保存済みScenario Comparison"
          empty="保存済みの比較はありません"
          rows={
            snapshot.scenarioComparisons as unknown as Array<
              Record<string, unknown>
            >
          }
          rowKey={(row) => String(row.id)}
          columns={[
            { key: "title", label: "比較" },
            {
              key: "scenario_run_ids",
              label: "案数",
              render: (row) =>
                Array.isArray(row.scenario_run_ids)
                  ? row.scenario_run_ids.length
                  : 0,
            },
            {
              key: "comparison_dimensions",
              label: "比較軸",
              render: (row) =>
                Array.isArray(row.comparison_dimensions)
                  ? row.comparison_dimensions.length
                  : 0,
            },
            { key: "created_by", label: "作成者" },
            {
              key: "created_at",
              label: "保存",
              render: (row) => formatDate(row.created_at),
            },
          ]}
        />
      </section>
      <div className="service-boundary-note">
        <strong>比較の境界</strong>
        <p>
          費用は自治体が登録したversion付き外部データだけを利用します。災害Stress
          Testは明示した利用不可仮定の比較であり、災害予測ではありません。
        </p>
      </div>
    </>
  );
}

function ReviewPage({
  snapshot,
  roles,
  selectedId,
  detail,
  onSelect,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  selectedId: string | null;
  detail: Record<string, unknown> | null;
  onSelect(id: string): void;
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const canReview = permits(roles, ["planner"]);
  const canField = permits(roles, ["field_staff", "planner"]);
  const investigation = detail?.investigation as Investigation | undefined;
  const reviews = (detail?.reviews ?? []) as Array<Record<string, unknown>>;
  const [offlinePackage, setOfflinePackage] =
    useState<FieldOfflinePackage | null>(null);
  const [offlineQueue, setOfflineQueue] = useState<QueuedFieldOperation[]>([]);
  const [fieldStatus, setFieldStatus] = useState<string | null>(null);
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);
  const [spatialViewport, setSpatialViewport] = useState<MunicipalViewport>({
    longitude:
      snapshot.cityHome?.city.city_key === "fujisawa" ? 139.49 : 135.33,
    latitude: snapshot.cityHome?.city.city_key === "fujisawa" ? 35.34 : 35.47,
    zoom: 12,
  });
  const [visibleEntityTypes, setVisibleEntityTypes] = useState<string[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const entities = useMemo(
    () => (detail?.entities ?? []) as MunicipalSpatialEntity[],
    [detail],
  );
  const savedViews = useMemo(
    () => (detail?.saved_views ?? []) as Array<Record<string, unknown>>,
    [detail],
  );
  const sourceContributions = useMemo(
    () =>
      (detail?.source_contributions ?? []) as Array<Record<string, unknown>>,
    [detail],
  );
  const investigationSourceTimeline = useMemo(
    () => (detail?.source_timeline ?? []) as Array<Record<string, unknown>>,
    [detail],
  );
  const selectedContributions = sourceContributions.filter(
    (contribution) => contribution.entity_id === selectedEntityId,
  );

  useEffect(() => {
    if (!investigation) return;
    const requestedToken =
      typeof window === "undefined"
        ? null
        : new URLSearchParams(window.location.search).get("savedView");
    const requested = savedViews.find(
      (view) => view.share_token === requestedToken,
    );
    const state = (requested?.spatial_state ??
      (investigation as unknown as Record<string, unknown>).spatial_state ??
      {}) as Record<string, unknown>;
    const viewport = state.viewport as Record<string, unknown> | undefined;
    if (
      viewport &&
      Number.isFinite(Number(viewport.longitude)) &&
      Number.isFinite(Number(viewport.latitude)) &&
      Number.isFinite(Number(viewport.zoom))
    ) {
      setSpatialViewport({
        longitude: Number(viewport.longitude),
        latitude: Number(viewport.latitude),
        zoom: Number(viewport.zoom),
      });
    }
    const available = [
      ...new Set(entities.map((entity) => entity.entity_type)),
    ];
    const storedTypes = Array.isArray(state.visible_entity_types)
      ? state.visible_entity_types.map(String)
      : available;
    setVisibleEntityTypes(
      storedTypes.filter((entityType) => available.includes(entityType)),
    );
    setSelectedEntityId((current) =>
      current && entities.some((entity) => entity.entity_id === current)
        ? current
        : null,
    );
  }, [entities, investigation, savedViews]);

  useEffect(() => {
    const city = snapshot.cityHome?.city.city_key;
    if (!canField || !city || typeof indexedDB === "undefined") return;
    void queuedFieldOperations(snapshot.profile.organization.id, city)
      .then(setOfflineQueue)
      .catch(() => setFieldStatus("端末のoffline queueを読み込めませんでした"));
  }, [
    canField,
    snapshot.cityHome?.city.city_key,
    snapshot.profile.organization.id,
  ]);

  const packageSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const city = snapshot.cityHome?.city.city_key;
    if (!city || !investigation) return;
    const data = new FormData(event.currentTarget);
    try {
      const downloaded = await serviceApi.createOfflinePackage(city, {
        urban_state_id: investigation.urban_state_id,
        scenario_run_id: String(data.get("scenario_run_id")),
        site_order: Number(data.get("site_order")),
      });
      await cacheSelectedFieldPackage({
        offline_package_id: downloaded.offline_package_id,
        package_version: downloaded.package_version,
        organization_id: snapshot.profile.organization.id,
        city_key: city,
        content: downloaded.content,
      });
      setOfflinePackage(downloaded);
      setFieldStatus("選択地点をこの端末へ保存しました");
    } catch (error) {
      setFieldStatus(
        error instanceof Error
          ? error.message
          : "offline packageを保存できませんでした",
      );
    }
  };

  const offlineRecordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!offlinePackage) return;
    const city = snapshot.cityHome?.city.city_key;
    if (!city) return;
    const data = new FormData(event.currentTarget);
    const operation: QueuedFieldOperation = {
      client_operation_id: crypto.randomUUID(),
      offline_package_id: offlinePackage.offline_package_id,
      organization_id: snapshot.profile.organization.id,
      city_key: city,
      scenario_run_id: offlinePackage.content.scenario_run_id,
      site_order: offlinePackage.content.site_order,
      base_record_version: Number(
        offlinePackage.content.field_record?.record_version ?? 1,
      ),
      client_updated_at: new Date().toISOString(),
      payload: {
        notes: String(data.get("offline_notes") ?? ""),
        site_access: String(data.get("site_access") ?? "unknown"),
      },
      status: "pending",
    };
    try {
      await queueFieldOperation(operation);
      setOfflineQueue((current) => [...current, operation]);
      setFieldStatus(
        "現地記録を端末queueへ保存しました。通信復帰後に同期できます",
      );
    } catch (error) {
      setFieldStatus(
        error instanceof Error ? error.message : "端末へ保存できませんでした",
      );
    }
  };

  const syncOfflineQueue = async () => {
    const city = snapshot.cityHome?.city.city_key;
    if (!city) return;
    const updates: QueuedFieldOperation[] = [];
    for (const operation of offlineQueue) {
      if (operation.status !== "pending") {
        updates.push(operation);
        continue;
      }
      try {
        const response = await serviceApi.syncFieldOperation(city, {
          client_operation_id: operation.client_operation_id,
          offline_package_id: operation.offline_package_id,
          scenario_run_id: operation.scenario_run_id,
          site_order: operation.site_order,
          base_record_version: operation.base_record_version,
          client_updated_at: operation.client_updated_at,
          payload: operation.payload,
        });
        const updated = applySyncResponse(
          operation,
          response.httpStatus,
          response.payload,
        );
        await saveFieldOperation(updated);
        if (updated.status !== "applied") updates.push(updated);
      } catch (error) {
        updates.push(operation);
        setFieldStatus(
          error instanceof Error ? error.message : "同期に失敗しました",
        );
      }
    }
    setOfflineQueue(updates);
    if (updates.some((operation) => operation.status === "conflict")) {
      setFieldStatus("競合を検出しました。自動上書きせず、明示解決が必要です");
    } else if (updates.length === 0) {
      setFieldStatus("offline queueを同期しました");
    }
  };

  const resolveOfflineConflict = async (
    operation: QueuedFieldOperation,
    resolutionStatus: "use_server" | "use_client",
  ) => {
    const city = snapshot.cityHome?.city.city_key;
    if (!city || !operation.conflict_id) return;
    try {
      await serviceApi.resolveFieldConflict(
        city,
        operation.conflict_id,
        resolutionStatus,
      );
      await saveFieldOperation({
        ...operation,
        status: resolutionStatus === "use_server" ? "rejected" : "applied",
      });
      setOfflineQueue((current) =>
        current.filter(
          (candidate) =>
            candidate.client_operation_id !== operation.client_operation_id,
        ),
      );
      setFieldStatus(
        resolutionStatus === "use_server"
          ? "サーバー版を採用して競合を解決しました"
          : "端末版を確認して採用し、競合を解決しました",
      );
    } catch (error) {
      setFieldStatus(
        error instanceof Error ? error.message : "競合を解決できませんでした",
      );
    }
  };

  const attachmentSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const city = snapshot.cityHome?.city.city_key;
    const data = new FormData(event.currentTarget);
    const file = data.get("attachment");
    if (!city || !(file instanceof File) || file.size === 0) return;
    try {
      const metadata = await serviceApi.uploadAttachment(
        city,
        file,
        "restricted",
      );
      setAttachmentIds((current) => [...current, metadata.id]);
      setFieldStatus(
        `${metadata.original_file_name} をrestricted添付として保存しました`,
      );
      event.currentTarget.reset();
    } catch (error) {
      setFieldStatus(
        error instanceof Error ? error.message : "添付を保存できませんでした",
      );
    }
  };

  const fieldSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedId) return;
    const data = new FormData(event.currentTarget);
    const saved = await mutate(
      `/api/v1/investigations/${selectedId}/field-observations`,
      "POST",
      {
        observation_type: data.get("observation_type"),
        notes: data.get("notes"),
        observed_at: new Date().toISOString(),
        attachment_ids: attachmentIds,
      },
      "現地観察を記録しました",
    );
    if (saved) setAttachmentIds([]);
  };
  const savedViewSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedId || !investigation) return;
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/investigations/${selectedId}/saved-views`,
      "POST",
      {
        title: data.get("title"),
        data_classification: data.get("data_classification"),
        spatial_state: {
          schema_version: "citygap-saved-spatial-view-1.0.0",
          investigation_id: selectedId,
          urban_state_id: investigation.urban_state_id,
          viewport: spatialViewport,
          visible_entity_types: visibleEntityTypes,
        },
      },
      "現在の空間状態を保存しました",
    );
    event.currentTarget.reset();
  };
  const restoreSavedView = (view: Record<string, unknown>) => {
    const state = view.spatial_state as Record<string, unknown> | undefined;
    const viewport = state?.viewport as Record<string, unknown> | undefined;
    if (viewport) {
      setSpatialViewport({
        longitude: Number(viewport.longitude),
        latitude: Number(viewport.latitude),
        zoom: Number(viewport.zoom),
      });
    }
    if (Array.isArray(state?.visible_entity_types)) {
      setVisibleEntityTypes(state.visible_entity_types.map(String));
    }
    setFieldStatus(`保存ビュー「${String(view.title)}」を復元しました`);
  };
  const shareSavedView = async (view: Record<string, unknown>) => {
    if (typeof window === "undefined" || !selectedId) return;
    const url = new URL(window.location.href);
    url.searchParams.set("servicePage", "review");
    url.searchParams.set("investigation", selectedId);
    url.searchParams.set("savedView", String(view.share_token));
    try {
      await navigator.clipboard.writeText(url.toString());
      setFieldStatus(
        "認証済みの同一Organizationメンバー向け共有URLをコピーしました",
      );
    } catch {
      setFieldStatus(url.toString());
    }
  };
  const decisionSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedId) return;
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/investigations/${selectedId}/decisions`,
      "POST",
      {
        review_request_id: data.get("review_request_id"),
        decision: data.get("decision"),
        reason: data.get("reason"),
        related_evidence_ids: String(data.get("evidence_ids") ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      },
      "Decision Recordを人の操作で記録しました",
    );
  };
  return (
    <>
      <PageHeader
        eyebrow="REVIEW"
        title="Investigation Case Workflow"
        description="Findingから調査、Scenario、Review、Field、Decisionへ一つのCaseとして引き継ぎます。"
      />
      <div className="case-layout">
        <section className="service-panel case-list">
          <header>
            <div>
              <span>INVESTIGATIONS</span>
              <h2>調査一覧</h2>
            </div>
          </header>
          {snapshot.investigations.length === 0 ? (
            <ServiceEmpty
              title="Investigationはありません"
              detail="AnalystがFindingをtriageして調査を開始すると表示されます。"
            />
          ) : (
            snapshot.investigations.map((item) => (
              <button
                type="button"
                key={item.id}
                className={selectedId === item.id ? "active" : ""}
                onClick={() => onSelect(item.id)}
              >
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.objective}</small>
                </div>
                <StatusChip value={item.status} />
              </button>
            ))
          )}
        </section>
        <section className="service-panel case-detail">
          <header>
            <div>
              <span>CASE DETAIL</span>
              <h2>{investigation?.title ?? "調査を選択"}</h2>
            </div>
          </header>
          {!selectedId ? (
            <ServiceEmpty
              title="Investigationを選択してください"
              detail="技術IDではなく、調査タイトルと業務状態を中心に表示します。"
            />
          ) : !detail ? (
            <div className="inline-loading">Caseを読み込んでいます</div>
          ) : (
            <div className="case-workflow">
              <ol>
                <li className="done">Finding</li>
                <li
                  className={
                    investigation?.status !== "open" ? "done" : "current"
                  }
                >
                  Investigation
                </li>
                <li className={reviews.length ? "done" : ""}>Review</li>
                <li
                  className={
                    ((detail.field_observations ?? []) as unknown[]).length
                      ? "done"
                      : ""
                  }
                >
                  Field
                </li>
                <li
                  className={
                    ((detail.decisions ?? []) as unknown[]).length ? "done" : ""
                  }
                >
                  Decision
                </li>
              </ol>
              <p>{investigation?.objective}</p>
              <MunicipalSpatialWorkspace
                entities={entities}
                viewport={spatialViewport}
                visibleEntityTypes={visibleEntityTypes}
                onViewportChange={setSpatialViewport}
                onVisibleEntityTypesChange={setVisibleEntityTypes}
                onEntitySelect={(entityId) => {
                  setSelectedEntityId(entityId);
                  setFieldStatus(`空間entity ${entityId} を選択しました`);
                }}
              />
              <div className="service-two-column investigation-source-context">
                <section className="service-panel">
                  <header>
                    <div>
                      <span>SELECTED FEATURE LINEAGE</span>
                      <h2>選択地物へ寄与したソース</h2>
                    </div>
                  </header>
                  {!selectedEntityId ? (
                    <ServiceEmpty
                      title="地図上の地物を選択してください"
                      detail="保存済みentityの明示出典とcanonical spatial linkだけを表示します。"
                    />
                  ) : selectedContributions.length === 0 ? (
                    <ServiceEmpty
                      title="紐づく出典記録はありません"
                      detail="一致を推測せず、linkageが保存された場合だけ表示します。"
                    />
                  ) : (
                    selectedContributions.map((contribution, index) => (
                      <article
                        className="source-comparison"
                        key={`${String(contribution.entity_id)}:${String(contribution.contribution_role)}:${String(contribution.source_title)}:${index}`}
                      >
                        <StatusChip value={String(contribution.match_method ?? "source")} />
                        <div>
                          <strong>{String(contribution.source_title)}</strong>
                          <small>
                            {String(contribution.reference_period ?? "基準時点未記載")} · {String(contribution.contribution_role)}
                          </small>
                          <small>{String(contribution.explanation)}</small>
                        </div>
                      </article>
                    ))
                  )}
                </section>
                <section className="service-panel">
                  <header>
                    <div>
                      <span>INVESTIGATION SOURCE TIMELINE</span>
                      <h2>この調査が参照する時点</h2>
                    </div>
                  </header>
                  {investigationSourceTimeline.length === 0 ? (
                    <ServiceEmpty
                      title="時点付きソースはありません"
                      detail="出典年を推定せず、Urban Stateとentityに記録された値だけを表示します。"
                    />
                  ) : (
                    investigationSourceTimeline.map((entry, index) => (
                      <article
                        className="source-timeline-row"
                        key={`${String(entry.source_role)}:${String(entry.source_title)}:${String(entry.reference_period)}:${index}`}
                      >
                        <time>{String(entry.reference_period)}</time>
                        <div>
                          <strong>{String(entry.source_title)}</strong>
                          <small>
                            {String(entry.source_role)} · {String(entry.contribution_count)}件
                          </small>
                        </div>
                      </article>
                    ))
                  )}
                </section>
              </div>
              <section className="case-form saved-view-workspace">
                <h3>空間ビューを保存・共有</h3>
                {permits(roles, ["analyst", "planner"]) && (
                  <form onSubmit={savedViewSubmit}>
                    <label>
                      ビュー名
                      <input name="title" required maxLength={500} />
                    </label>
                    <label>
                      データ分類
                      <select
                        name="data_classification"
                        defaultValue="internal"
                      >
                        <option value="public">public</option>
                        <option value="internal">internal</option>
                        <option value="restricted">restricted</option>
                      </select>
                    </label>
                    <button type="submit">現在の地図状態を保存</button>
                  </form>
                )}
                {savedViews.length === 0 ? (
                  <p className="service-muted">保存済みビューはありません。</p>
                ) : (
                  <div className="saved-view-list">
                    {savedViews.map((view) => (
                      <article key={String(view.id)}>
                        <div>
                          <strong>{String(view.title)}</strong>
                          <small>
                            {String(view.data_classification)} ·{" "}
                            {formatDate(view.updated_at)}
                          </small>
                        </div>
                        <button
                          type="button"
                          onClick={() => restoreSavedView(view)}
                        >
                          復元
                        </button>
                        <button
                          type="button"
                          onClick={() => void shareSavedView(view)}
                        >
                          共有URL
                        </button>
                      </article>
                    ))}
                  </div>
                )}
                <p className="form-boundary">
                  共有tokenは認可の代わりではありません。同一Organizationでログインし、Investigation閲覧権限が必要です。
                </p>
              </section>
              <div className="case-actions">
                {canReview && investigation?.status !== "closed" && (
                  <button
                    type="button"
                    onClick={() =>
                      void mutate(
                        `/api/v1/investigations/${selectedId}/reviews`,
                        "POST",
                        { request_note: "Case画面からレビューを依頼" },
                        "レビューを依頼しました",
                      )
                    }
                  >
                    Reviewを依頼
                  </button>
                )}
                {canReview &&
                  reviews.map((review) =>
                    review.status === "requested" ? (
                      <button
                        key={String(review.id)}
                        type="button"
                        onClick={() =>
                          void mutate(
                            `/api/v1/reviews/${String(review.id)}/status`,
                            "PATCH",
                            {
                              expected_status: "requested",
                              proposed_status: "in_review",
                              review_note: "",
                            },
                            "レビューを開始しました",
                          )
                        }
                      >
                        Review開始
                      </button>
                    ) : review.status === "in_review" ? (
                      <button
                        key={String(review.id)}
                        type="button"
                        onClick={() =>
                          void mutate(
                            `/api/v1/reviews/${String(review.id)}/status`,
                            "PATCH",
                            {
                              expected_status: "in_review",
                              proposed_status: "reviewed",
                              review_note: "根拠と限界を確認",
                            },
                            "レビュー済みとして記録しました",
                          )
                        }
                      >
                        Review完了
                      </button>
                    ) : null,
                  )}
                {canReview && investigation?.status === "field_check" && (
                  <button
                    type="button"
                    onClick={() =>
                      void mutate(
                        `/api/v1/investigations/${selectedId}/status`,
                        "PATCH",
                        {
                          expected_status: "field_check",
                          proposed_status: "decision_pending",
                          note: "現地記録を確認し、Decision Record作成へ進む",
                        },
                        "現地確認を完了しました",
                      )
                    }
                  >
                    現地確認を完了
                  </button>
                )}
              </div>
              {canField && (
                <div className="field-workspace">
                  <section className="case-form offline-package-form">
                    <h3>選択地点のoffline準備</h3>
                    <p>
                      都市全体ではなく、選んだScenario地点の地図文脈・PLATEAU属性・根拠要約だけを端末へ保存します。
                    </p>
                    {snapshot.scenarios.length ? (
                      <form onSubmit={packageSubmit}>
                        <label>
                          Scenario
                          <select name="scenario_run_id" required>
                            {snapshot.scenarios.map((scenario) => (
                              <option key={scenario.id} value={scenario.id}>
                                {scenario.title} · {scenario.site_count}地点
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          地点番号
                          <input
                            name="site_order"
                            type="number"
                            min="1"
                            max="20"
                            defaultValue="1"
                            required
                          />
                        </label>
                        <button type="submit">この地点を端末へ保存</button>
                      </form>
                    ) : (
                      <p className="service-muted">
                        保存対象にできる実在Scenarioがありません。Scenario生成・保存後に利用できます。
                      </p>
                    )}
                    {offlinePackage && (
                      <form onSubmit={offlineRecordSubmit}>
                        <strong>
                          package v{offlinePackage.package_version} · site{" "}
                          {offlinePackage.content.site_order}
                        </strong>
                        <label>
                          現地アクセス
                          <select name="site_access" defaultValue="unknown">
                            <option value="unknown">未確認</option>
                            <option value="confirmed">確認済み</option>
                            <option value="attention">要注意</option>
                            <option value="not_applicable">対象外</option>
                          </select>
                        </label>
                        <label>
                          offline記録
                          <textarea
                            name="offline_notes"
                            maxLength={4000}
                            required
                          />
                        </label>
                        <button type="submit">端末queueへ保存</button>
                      </form>
                    )}
                    <div className="offline-queue-status" aria-live="polite">
                      <span>pending / conflict: {offlineQueue.length}</span>
                      <button
                        type="button"
                        disabled={
                          !offlineQueue.some(
                            (item) => item.status === "pending",
                          )
                        }
                        onClick={() => void syncOfflineQueue()}
                      >
                        通信復帰後に同期
                      </button>
                    </div>
                    {offlineQueue.some(
                      (item) => item.status === "conflict",
                    ) && (
                      <div className="service-warning">
                        <p>
                          競合はlast-write-winsで上書きしません。サーバー版と端末版を確認して解決します。
                        </p>
                        {offlineQueue
                          .filter((item) => item.status === "conflict")
                          .map((item) => (
                            <div key={item.client_operation_id}>
                              <code>{item.conflict_id}</code>
                              <button
                                type="button"
                                onClick={() =>
                                  void resolveOfflineConflict(
                                    item,
                                    "use_server",
                                  )
                                }
                              >
                                サーバー版を採用
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  void resolveOfflineConflict(
                                    item,
                                    "use_client",
                                  )
                                }
                              >
                                端末版を採用
                              </button>
                            </div>
                          ))}
                      </div>
                    )}
                  </section>

                  <form className="case-form" onSubmit={attachmentSubmit}>
                    <h3>現地添付</h3>
                    <p>
                      画像・PDF等を最大25 MiB、初期値restrictedで保存します。
                    </p>
                    <label>
                      ファイル
                      <input
                        name="attachment"
                        type="file"
                        accept="image/jpeg,image/png,image/webp,application/pdf,text/plain,text/csv,application/json,application/geo+json"
                        required
                      />
                    </label>
                    <button type="submit">添付を保存</button>
                    <small>
                      {attachmentIds.length}件を次の現地観察へ関連付け
                    </small>
                  </form>

                  <form className="case-form" onSubmit={fieldSubmit}>
                    <h3>現地観察</h3>
                    <label>
                      観察種別
                      <input
                        name="observation_type"
                        required
                        defaultValue="access_check"
                      />
                    </label>
                    <label>
                      記録
                      <textarea name="notes" required />
                    </label>
                    <button type="submit">現地記録を追加</button>
                  </form>
                  {fieldStatus && (
                    <p className="field-status" role="status">
                      {fieldStatus}
                    </p>
                  )}
                </div>
              )}
              {canReview && investigation?.status === "decision_pending" && (
                <form className="case-form decision" onSubmit={decisionSubmit}>
                  <h3>Decision Record</h3>
                  <label>
                    Review
                    <select name="review_request_id" required>
                      {reviews
                        .filter((review) => review.status === "reviewed")
                        .map((review) => (
                          <option
                            key={String(review.id)}
                            value={String(review.id)}
                          >
                            Reviewed · {formatDate(review.reviewed_at)}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    判断
                    <select name="decision">
                      <option value="adopted">adopted</option>
                      <option value="on_hold">on hold</option>
                      <option value="rejected">rejected</option>
                      <option value="additional_investigation">
                        additional investigation
                      </option>
                    </select>
                  </label>
                  <label>
                    理由
                    <textarea name="reason" required />
                  </label>
                  <label>
                    Evidence ID（カンマ区切り）
                    <input name="evidence_ids" required />
                  </label>
                  <button type="submit">人の判断として記録</button>
                </form>
              )}
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function EvidencePage({
  snapshot,
  roles,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const datasets = snapshot.cityHome?.datasets ?? [];
  const city = snapshot.cityHome?.city.city_key;
  const canCreate = permits(roles, ["planner"]);
  const [reportType, setReportType] = useState("data_quality");
  const createReport = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!city) return;
    const data = new FormData(event.currentTarget);
    void mutate(
      `/api/v1/cities/${encodeURIComponent(city)}/reports`,
      "POST",
      {
        report_type: reportType,
        title: data.get("title"),
        investigation_id:
          reportType === "investigation" ? data.get("subject_id") : null,
        scenario_comparison_id:
          reportType === "scenario_comparison" ? data.get("subject_id") : null,
        data_classification: data.get("data_classification"),
      },
      "保存済み記録からReportを生成しました",
    );
  };
  return (
    <>
      <PageHeader
        eyebrow="EVIDENCE CENTER"
        title="根拠・検証・Report"
        description="出典、version、アルゴリズム、検証、現地記録、Decision Recordを再現可能なmanifestへまとめます。"
      />
      {canCreate && city && (
        <form className="service-form report-form" onSubmit={createReport}>
          <label>
            Report種別
            <select
              name="report_type"
              value={reportType}
              onChange={(event) => setReportType(event.target.value)}
            >
              <option value="data_quality">Data Quality</option>
              <option value="investigation">Investigation</option>
              <option value="scenario_comparison">Scenario Comparison</option>
              <option value="annual_change">Annual Change</option>
              <option value="resilience_review">Resilience Review</option>
            </select>
          </label>
          <label>
            タイトル
            <input name="title" required maxLength={500} />
          </label>
          {(reportType === "investigation" ||
            reportType === "scenario_comparison") && (
            <label>
              対象ID
              <input name="subject_id" required />
            </label>
          )}
          <label>
            データ分類
            <select name="data_classification" defaultValue="internal">
              <option value="internal">internal</option>
              <option value="restricted">restricted</option>
              {reportType === "data_quality" && (
                <option value="public">public（public入力のみ）</option>
              )}
            </select>
          </label>
          <button className="primary-action" type="submit">
            決定論的Reportを生成
          </button>
        </form>
      )}
      <div className="service-evidence-grid">
        <section className="service-panel">
          <header>
            <div>
              <span>SOURCE LINEAGE</span>
              <h2>現在参照するデータ</h2>
            </div>
          </header>
          {datasets.length === 0 ? (
            <ServiceEmpty
              title="根拠対象データがありません"
              detail="Data Hubでpromotedになった実データだけがEvidenceの入力になります。"
            />
          ) : (
            datasets.map((dataset) => (
              <article className="evidence-source" key={dataset.version_id}>
                <StatusChip value={dataset.data_classification} />
                <div>
                  <strong>
                    {dataset.title} · {dataset.dataset_year}
                  </strong>
                  <small>
                    {dataset.dataset_key} / {dataset.version_key} ·{" "}
                    {dataset.quality_status}
                  </small>
                </div>
              </article>
            ))
          )}
        </section>
        <section className="service-panel">
          <header>
            <div>
              <span>EXPORT BOUNDARY</span>
              <h2>公開と内部の分離</h2>
            </div>
          </header>
          <div className="evidence-policy">
            <strong>Internal</strong>
            <p>
              担当者、コメント、現地添付、内部Decision、restrictedデータを含められます。
            </p>
            <strong>Public</strong>
            <p>
              public分類の集計・出典・検証済み成果だけを含み、個人情報・内部注記を除外します。
            </p>
          </div>
        </section>
      </div>
      <section className="service-panel full evidence-library">
        <header>
          <div>
            <span>REPORT LIBRARY</span>
            <h2>保存済みReport</h2>
          </div>
        </header>
        <ServiceTable
          caption="保存済みReport"
          empty="Reportはまだ生成されていません"
          rows={
            (snapshot.evidence?.reports ?? []) as unknown as Array<
              Record<string, unknown>
            >
          }
          rowKey={(row) => String(row.id)}
          columns={[
            { key: "title", label: "Report" },
            { key: "report_type", label: "種別" },
            {
              key: "data_classification",
              label: "分類",
              render: (row) => (
                <StatusChip value={String(row.data_classification)} />
              ),
            },
            { key: "generator_version", label: "Generator" },
            {
              key: "artifact_sha256",
              label: "SHA-256",
              render: (row) => String(row.artifact_sha256).slice(0, 12),
            },
            {
              key: "created_at",
              label: "生成",
              render: (row) => formatDate(row.created_at),
            },
            {
              key: "artifact",
              label: "Artifact",
              render: (row) => (
                <a
                  className="table-action"
                  href={serviceApi.url(
                    `/api/v1/reports/${String(row.id)}/artifact`,
                  )}
                >
                  JSON
                </a>
              ),
            },
            {
              key: "export",
              label: "Export記録",
              render: (row) =>
                canCreate ? (
                  <button
                    className="table-action"
                    type="button"
                    onClick={() =>
                      void mutate(
                        `/api/v1/reports/${String(row.id)}/exports`,
                        "POST",
                        { export_scope: "internal" },
                        "内部Export記録を作成しました",
                      )
                    }
                  >
                    internal
                  </button>
                ) : (
                  <span>—</span>
                ),
            },
          ]}
        />
      </section>
      <div className="service-two-column evidence-records">
        <section className="service-panel">
          <header>
            <div>
              <span>MANIFESTS</span>
              <h2>Evidence Center V2</h2>
            </div>
          </header>
          {(snapshot.evidence?.evidence_centers ?? []).length === 0 ? (
            <ServiceEmpty
              title="Evidence Manifestはありません"
              detail="出典、アルゴリズム、検証、現地記録、Decisionを保存すると表示されます。"
            />
          ) : (
            snapshot.evidence?.evidence_centers.map((item) => (
              <article className="evidence-source" key={item.id}>
                <StatusChip value={item.data_classification} />
                <div>
                  <strong>{item.manifest_sha256.slice(0, 16)}…</strong>
                  <small>
                    schema {item.schema_version ?? "1.0.0"} · integrity{" "}
                    {item.reproducibility_status ?? "recorded"} · field{" "}
                    {item.field_evidence_count} · decision {item.decision_count} ·{" "}
                    {formatDate(item.created_at)}
                  </small>
                  <a
                    href={serviceApi.url(`/api/v1/evidence-centers/${item.id}`)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    manifest詳細
                  </a>
                </div>
              </article>
            ))
          )}
        </section>
        <section className="service-panel">
          <header>
            <div>
              <span>VALIDATION</span>
              <h2>検証履歴</h2>
            </div>
          </header>
          {(snapshot.evidence?.validation_runs ?? []).length === 0 ? (
            <ServiceEmpty
              title="検証履歴はありません"
              detail="実行済みの一次モデルと参照モデルの比較だけを表示します。"
            />
          ) : (
            snapshot.evidence?.validation_runs.map((item) => (
              <article className="evidence-source" key={item.id}>
                <StatusChip value={item.validation_status} />
                <div>
                  <strong>{item.claim_key}</strong>
                  <small>
                    {item.method_key} · {item.algorithm_version} ·{" "}
                    {formatDate(item.generated_at)}
                  </small>
                </div>
              </article>
            ))
          )}
        </section>
      </div>
      <div className="service-boundary-note">
        <strong>決定論的Report</strong>
        <p>
          Reportは保存済みのversion付き入力とmanifestから再生成し、artifact
          SHA-256を記録します。画面表示の都合で数値や出典を作りません。
        </p>
      </div>
    </>
  );
}

function OperationsPage({
  snapshot,
  roles,
  mutate,
}: {
  snapshot: ServiceSnapshot;
  roles: ProductRole[];
  mutate: (
    path: string,
    method: "POST" | "PATCH",
    body: unknown,
    success: string,
  ) => Promise<boolean>;
}) {
  const operations = snapshot.operations;
  const canOperate = permits(roles, ["administrator"]);
  if (!operations)
    return (
      <>
        <PageHeader
          eyebrow="OPERATIONS"
          title="サービス運用"
          description="Job、データ更新、backup記録、release versionを確認します。"
        />
        <ServiceEmpty
          title="このRoleでは運用情報を表示できません"
          detail="Data ManagerまたはAdministratorの権限が必要です。"
        />
      </>
    );

  const jobOperation = (
    jobId: string,
    action: "retry" | "cancel",
    expectedState: "failed" | "queued",
  ) => {
    if (
      action === "cancel" &&
      !window.confirm("未実行のJobをcancelします。処理を続けますか？")
    )
      return;
    void mutate(
      `/api/v1/jobs/${jobId}/operations`,
      "POST",
      {
        action,
        expected_state: expectedState,
        reason:
          action === "retry"
            ? "Operations画面で失敗内容を確認して再実行"
            : "Operations画面で入力条件を再確認するためcancel",
        cancel_confirmation: action === "cancel" ? "cancel" : null,
      },
      action === "retry"
        ? "Jobを再実行待ちに戻しました"
        : "Jobをcancelしました",
    );
  };

  const membershipSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void mutate(
      "/api/v1/organizations/current/memberships",
      "POST",
      {
        issuer: data.get("issuer"),
        subject: data.get("subject"),
        display_name: data.get("display_name"),
        email: data.get("email") || null,
        role: data.get("role"),
      },
      "IdP identityへ組織Roleを登録しました",
    );
  };

  const membershipStatus = (userId: string, role: string, active: boolean) => {
    void mutate(
      `/api/v1/organizations/current/memberships/${userId}/${role}`,
      "PATCH",
      {
        expected_active: active,
        proposed_active: !active,
        note: "AdministratorがIdP identityと担当を確認して変更",
      },
      active ? "組織Roleを無効にしました" : "組織Roleを有効にしました",
    );
  };

  const configurationSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const key = String(data.get("config_key"));
    const valueInput = event.currentTarget.elements.namedItem(
      "config_value",
    ) as HTMLInputElement;
    let value: unknown;
    try {
      value = JSON.parse(valueInput.value);
      valueInput.setCustomValidity("");
    } catch {
      valueInput.setCustomValidity("有効なJSON値を入力してください");
      valueInput.reportValidity();
      return;
    }
    const existing = operations.overview.configuration.find(
      (item) => item.config_key === key,
    );
    void mutate(
      `/api/v1/organizations/current/configuration/${encodeURIComponent(key)}`,
      "PATCH",
      {
        expected_updated_at: existing?.updated_at ?? null,
        config_value: value,
        note: "Administratorが非secret設定値を確認して更新",
      },
      "Organization設定を更新しました",
    );
  };

  const retentionSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const resourceType = String(data.get("resource_type"));
    const existing = operations.overview.retention_policies.find(
      (item) => item.resource_type === resourceType,
    );
    const rawDays = String(data.get("retention_days") ?? "").trim();
    void mutate(
      `/api/v1/organizations/current/retention-policies/${encodeURIComponent(resourceType)}`,
      "PATCH",
      {
        expected_retention_days: existing?.retention_days ?? null,
        proposed_retention_days: rawDays ? Number(rawDays) : null,
        legal_hold_supported: false,
        note: "Administratorが保持期間の方針記録を更新",
      },
      "保持方針を記録しました（自動削除は未実装）",
    );
  };

  return (
    <>
      <PageHeader
        eyebrow="OPERATIONS"
        title="サービス運用"
        description="内部Job名は運用担当だけに表示し、進捗は実Stageで確認します。架空の進捗率は使いません。"
      />
      <div className="service-kpis operations-kpis">
        {(["queued", "running", "failed", "cancelled"] as const).map(
          (state) => (
            <button type="button" key={state}>
              <span>{state.toUpperCase()}</span>
              <strong>{operations.overview.jobs[state] ?? 0}</strong>
              <small>Job</small>
            </button>
          ),
        )}
      </div>
      <section className="service-panel full">
        <header>
          <div>
            <span>JOB OPERATIONS</span>
            <h2>実行履歴</h2>
          </div>
        </header>
        <ServiceTable
          caption="Job実行履歴"
          empty="Job履歴はありません"
          rows={operations.jobs as unknown as Array<Record<string, unknown>>}
          rowKey={(row) => String(row.id)}
          columns={[
            { key: "city_name", label: "都市" },
            {
              key: "job_type",
              label: "処理",
              render: (row) => String(row.job_type).replaceAll("_", " "),
            },
            {
              key: "state",
              label: "状態",
              render: (row) => <StatusChip value={String(row.state)} />,
            },
            { key: "current_stage", label: "現在Stage" },
            { key: "algorithm_version", label: "Algorithm" },
            {
              key: "queued_at",
              label: "登録",
              render: (row) => formatDate(row.queued_at),
            },
            {
              key: "action",
              label: "操作",
              render: (row) => {
                if (!canOperate) return <span>—</span>;
                if (row.state === "failed")
                  return (
                    <button
                      className="table-action"
                      type="button"
                      onClick={() =>
                        jobOperation(String(row.id), "retry", "failed")
                      }
                    >
                      retry
                    </button>
                  );
                if (row.state === "queued")
                  return (
                    <button
                      className="table-action destructive"
                      type="button"
                      onClick={() =>
                        jobOperation(String(row.id), "cancel", "queued")
                      }
                    >
                      cancel
                    </button>
                  );
                return <span>—</span>;
              },
            },
          ]}
        />
      </section>
      {canOperate && (
        <section className="service-panel full">
          <header>
            <div>
              <span>ORGANIZATION ACCESS</span>
              <h2>利用者と6 Role</h2>
            </div>
          </header>
          <form
            className="service-form member-form"
            onSubmit={membershipSubmit}
          >
            <label>
              OIDC issuer
              <input name="issuer" type="url" required />
            </label>
            <label>
              Subject
              <input name="subject" required maxLength={500} />
            </label>
            <label>
              表示名
              <input name="display_name" required maxLength={300} />
            </label>
            <label>
              Email（任意）
              <input name="email" type="email" />
            </label>
            <label>
              Role
              <select name="role" defaultValue="viewer">
                {Object.entries(ROLE_LABELS).map(([role, label]) => (
                  <option key={role} value={role}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <button className="primary-action" type="submit">
              Directory identityを登録
            </button>
          </form>
          <ServiceTable
            caption="組織membership"
            empty="登録済みmembershipはありません"
            rows={
              operations.memberships as unknown as Array<
                Record<string, unknown>
              >
            }
            rowKey={(row) => `${String(row.user_id)}:${String(row.role)}`}
            columns={[
              { key: "display_name", label: "利用者" },
              { key: "email", label: "Email" },
              { key: "role", label: "Role" },
              {
                key: "active",
                label: "状態",
                render: (row) => (
                  <StatusChip value={row.active ? "active" : "inactive"} />
                ),
              },
              {
                key: "membership_action",
                label: "操作",
                render: (row) => (
                  <button
                    className="table-action"
                    type="button"
                    onClick={() =>
                      membershipStatus(
                        String(row.user_id),
                        String(row.role),
                        Boolean(row.active),
                      )
                    }
                  >
                    {row.active ? "disable" : "enable"}
                  </button>
                ),
              },
            ]}
          />
          <p className="service-panel-note">
            招待メールは送信しません。実在するIdP issuer /
            subjectを登録し、OIDC検証とactive
            membershipの両方が一致した場合だけ利用できます。
          </p>
        </section>
      )}
      {canOperate && (
        <section className="service-panel full">
          <header>
            <div>
              <span>IMMUTABLE AUDIT</span>
              <h2>監査イベント</h2>
            </div>
          </header>
          <ServiceTable
            caption="組織スコープの監査イベント"
            empty="監査イベントはありません"
            rows={
              operations.auditEvents as unknown as Array<
                Record<string, unknown>
              >
            }
            rowKey={(row) => String(row.id)}
            columns={[
              { key: "actor", label: "Actor" },
              { key: "action", label: "Action" },
              { key: "resource_type", label: "Resource" },
              { key: "resource_id", label: "Resource ID" },
              { key: "request_id", label: "Request ID" },
              {
                key: "occurred_at",
                label: "時刻",
                render: (row) => formatDate(row.occurred_at),
              },
            ]}
          />
        </section>
      )}
      {canOperate && (
        <section className="service-panel full">
          <header>
            <div>
              <span>ORGANIZATION SETTINGS</span>
              <h2>非secret設定と保持方針</h2>
            </div>
          </header>
          <div className="service-two-column organization-settings">
            <div>
              <form className="case-form" onSubmit={configurationSubmit}>
                <h3>Organization設定</h3>
                <label>
                  設定項目
                  <select name="config_key" defaultValue="timezone">
                    <option value="timezone">timezone</option>
                    <option value="locale">locale</option>
                    <option value="default_data_classification">
                      default data classification
                    </option>
                    <option value="default_map_basemap">
                      default map basemap
                    </option>
                    <option value="field_offline_expiry_hours">
                      field offline expiry hours
                    </option>
                    <option value="annual_update_algorithm_version">
                      annual update algorithm version
                    </option>
                  </select>
                </label>
                <label>
                  JSON値
                  <input
                    name="config_value"
                    defaultValue='"Asia/Tokyo"'
                    maxLength={16384}
                    required
                  />
                </label>
                <button type="submit">設定を保存</button>
              </form>
              <ServiceTable
                caption="Organization設定"
                empty="Organization設定はありません"
                rows={
                  operations.overview.configuration as unknown as Array<
                    Record<string, unknown>
                  >
                }
                rowKey={(row) => String(row.config_key)}
                columns={[
                  { key: "config_key", label: "設定" },
                  {
                    key: "config_value",
                    label: "値",
                    render: (row) => JSON.stringify(row.config_value),
                  },
                  { key: "updated_by", label: "更新者" },
                  {
                    key: "updated_at",
                    label: "更新",
                    render: (row) => formatDate(row.updated_at),
                  },
                ]}
              />
            </div>
            <div>
              <form className="case-form" onSubmit={retentionSubmit}>
                <h3>保持方針</h3>
                <label>
                  Resource
                  <select name="resource_type" defaultValue="attachment">
                    <option value="audit">audit</option>
                    <option value="field_observation">field observation</option>
                    <option value="attachment">attachment</option>
                    <option value="job">job</option>
                  </select>
                </label>
                <label>
                  保持日数（未決定は空欄）
                  <input
                    name="retention_days"
                    type="number"
                    min="1"
                    max="36500"
                  />
                </label>
                <button type="submit">方針を記録</button>
              </form>
              <ServiceTable
                caption="保持方針"
                empty="保持方針は未決定です"
                rows={
                  operations.overview.retention_policies as unknown as Array<
                    Record<string, unknown>
                  >
                }
                rowKey={(row) => String(row.resource_type)}
                columns={[
                  { key: "resource_type", label: "Resource" },
                  {
                    key: "retention_days",
                    label: "保持日数",
                    render: (row) =>
                      row.retention_days == null
                        ? "未決定"
                        : `${String(row.retention_days)}日`,
                  },
                  { key: "configured_by", label: "更新者" },
                  {
                    key: "configured_at",
                    label: "更新",
                    render: (row) => formatDate(row.configured_at),
                  },
                ]}
              />
            </div>
          </div>
          <p className="service-panel-note">
            secret・password・token・credential・private
            keyは保存できません。保持期間は方針記録であり、自動削除workerとlegal
            holdは未実装です。
          </p>
        </section>
      )}
      <div className="service-two-column operations-records">
        <section className="service-panel">
          <header>
            <div>
              <span>BACKUP RECORDS</span>
              <h2>Backup / Restore</h2>
            </div>
          </header>
          {operations.overview.backups.length === 0 ? (
            <ServiceEmpty
              title="tenant backup記録はありません"
              detail="実行はdeployment operator境界です。復元後はintegrity validationを記録します。"
            />
          ) : (
            operations.overview.backups.map((backup) => (
              <article className="quality-row" key={String(backup.id)}>
                <StatusChip value={String(backup.status)} />
                <div>
                  <strong>{String(backup.backup_type)}</strong>
                  <small>{formatDate(backup.started_at)}</small>
                </div>
              </article>
            ))
          )}
        </section>
        <section className="service-panel">
          <header>
            <div>
              <span>RELEASE</span>
              <h2>Versionと移行計画</h2>
            </div>
          </header>
          {operations.overview.releases.map((release) => (
            <article className="quality-row" key={String(release.version)}>
              <StatusChip value={String(release.release_status)} />
              <div>
                <strong>{String(release.version)}</strong>
                <small>
                  DB {String(release.migration_version)} · Frontend{" "}
                  {String(release.frontend_asset_version)}
                </small>
              </div>
            </article>
          ))}
        </section>
      </div>
      <div className="service-boundary-note">
        <strong>SLO / cancellation boundary</strong>
        <p>
          測定基盤はSLAを断定しません。APIから安全にcancelできるのはqueued
          Jobだけです。running
          processは運用者が実行環境で停止し、監査記録を残します。
        </p>
      </div>
    </>
  );
}
