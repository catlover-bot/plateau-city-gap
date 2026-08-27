import { useEffect, useMemo, useState } from "react";

type AdminRecord = Record<string, unknown>;

export interface AdminSnapshot {
  cities: AdminRecord[];
  datasets: AdminRecord[];
  capabilities: AdminRecord[];
  networks: AdminRecord[];
  jobs: AdminRecord[];
  users: AdminRecord[];
}

export interface PilotReadiness {
  status: "READY" | "READY_WITH_LIMITATIONS" | "NOT_READY";
  blockers: string[];
  limitations: string[];
  checks: Array<{
    name: string;
    passed: boolean;
    required: boolean;
    detail: string;
  }>;
}

interface MunicipalAdminProps {
  cityId: "maizuru" | "fujisawa";
  initialSnapshot?: AdminSnapshot;
  initialReadiness?: PilotReadiness;
}

const EMPTY_SNAPSHOT: AdminSnapshot = {
  cities: [], datasets: [], capabilities: [], networks: [], jobs: [], users: []
};

function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.map((item) => {
    if (typeof item === "object" && item !== null && "role" in item) {
      const role = String((item as AdminRecord).role);
      const city = (item as AdminRecord).city_code;
      return city ? `${role} (${String(city)})` : role;
    }
    return String(item);
  }).join(", ") || "—";
  return String(value);
}

function Status({ value }: { value: unknown }) {
  const label = text(value);
  const normalized = label.toLowerCase().replaceAll("_", "-");
  return <span className={`admin-status ${normalized}`}>{label}</span>;
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <section className="admin-section">
      <header><h2>{title}</h2><span>{count}</span></header>
      {children}
    </section>
  );
}

export function MunicipalAdmin({ cityId, initialSnapshot, initialReadiness }: MunicipalAdminProps) {
  const [snapshot, setSnapshot] = useState<AdminSnapshot | null>(initialSnapshot ?? null);
  const [readiness, setReadiness] = useState<PilotReadiness | null>(initialReadiness ?? null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const apiBase = String(import.meta.env.VITE_CITYGAP_API_URL ?? "/api").replace(/\/$/, "");
  const cityCode = cityId === "maizuru" ? "26202" : "14205";

  useEffect(() => {
    if (initialSnapshot && initialReadiness) return;
    const abort = new AbortController();
    setError(null);
    Promise.all([
      fetch(`${apiBase}/admin/snapshot`, { credentials: "include", signal: abort.signal }),
      fetch(`${apiBase}/admin/pilot-readiness/${cityCode}`, { credentials: "include", signal: abort.signal })
    ]).then(async ([snapshotResponse, readinessResponse]) => {
      if (!snapshotResponse.ok || !readinessResponse.ok) {
        throw new Error(`管理APIへ接続できません (${snapshotResponse.status}/${readinessResponse.status})`);
      }
      setSnapshot(await snapshotResponse.json() as AdminSnapshot);
      setReadiness(await readinessResponse.json() as PilotReadiness);
    }).catch((reason: unknown) => {
      if (!abort.signal.aborted) {
        setError(reason instanceof Error ? reason.message : "管理APIへ接続できません");
      }
    });
    return () => abort.abort();
  }, [apiBase, cityCode, initialReadiness, initialSnapshot, retry]);

  const data = snapshot ?? EMPTY_SNAPSHOT;
  const cityDatasets = useMemo(
    () => data.datasets.filter((item) => text(item.city_code) === cityCode),
    [cityCode, data.datasets]
  );
  const cityCapabilities = useMemo(
    () => data.capabilities.filter((item) => text(item.city_code) === cityCode),
    [cityCode, data.capabilities]
  );

  return (
    <main className="municipal-admin" aria-label="CITY GAP自治体管理">
      <div className="admin-heading">
        <div><p>MUNICIPAL PLATFORM · AUTHENTICATED</p><h1>運用状況</h1></div>
        {readiness && <Status value={readiness.status} />}
      </div>
      <p className="admin-boundary">OIDCで認証された管理者向けです。公開デモ資産から詳細データを読み込まず、PostGIS管理APIの現在値だけを表示します。</p>

      {error && (
        <div className="admin-error" role="alert">
          <strong>管理データを表示できません</strong><span>{error}</span>
          <small>VITE_CITYGAP_API_URL、OIDCセッション、administrator権限を確認してください。</small>
          <button type="button" onClick={() => setRetry((value) => value + 1)}>再接続</button>
        </div>
      )}
      {!snapshot && !error && <div className="admin-loading" role="status">管理APIを確認中…</div>}

      {readiness && (
        <Section title="Pilot Readiness" count={readiness.checks.length}>
          <div className="admin-check-grid">
            {readiness.checks.map((check) => (
              <div key={check.name}>
                <Status value={check.passed ? "passed" : check.required ? "blocker" : "limitation"} />
                <strong>{check.name}</strong><small>{check.detail}</small>
              </div>
            ))}
          </div>
        </Section>
      )}

      {snapshot && <>
        <Section title="Cities" count={data.cities.length}>
          <div className="admin-card-grid">{data.cities.map((city) => <article key={text(city.city_code)}><strong>{text(city.name)}</strong><span>{text(city.city_code)} · {text(city.analysis_crs)}</span><small>{text(city.prefecture)}</small></article>)}</div>
        </Section>
        <Section title="Datasets / Versions" count={cityDatasets.length}>
          <div className="admin-table-wrap"><table><thead><tr><th>Dataset</th><th>Version</th><th>検証</th><th>Lifecycle</th><th>Quality</th><th>Analysis</th></tr></thead><tbody>{cityDatasets.map((dataset) => <tr key={text(dataset.dataset_version_id)}><td><strong>{text(dataset.title)}</strong><small>{text(dataset.dataset_key)}</small></td><td>{text(dataset.version_key)}</td><td><Status value={dataset.verification_status} /></td><td><Status value={dataset.lifecycle_status} /></td><td><Status value={dataset.quality_status} /></td><td><Status value={dataset.analysis_ready ? "ready" : "not-ready"} /></td></tr>)}</tbody></table></div>
        </Section>
        <Section title="Capabilities" count={cityCapabilities.length}>
          <div className="admin-capabilities">{cityCapabilities.map((capability) => <div key={text(capability.capability)}><strong>{text(capability.capability)}</strong><Status value={capability.status} /><small>{text(capability.note)}</small></div>)}</div>
        </Section>
        <Section title="Network Versions" count={data.networks.length}>
          <div className="admin-table-wrap"><table><thead><tr><th>City</th><th>Graph</th><th>Source</th><th>Type</th><th>Nodes</th><th>Edges</th></tr></thead><tbody>{data.networks.map((network) => <tr key={text(network.network_version_id)}><td>{text(network.city_code)}</td><td>{text(network.graph_version)}</td><td><Status value={network.source_type} /></td><td>{text(network.network_type)}</td><td>{text(network.node_count)}</td><td>{text(network.edge_count)}</td></tr>)}</tbody></table></div>
        </Section>
        <Section title="Jobs" count={data.jobs.length}>
          <div className="admin-table-wrap"><table><thead><tr><th>City</th><th>Job</th><th>State</th><th>Stage</th><th>Retry</th></tr></thead><tbody>{data.jobs.map((job) => <tr key={text(job.job_id)}><td>{text(job.city_code)}</td><td>{text(job.job_type)}</td><td><Status value={job.state} /></td><td>{text(job.stage)}</td><td>{text(job.retry_count)} / {text(job.max_retries)}</td></tr>)}</tbody></table></div>
        </Section>
        <Section title="Users / Roles" count={data.users.length}>
          <div className="admin-table-wrap"><table><thead><tr><th>User</th><th>Issuer</th><th>Roles</th><th>Active</th></tr></thead><tbody>{data.users.map((user) => <tr key={text(user.user_id)}><td><strong>{text(user.display_name)}</strong><small>{text(user.email)}</small></td><td>{text(user.issuer)}</td><td>{text(user.roles)}</td><td><Status value={user.active ? "active" : "disabled"} /></td></tr>)}</tbody></table></div>
        </Section>
      </>}
    </main>
  );
}
