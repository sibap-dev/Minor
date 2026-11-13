import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, ArrowRight, ArrowUpRight, BarChart3, Bell, CheckCircle2, ChevronDown,
  Monitor,
  CircleHelp, Cpu, Database, Download, FileSpreadsheet, Gauge, HardDrive,
  Info, LayoutDashboard, Layers, Menu, Network, Play, PlayCircle, RefreshCw,
  Search, Settings, ShieldCheck, SlidersHorizontal, Square, Users, Wifi, X
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import { get, post, formatPercent, formatNumber } from "./api";
import { datasetFiles, clientProfiles, workflowSteps } from "./data";

const nav = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Dataset", icon: Database },
  { label: "IoT Clients", icon: Users },
  { label: "Client Selection", icon: ShieldCheck },
  { label: "Federated Learning", icon: Activity },
  { label: "Experiments & Results", icon: BarChart3 },
  { label: "Advanced Configuration", icon: SlidersHorizontal }
];

const STRATEGY_LABELS = {
  all: "All clients",
  random: "Random",
  resource: "Resource-aware",
  context: "Context-aware"
};

const DEFAULT_SELECTION = {
  scenario: "iid",
  strategy: "context",
  seed: 42,
  round: 0,
  numSelect: 3,
  minAvailability: 0.5,
  maxCpuPercent: 95,
  minMemoryAvailableMb: 128,
  maxDiskPercent: 98,
  maxLatencyMs: 1000,
  maxPacketLossPercent: 50,
  weights: { resource: 0.30, network: 0.20, data: 0.25, fairness: 0.15, cost: 0.10 }
};

const DEFAULT_TRAINING = {
  name: "",
  rounds: 2,
  localEpochs: 1,
  batchSize: 256,
  learningRate: 0.001,
  validationFraction: 0.1,
  maxSamplesPerClient: "",
  classWeightMode: "none",
  numThreads: 4
};

function InfoTip({ text }) {
  if (!text) return null;
  return <span className="info-tip" title={text} aria-label={text}><Info size={13} /></span>;
}

function Provenance({ label, title }) {
  const value = label || "UNAVAILABLE";
  const cls = value.toLowerCase().replace(/[^a-z]+/g, "-");
  return <span className={`provenance provenance-${cls}`} title={title}>{value}</span>;
}

function MetricCard({ title, value, unit = "", change, icon: Icon, tone = "blue", foot, tip }) {
  return <article className="metric-card" title={tip}>
    <div className="metric-top"><span>{title} <InfoTip text={tip} /></span><span className={`metric-icon ${tone}`}><Icon size={18} /></span></div>
    <div className="metric-value">{value}<small>{unit}</small></div>
    <div className="metric-foot"><span className={change?.startsWith("+") ? "positive" : "neutral"}>{change}</span><span>{foot}</span></div>
  </article>;
}

function PanelTitle({ title, subtitle, action }) {
  return <div className="panel-title"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{action}</div>;
}

function StatusBadge({ status }) {
  const map = {
    running: "online",
    completed: "online",
    failed: "offline",
    cancelled: "offline",
    starting: "online"
  };
  const tone = map[status] || "offline";
  return <span className={`status-pill ${tone}`}><i />{status || "unknown"}</span>;
}

function safeNumber(value, fallback = "N/A") {
  if (value === null || value === undefined || value === "") return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function loadStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}

function WorkflowBar({ activeStep }) {
  return <div className="workflow-bar">
    {workflowSteps.map((step, index) => {
      const state = index < activeStep ? "done" : index === activeStep ? "active" : "pending";
      return <div key={step} className={`workflow-step ${state}`}>
        <span>{index + 1}</span><small>{step}</small>
      </div>;
    })}
  </div>;
}

function DatasetPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reports, setReports] = useState({ iid: null, non_iid: null });
  const [partitionError, setPartitionError] = useState("");
  const [mode, setMode] = useState("iid");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await get("/api/datasets/summary", { timeout: 10000 });
        if (!cancelled) setSummary(data);
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.message || err.message || "Dataset summary unavailable.");
      } finally {
        if (!cancelled) setLoading(false);
      }
      try {
        const [iid, nonIid] = await Promise.all([
          get("/data/partitions/iid/partition_report.json"),
          get("/data/partitions/non_iid/partition_report.json")
        ]);
        if (!cancelled) setReports({ iid, non_iid: nonIid });
      } catch {
        if (!cancelled) setPartitionError("Partition reports unavailable. Static reports must exist under public/data/partitions.");
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) return <section className="panel"><p>Loading dataset information...</p></section>;
  if (error || !summary?.train || !summary?.test) return <section className="panel"><h3>Dataset unavailable</h3><p>{error || "Unexpected dataset structure."}</p></section>;

  const train = summary.train;
  const test = summary.test;
  const total = train.rows + test.rows;
  const report = reports[mode];
  const clients = Object.entries(report?.clients || {});
  const classDistribution = Object.entries(train.class_distribution || {}).sort((a, b) => b[1] - a[1]);
  const chartData = clients.map(([id, details]) => ({ client: id, records: details.records, share: details.records / train.rows * 100 }));
  const missing = Object.values(train.missing_values || {}).reduce((sum, v) => sum + Number(v || 0), 0);

  return <>
    <section className="metric-grid">
      <MetricCard title="Dataset" value="CICIoT2023" icon={Database} tone="blue" foot="Static, verified report" tip="Dataset metadata comes from the saved inspection report." />
      <MetricCard title="Training samples" value={train.rows.toLocaleString()} icon={Layers} tone="green" foot={`${(train.rows / total * 100).toFixed(2)}% split`} />
      <MetricCard title="Testing samples" value={test.rows.toLocaleString()} icon={ShieldCheck} tone="purple" foot="Held out for final evaluation" />
      <MetricCard title="Features / classes" value={`${train.feature_count} / ${train.class_count}`} icon={Activity} tone="orange" foot="39 numeric features, 34 labels" />
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Train/test split" subtitle="Leakage-aware split preserved from dataset preparation" />
        <div className="dataset-split">
          <div><span>Training</span><b>{train.rows.toLocaleString()}</b><div className="meter"><i style={{ width: `${train.rows / total * 100}%` }} /></div><small>Used for partitioning and local training only</small></div>
          <div><span>Testing</span><b>{test.rows.toLocaleString()}</b><div className="meter"><i className="green" style={{ width: `${test.rows / total * 100}%` }} /></div><small>Never used in partitioning, selection or training</small></div>
        </div>
      </article>
      <article className="panel">
        <PanelTitle title="IID vs Non-IID comparison" subtitle="Saved partition reports, five logical clients" action={<div className="partition-switch"><button className={mode === "iid" ? "active" : ""} onClick={() => setMode("iid")}>IID</button><button className={mode === "non_iid" ? "active" : ""} onClick={() => setMode("non_iid")}>Non-IID</button></div>} />
        {partitionError ? <p className="partition-message partition-error">{partitionError}</p> : <>
          <div className="partition-summary">
            <div><span>Method</span><b>{report?.method?.toUpperCase() || mode.toUpperCase()}</b></div>
            <div><span>Dirichlet alpha</span><b>{report?.dirichlet_alpha ?? "Not used (IID)"}</b></div>
            <div><span>Explanation</span><b>{mode === "iid" ? "Class-proportional balanced allocation" : "Dirichlet alpha = 0.5 concentrates classes per client"}</b></div>
            <div><span>Records assigned once</span><b className="partition-valid">{report?.all_records_assigned_once ? "Yes" : "Unknown"}</b></div>
            <div><span>Clients</span><b>{Object.keys(report?.clients || {}).length || 5}</b></div>
          </div>
          <p className="dataset-note">IID distributes each class approximately evenly. Non-IID uses Dirichlet alpha = 0.5, so clients receive different class mixes. Partition artifacts are preserved; the dashboard does not repartition data.</p>
        </>}
      </article>
    </section>

    <section className="panel dataset-files">
      <PanelTitle title="Client-wise sample distribution" subtitle={`${mode.toUpperCase()} allocation across logical federated clients`} />
      {chartData.length > 0 && <div className="partition-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 20, left: 8, bottom: 4 }}>
        <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" horizontal={false} />
        <XAxis type="number" tick={{ fill: "#8795aa", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="client" width={70} tick={{ fill: "#b9c5d7", fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip formatter={(value, name, item) => [`${Number(value).toLocaleString()} (${item.payload.share.toFixed(2)}%)`, "Records"]} contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
        <Bar dataKey="records" fill={mode === "iid" ? "#5b8cff" : "#20c997"} radius={[0, 5, 5, 0]} />
      </BarChart></ResponsiveContainer></div>}
      <div className="table-scroll"><table><thead><tr><th>CLIENT</th><th>RECORDS</th><th>SHARE</th><th>CLASSES PRESENT</th></tr></thead><tbody>
        {clients.map(([id, details]) => <tr key={id}><td><b>{id}</b></td><td>{details.records.toLocaleString()}</td><td>{(details.records / train.rows * 100).toFixed(2)}%</td><td>{details.class_count} / {train.class_count}</td></tr>)}
      </tbody></table></div>
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Class distribution" subtitle="Top training classes from the saved dataset report" />
        <div className="chart-wrap small"><ResponsiveContainer width="100%" height="100%"><BarChart data={classDistribution.slice(0, 10).map(([label, count]) => ({ label: label.replace("DDOS-", "").replace("DOS-", ""), count }))} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#7f8ba3", fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={50} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#7f8ba3", fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Bar dataKey="count" fill="#5b8cff" radius={[4, 4, 0, 0]} />
        </BarChart></ResponsiveContainer></div>
        <details className="advanced-details"><summary>Show full class table</summary>
          <div className="table-scroll"><table><thead><tr><th>CLASS</th><th>TRAINING RECORDS</th></tr></thead><tbody>{classDistribution.map(([label, count]) => <tr key={label}><td>{label}</td><td>{Number(count).toLocaleString()}</td></tr>)}</tbody></table></div>
        </details>
      </article>
      <article className="panel">
        <PanelTitle title="Dataset validation status" subtitle="From saved inspection and partition reports" />
        <div className="validation-list">
          <div><CheckCircle2 size={16} />{train.feature_count} input features and one Label column</div>
          <div><CheckCircle2 size={16} />{train.class_count} classification classes</div>
          <div><CheckCircle2 size={16} />Training and testing splits available</div>
          <div><CheckCircle2 size={16} />{missing.toLocaleString()} missing values in training data</div>
          <div><CheckCircle2 size={16} />IID and Non-IID partition reports available</div>
          <div><CheckCircle2 size={16} />Partitioning uses training split only</div>
        </div>
        <p className="dataset-note">Validation status comes from prepared artifacts, not a live scan. Macro-F1 averages per-class F1, so rare classes remain visible despite class imbalance.</p>
      </article>
    </section>

    <section className="panel dataset-files">
      <PanelTitle title="Available dataset files" subtitle="Prepared CICIoT2023 artifacts" />
      <div className="table-scroll"><table><thead><tr><th>FILE</th><th>RECORDS</th><th>TYPE</th><th>PROVENANCE</th></tr></thead><tbody>
        {datasetFiles.map(file => <tr key={file.name}><td><div className="client-name"><div className="client-avatar"><FileSpreadsheet size={15} /></div><b>{file.name}</b></div></td><td>{file.records.toLocaleString()}</td><td>{file.type}</td><td><Provenance label="HISTORICAL" title="Previously prepared dataset file." /></td></tr>)}
      </tbody></table></div>
    </section>
  </>;
}

function OverviewPage({ overview, overviewError, timeseries, latestSelection, jobs, aggregate, simulation, onNavigate, onRefresh }) {
  const running = jobs.filter(job => job.status === "running" || job.status === "starting");
  const latestJob = jobs.length ? jobs[0] : null;
  const latestByScenario = aggregate.filter(row => row.scenario === "iid").sort((a, b) => b.test_accuracy_mean - a.test_accuracy_mean)[0];
  const resourceSeries = (timeseries.resource || []).map(row => ({ time: row.time, cpu: Number(row.cpu || 0), memory: Number(row.memory || 0) }));
  const networkSeries = (timeseries.network || []).map(row => ({ time: row.time, bandwidth: Number(row.bandwidth || 0), latency: Number(row.latency || 0) }));
  const managedClients = simulation?.clientCount ?? 5;
  const totalRegistered = overview?.totalClients ?? 0;
  const activeRegistered = overview?.activeClients ?? 0;
  const inactiveRegistered = overview?.inactiveClients ?? Math.max(0, totalRegistered - activeRegistered);
  const legacyRegistered = Math.max(0, totalRegistered - managedClients);
  const stageStatus = (index) => {
    if (index === 0) return "Preserved split";
    if (index === 1) return simulation?.running ? "Running" : "Stopped";
    if (index === 2) return latestSelection ? "Ready" : "Not executed";
    if (index === 3) return latestSelection ? "Ready" : "Not executed";
    if (index === 4) return running.length ? "Running" : latestJob ? latestJob.status : "Idle";
    if (index === 5) return latestJob?.status === "completed" ? "Completed" : "Pending";
    if (index === 6) return latestJob?.status === "completed" ? "Completed" : "Pending";
    return aggregate.length ? "Available" : "Unavailable";
  };

  return <>
    <WorkflowBar activeStep={latestSelection ? (running.length ? 4 : 3) : 1} />
    <section className="metric-grid">
      <MetricCard title="Total registered clients" value={totalRegistered || "N/A"} icon={Users} tone="blue" foot={`${activeRegistered} active, ${inactiveRegistered} inactive`} change={overviewError ? "API unavailable" : "Live DB"} tip="Counts every row in the clients table, including legacy test registrations." />
      <MetricCard title="Simulator-managed clients" value={managedClients} icon={Monitor} tone="green" foot={simulation?.running ? "Simulation running" : "Simulation stopped"} tip="These are the stable client_1 to client_5 profiles managed by the dashboard simulator." />
      <MetricCard title="Dataset" value="CICIoT2023" icon={Database} tone="green" foot="1,170,022 train / 290,874 test" tip="Static preserved split. No live repartitioning." />
      <MetricCard title="Latest training job" value={latestJob ? latestJob.status : "Idle"} icon={PlayCircle} tone="purple" foot={latestJob?.runId || "No dashboard training job"} tip="Filesystem-managed training jobs are separate from database experiment rows." />
      <MetricCard title="Latest verified accuracy" value={latestByScenario ? formatPercent(latestByScenario.test_accuracy_mean) : "N/A"} icon={ShieldCheck} tone="orange" foot={latestByScenario ? `IID ${STRATEGY_LABELS[latestByScenario.strategy]} (3 seeds)` : "Historical aggregate unavailable"} />
      <MetricCard title="Running jobs" value={running.length} icon={Activity} tone="orange" foot={running[0]?.runId || "None"} />
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Workflow status" subtitle="Compact research pipeline and current stage" />
        <div className="workflow-status-grid">
          {workflowSteps.map((step, index) => <div key={step} className="workflow-status-item"><b>{index + 1}. {step}</b><span className={`status-pill ${stageStatus(index) === "Completed" || stageStatus(index) === "Ready" || stageStatus(index) === "Running" ? "online" : "offline"}`}><i />{stageStatus(index)}</span></div>)}
        </div>
        <p className="dataset-note">Managed clients are `client_1` to `client_5`. Registered clients also include any older test registrations; {legacyRegistered} additional registered client{legacyRegistered === 1 ? "" : "s"} {legacyRegistered === 1 ? "is" : "are"} not simulator-managed.</p>
      </article>
      <article className="panel">
        <PanelTitle title="Current status" subtitle="Selection, training and data provenance" action={<button className="btn-secondary small" onClick={onRefresh}><RefreshCw size={14} /> Refresh</button>} />
        <div className="validation-list">
          <div><CheckCircle2 size={16} />Selection: {latestSelection ? `${STRATEGY_LABELS[latestSelection.strategy]} (${latestSelection.selected?.length || 0} selected)` : "none"}</div>
          <div><CheckCircle2 size={16} />Selection ID: {latestSelection?.selectionId || "N/A"}</div>
          <div><CheckCircle2 size={16} />Constraints relaxed: {latestSelection ? String(latestSelection.constraints_relaxed) : "N/A"}</div>
          <div><CheckCircle2 size={16} />Latest job: {latestJob ? `${latestJob.status} (${latestJob.runId})` : "none"}</div>
          <div><CheckCircle2 size={16} />Running jobs: {running.length}</div>
          <div><CheckCircle2 size={16} />Telemetry API: {overviewError ? "unavailable" : "connected"}</div>
        </div>
        <div className="heading-actions compact-actions">
          <button className="btn-secondary" onClick={() => onNavigate("Client Selection")}><ShieldCheck size={15} /> Selection</button>
          <button className="btn-primary" onClick={() => onNavigate("Federated Learning")}><PlayCircle size={15} /> Training</button>
        </div>
      </article>
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Resource telemetry" subtitle="Last 2 hours, 5-minute buckets from PostgreSQL" />
        {resourceSeries.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={resourceSeries} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "#7f8ba3", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: "#7f8ba3", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Area type="monotone" dataKey="cpu" name="CPU %" stroke="#5b8cff" fill="#5b8cff22" />
          <Area type="monotone" dataKey="memory" name="Memory %" stroke="#20c997" fill="#20c99722" />
        </AreaChart></ResponsiveContainer></div> : <p className="dataset-note">No live resource timeseries available. Start the simulator or agent and wait for samples.</p>}
      </article>
      <article className="panel">
        <PanelTitle title="Network bandwidth" subtitle="Average Mbps over recent 5-minute buckets" />
        {networkSeries.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={networkSeries} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "#7f8ba3", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#7f8ba3", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Line type="monotone" dataKey="bandwidth" name="Bandwidth Mbps" stroke="#5b8cff" strokeWidth={2.2} dot={false} />
        </LineChart></ResponsiveContainer></div> : <p className="dataset-note">No live network bandwidth samples available.</p>}
      </article>
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Network latency" subtitle="Average milliseconds over recent 5-minute buckets" />
        {networkSeries.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={networkSeries} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "#7f8ba3", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#7f8ba3", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Line type="monotone" dataKey="latency" name="Latency ms" stroke="#f59e0b" strokeWidth={2.2} dot={false} />
        </LineChart></ResponsiveContainer></div> : <p className="dataset-note">No live latency samples available.</p>}
      </article>
      <article className="panel">
        <PanelTitle title="Federated evaluation" subtitle="Measured results from the local experiment suite" action={<button className="btn-secondary small" onClick={() => onNavigate("Experiments & Results")}>Open results <ArrowUpRight size={14}/></button>} />
        <div className="activity-list">
          <div className="activity-item"><div className="activity-marker success"/><div><b>IID and Non-IID runs complete</b><p>Three seeds per strategy with full, random, resource-aware and context-aware selection.</p><small>See Experiments & Results for comparison tables and downloads.</small></div></div>
          <div className="activity-item"><div className="activity-marker info"/><div><b>Client allocation reports loaded</b><p>IID and Non-IID partition reports are available in Dataset.</p><small>Every training row is assigned exactly once.</small></div></div>
        </div>
      </article>
    </section>
  </>;
}

function IoTClientsPage({ clients, clientsError, simulation, onStart, onStop, onRefresh }) {
  const [query, setQuery] = useState("");
  const [selectedClient, setSelectedClient] = useState(null);
  const filtered = clients.filter(client => `${client.display_name} ${client.client_id} ${client.agent_mode}`.toLowerCase().includes(query.toLowerCase()));
  const selectedProfile = selectedClient ? clientProfiles.find(profile => profile.id === selectedClient.client_id || profile.id === selectedClient.display_name) : null;
  const selectedLastSeen = selectedClient?.last_seen_at ? new Date(selectedClient.last_seen_at) : null;

  return <>
    <section className="panel">
      <PanelTitle title="Client simulation controls" subtitle="Dashboard-managed simulator reuses cached registrations on restart" action={<div className="heading-actions">
        <button className="btn-secondary" onClick={onRefresh}><RefreshCw size={15} /> Refresh</button>
        <button className="btn-primary" onClick={onStart} disabled={simulation.running}><Play size={15} /> Start simulation</button>
        <button className="btn-secondary danger" onClick={onStop} disabled={!simulation.running}><Square size={15} /> Stop</button>
      </div>} />
      <div className="partition-summary">
        <div><span>Simulator process</span><b>{simulation.running ? "RUNNING" : "STOPPED"}</b></div>
        <div><span>Managed clients</span><b>{simulation.clientCount ?? 5}</b></div>
        <div><span>Interval</span><b>{simulation.intervalMs ?? 10000} ms</b></div>
        <div><span>Ingest API</span><b>{simulation.apiUrl || "configured by server"}</b></div>
      </div>
      <p className="dataset-note">Managed simulator clients are `client_1` to `client_5`. Registered clients may also include older test registrations. The simulator uses stable logical names and a local credential cache, so restarts reuse existing rows instead of creating duplicates. {simulation.error ? `Error: ${simulation.error}` : ""}</p>
    </section>

    <section className="panel dataset-files">
      <PanelTitle title="Configured client profiles" subtitle="Five heterogeneous logical clients used for context-aware experiments" />
      <div className="table-scroll"><table><thead><tr><th>CLIENT</th><th>PROFILE</th><th>CPU</th><th>MEMORY</th><th>LATENCY</th><th>BANDWIDTH</th><th>PACKET LOSS</th><th>AVAILABILITY</th><th>PROVENANCE</th></tr></thead><tbody>
        {clientProfiles.map(profile => <tr key={profile.id}><td><b>{profile.id}</b><div className="muted">{profile.label}</div></td><td>{profile.profile}</td><td>{profile.cpu}</td><td>{profile.memory}</td><td>{profile.latency}</td><td>{profile.bandwidth}</td><td>{profile.packetLoss}</td><td>{profile.availability}</td><td><Provenance label="SIMULATED" title="Profile defaults are simulated and used as reproducible client context." /></td></tr>)}
      </tbody></table></div>
      <p className="dataset-note">Configured profiles are reproducible defaults. Latest telemetry shows the most recent simulated sample for each registered client.</p>
    </section>

    <section className="panel clients-panel">
      <PanelTitle title="Registered IoT clients" subtitle="Latest telemetry sample per client from PostgreSQL. Click a row for details." />
      <div className="table-toolbar"><div className="search-box"><Search size={15} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search clients..." /></div></div>
      {clientsError ? <p className="partition-message partition-error">{clientsError}</p> : <div className="table-scroll"><table><thead><tr><th>CLIENT</th><th>TYPE</th><th>STATUS</th><th>CPU</th><th>MEMORY</th><th>LATENCY</th><th>BANDWIDTH</th><th>PACKET LOSS</th><th>AVAILABILITY</th><th>PROVENANCE</th></tr></thead><tbody>
        {filtered.map((client, index) => {
          const lastSeen = client.last_seen_at ? new Date(client.last_seen_at) : null;
          const online = lastSeen && Date.now() - lastSeen.getTime() < 5 * 60 * 1000;
          const provenance = client.agent_mode === "real_agent" ? "REAL" : "SIMULATED";
          return <tr key={client.client_id || index} className={selectedClient?.client_id === client.client_id ? "selected-row" : ""} onClick={() => setSelectedClient(client)} style={{ cursor: "pointer" }}>
            <td><div className="client-name"><div className={`client-avatar avatar-${index % 4}`}><Gauge size={15} /></div><div><b>{client.display_name}</b><small>{client.client_id}</small></div></div></td>
            <td><span className={`type-pill ${client.agent_mode === "simulated_agent" ? "sim" : "real"}`}>{client.agent_mode === "simulated_agent" ? "Simulated agent" : "Real agent"}</span></td>
            <td><span className={`status-pill ${online ? "online" : "offline"}`}><i />{online ? "Active" : "Inactive"}</span></td>
            <td>{safeNumber(client.cpu_percent, "N/A")}{client.cpu_percent == null ? "" : "%"}</td>
            <td>{formatNumber(client.memory_percent)}</td>
            <td>{formatNumber(client.latency_ms)} ms</td>
            <td>{formatNumber(client.bandwidth_mbps)} Mbps</td>
            <td>{formatNumber(client.packet_loss_percent)} %</td>
            <td>{formatNumber(client.availability_effective)} <Provenance label={client.availability_source === "derived_from_last_seen" ? "DERIVED" : "SIMULATED"} /></td>
            <td><Provenance label={provenance} title={client.source || provenance} /></td>
          </tr>;
        })}
      </tbody></table>{filtered.length === 0 && <div className="empty-state">No clients found.</div>}</div>}
    </section>

    {selectedClient && <section className="panel dataset-files">
      <PanelTitle title={`Client detail: ${selectedClient.display_name}`} subtitle="Configured profile, latest telemetry, availability and provenance" action={<button className="btn-secondary small" onClick={() => setSelectedClient(null)}>Close</button>} />
      <div className="partition-summary">
        <div><span>Client ID</span><b>{selectedClient.client_id}</b></div>
        <div><span>Type</span><b>{selectedClient.agent_mode === "simulated_agent" ? "Simulated agent" : "Real agent"}</b></div>
        <div><span>Status</span><b>{selectedLastSeen && Date.now() - selectedLastSeen.getTime() < 5 * 60 * 1000 ? "Active" : "Inactive"}</b></div>
        <div><span>Last sample</span><b>{selectedClient.last_sample_at ? new Date(selectedClient.last_sample_at).toLocaleString() : "N/A"}</b></div>
        <div><span>Last seen</span><b>{selectedClient.last_seen_at ? new Date(selectedClient.last_seen_at).toLocaleString() : "N/A"}</b></div>
        <div><span>Configured profile</span><b>{selectedProfile ? `${selectedProfile.label} (${selectedProfile.profile})` : "Not mapped to a configured profile"}</b></div>
      </div>
      <div className="table-scroll"><table><thead><tr><th>METRIC</th><th>LATEST TELEMETRY</th><th>PROVENANCE</th></tr></thead><tbody>
        <tr><td>CPU</td><td>{formatNumber(selectedClient.cpu_percent)} %</td><td><Provenance label={selectedClient.agent_mode === "real_agent" ? "REAL" : "SIMULATED"} /></td></tr>
        <tr><td>Memory</td><td>{formatNumber(selectedClient.memory_percent)} %</td><td><Provenance label={selectedClient.agent_mode === "real_agent" ? "REAL" : "SIMULATED"} /></td></tr>
        <tr><td>Latency</td><td>{formatNumber(selectedClient.latency_ms)} ms</td><td><Provenance label={selectedClient.agent_mode === "real_agent" ? "REAL" : "SIMULATED"} /></td></tr>
        <tr><td>Bandwidth</td><td>{formatNumber(selectedClient.bandwidth_mbps)} Mbps</td><td><Provenance label={selectedClient.agent_mode === "real_agent" ? "REAL" : "SIMULATED"} /></td></tr>
        <tr><td>Packet loss</td><td>{formatNumber(selectedClient.packet_loss_percent)} %</td><td><Provenance label={selectedClient.agent_mode === "real_agent" ? "REAL" : "SIMULATED"} /></td></tr>
        <tr><td>Availability</td><td>{formatNumber(selectedClient.availability_effective)} ({selectedClient.availability_source})</td><td><Provenance label={selectedClient.availability_source === "derived_from_last_seen" ? "DERIVED" : "SIMULATED"} /></td></tr>
      </tbody></table></div>
    </section>}
  </>;
}

function SelectionPage({ selection, setSelection, lastSelection, onExecuted }) {
  const [form, setForm] = useState(loadStored("greenfed:selectionForm", DEFAULT_SELECTION));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function update(name, value) {
    const next = { ...form, [name]: value };
    setForm(next);
    localStorage.setItem("greenfed:selectionForm", JSON.stringify(next));
  }

  function updateWeight(name, value) {
    update("weights", { ...form.weights, [name]: Number(value) });
  }

  async function execute() {
    setLoading(true);
    setError("");
    try {
      const payload = await post("/api/selection", {
        ...form,
        numSelect: Number(form.numSelect),
        seed: Number(form.seed),
        round: Number(form.round),
        minAvailability: Number(form.minAvailability),
        maxCpuPercent: Number(form.maxCpuPercent),
        minMemoryAvailableMb: Number(form.minMemoryAvailableMb),
        maxDiskPercent: Number(form.maxDiskPercent),
        maxLatencyMs: Number(form.maxLatencyMs),
        maxPacketLossPercent: Number(form.maxPacketLossPercent),
        weights: Object.fromEntries(Object.entries(form.weights).map(([k, v]) => [k, Number(v)]))
      });
      localStorage.setItem("greenfed:lastSelection", JSON.stringify(payload));
      setSelection(payload);
      onExecuted(payload);
    } catch (err) {
      setError(err.response?.data?.message || err.message || "Selection failed.");
    } finally {
      setLoading(false);
    }
  }

  const current = selection || lastSelection;
  const clients = current ? Object.values(current.clients || {}) : [];
  const selected = clients.filter(client => client.selected).sort((a, b) => (a.selection_rank || 99) - (b.selection_rank || 99));
  const rejected = clients.filter(client => !client.selected);
  const formDiffers = lastSelection && (
    form.scenario !== lastSelection.scenario ||
    form.strategy !== lastSelection.strategy ||
    Number(form.numSelect) !== Number(lastSelection.numSelect ?? lastSelection.requested) ||
    JSON.stringify(form.weights) !== JSON.stringify(lastSelection.configuration?.selection_weights || lastSelection.weights)
  );

  return <>
    <section className="panel">
      <PanelTitle title="Execute client selection" subtitle="Runs the existing Python selection algorithm and stores the exact explainable result" action={<button className="btn-primary" onClick={execute} disabled={loading}><PlayCircle size={16} /> {loading ? "Selecting..." : "Execute selection"}</button>} />
      <div className="form-grid">
        <label>Scenario<select value={form.scenario} onChange={e => update("scenario", e.target.value)}><option value="iid">IID</option><option value="non_iid">Non-IID</option></select></label>
        <label>Strategy<select value={form.strategy} onChange={e => update("strategy", e.target.value)}>{Object.entries(STRATEGY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Clients to select<input type="number" min="1" max="5" value={form.numSelect} onChange={e => update("numSelect", e.target.value)} /></label>
        <label>Seed<input type="number" value={form.seed} onChange={e => update("seed", e.target.value)} /></label>
        <label>Min availability<input type="number" step="0.01" value={form.minAvailability} onChange={e => update("minAvailability", e.target.value)} /></label>
        <label>Max CPU %<input type="number" value={form.maxCpuPercent} onChange={e => update("maxCpuPercent", e.target.value)} /></label>
        <label>Min memory (MB)<input type="number" value={form.minMemoryAvailableMb} onChange={e => update("minMemoryAvailableMb", e.target.value)} /></label>
        <label>Max disk %<input type="number" value={form.maxDiskPercent} onChange={e => update("maxDiskPercent", e.target.value)} /></label>
        <label>Max latency (ms)<input type="number" value={form.maxLatencyMs} onChange={e => update("maxLatencyMs", e.target.value)} /></label>
        <label>Max packet loss %<input type="number" step="0.1" value={form.maxPacketLossPercent} onChange={e => update("maxPacketLossPercent", e.target.value)} /></label>
      </div>
      <details className="advanced-details"><summary>Context-aware weights and thresholds</summary>
        <div className="form-grid compact-form">
          {Object.entries(form.weights).map(([key, value]) => <label key={key}>{key} weight<input type="number" step="0.01" value={value} onChange={e => updateWeight(key, e.target.value)} /></label>)}
        </div>
        <p className="dataset-note">Eligibility applies hard constraints first. Ranking scores only eligible clients. If fewer than requested are eligible, constraints are relaxed and the fallback is recorded explicitly.</p>
      </details>
      {error && <p className="partition-message partition-error">{error}</p>}
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Current unsaved configuration" subtitle="Form values that will be used by the next execution" />
        <div className="partition-summary">
          <div><span>Scenario</span><b>{form.scenario}</b></div>
          <div><span>Strategy</span><b>{STRATEGY_LABELS[form.strategy]}</b></div>
          <div><span>Requested clients</span><b>{form.numSelect}</b></div>
          <div><span>Seed</span><b>{form.seed}</b></div>
        </div>
        {formDiffers && <p className="dataset-note">This differs from the last executed selection. Execute selection to make it the active selection.</p>}
      </article>
      <article className="panel">
        <PanelTitle title="Last executed selection" subtitle="Actual algorithm result stored by the backend" />
        {current ? <div className="partition-summary">
          <div><span>Selection ID</span><b>{current.selectionId}</b></div>
          <div><span>Executed at</span><b>{current.metadata?.generated_at ? new Date(current.metadata.generated_at).toLocaleString() : "N/A"}</b></div>
          <div><span>Strategy</span><b>{STRATEGY_LABELS[current.strategy]}</b></div>
          <div><span>Scenario</span><b>{current.scenario}</b></div>
          <div><span>Requested / selected</span><b>{current.requested} / {current.selected?.length || 0}</b></div>
          <div><span>Constraints relaxed</span><b>{String(current.constraints_relaxed)}</b></div>
        </div> : <p className="dataset-note">No selection has been executed yet.</p>}
      </article>
    </section>

    {current && <>
      <section className="metric-grid">
        <MetricCard title="Selection ID" value={current.selectionId?.slice(0, 8) || "N/A"} icon={ShieldCheck} tone="blue" foot={STRATEGY_LABELS[current.strategy]} />
        <MetricCard title="Selected clients" value={current.selected?.length || 0} icon={Users} tone="green" foot={(current.selected || []).join(", ")} />
        <MetricCard title="Constraints relaxed" value={String(current.constraints_relaxed)} icon={AlertTriangle} tone={current.constraints_relaxed ? "orange" : "purple"} foot={current.notes?.[0] || "Hard constraints satisfied"} />
        <MetricCard title="Execution" value="Live" icon={PlayCircle} tone="orange" foot={current.metadata?.generated_at || "Python selection"} />
      </section>

      <section className="panel dataset-files">
        <PanelTitle title="Selected clients" subtitle="Scores, contributions and explainable decision reasons" />
        <div className="table-scroll"><table><thead><tr><th>RANK</th><th>CLIENT</th><th>SCORE</th><th>MISSING METRICS</th><th>CONTRIBUTIONS</th><th>REASON</th></tr></thead><tbody>
          {selected.map(client => <tr key={client.client_id}><td>{client.selection_rank}</td><td><b>{client.client_id}</b></td><td>{formatNumber(client.score, 4)}</td><td>{(client.missing_metrics || []).join(", ") || "None"}</td><td>{Object.entries(client.contributions || {}).map(([k, v]) => `${k}: ${formatNumber(v, 3)}`).join(" | ") || "N/A"}</td><td>{client.decision_reason}</td></tr>)}
        </tbody></table></div>
      </section>

      <section className="panel dataset-files">
        <PanelTitle title="Rejected or non-selected clients" subtitle="Eligibility failures and lower-ranked candidates remain visible" />
        <div className="table-scroll"><table><thead><tr><th>CLIENT</th><th>ELIGIBLE</th><th>MISSING METRICS</th><th>REASONS</th><th>SCORE</th></tr></thead><tbody>
          {rejected.map(client => <tr key={client.client_id}><td><b>{client.client_id}</b></td><td>{String(client.eligible)}</td><td>{(client.missing_metrics || []).join(", ") || "None"}</td><td>{[...(client.eligibility_reasons || []), client.decision_reason].filter(Boolean).join("; ")}</td><td>{formatNumber(client.score, 4)}</td></tr>)}
        </tbody></table></div>
      </section>

      <details className="panel advanced-details"><summary>Show raw selection payload (advanced)</summary><pre className="raw-json">{JSON.stringify(current, null, 2)}</pre></details>
    </>}
  </>;
}

function FederatedLearningPage({ latestSelection, jobs, onStarted, onRefreshJobs }) {
  const [form, setForm] = useState(loadStored("greenfed:trainingForm", DEFAULT_TRAINING));
  const [error, setError] = useState("");
  const [activeJobId, setActiveJobId] = useState(localStorage.getItem("greenfed:activeJobId") || "");
  const [activeJob, setActiveJob] = useState(null);
  const [roundResults, setRoundResults] = useState(null);

  useEffect(() => { localStorage.setItem("greenfed:trainingForm", JSON.stringify(form)); }, [form]);
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      if (!activeJobId) return;
      try {
        const job = await get(`/api/training/jobs/${activeJobId}`);
        if (!cancelled) setActiveJob(job);
      } catch {}
    }
    poll();
    const timer = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [activeJobId, jobs.length]);

  useEffect(() => {
    let cancelled = false;
    async function loadRounds() {
      if (!activeJob?.runId || activeJob.status !== "completed") return;
      const strategy = activeJob.strategy || latestSelection?.strategy || "context";
      try {
        const result = await get(`/api/experiments/${activeJob.runId}/strategy/${strategy}`);
        if (!cancelled) setRoundResults(result);
      } catch {
        if (!cancelled) setRoundResults(null);
      }
    }
    loadRounds();
    return () => { cancelled = true; };
  }, [activeJob?.runId, activeJob?.status, activeJob?.strategy, latestSelection?.strategy]);

  function update(name, value) { setForm(prev => ({ ...prev, [name]: value })); }

  async function startTraining() {
    if (!latestSelection?.selectionId) {
      setError("Execute a client selection first. Federated training must use the selected clients.");
      return;
    }
    setError("");
    try {
      const job = await post("/api/training/jobs", {
        name: form.name || undefined,
        selectionId: latestSelection.selectionId,
        rounds: Number(form.rounds),
        localEpochs: Number(form.localEpochs),
        batchSize: Number(form.batchSize),
        learningRate: Number(form.learningRate),
        validationFraction: Number(form.validationFraction),
        maxSamplesPerClient: form.maxSamplesPerClient ? Number(form.maxSamplesPerClient) : null,
        classWeightMode: form.classWeightMode,
        numThreads: Number(form.numThreads)
      });
      setActiveJob(job);
      setActiveJobId(job.jobId);
      localStorage.setItem("greenfed:activeJobId", job.jobId);
      onStarted(job);
    } catch (err) {
      setError(err.response?.data?.message || err.message || "Training failed to start.");
    }
  }

  const roundSummaries = (activeJob?.summary && Array.isArray(activeJob.summary)) ? activeJob.summary : null;
  const flSteps = ["Global Model", "Selected Clients", "Local Training", "Model Updates", "FedAvg Aggregation", "Updated Global Model", "Evaluation"];

  return <>
    <section className="panel">
      <PanelTitle title="Federated learning configuration" subtitle="Training uses the exact dashboard-selected clients via the existing FedAvg implementation" action={<button className="btn-primary" onClick={startTraining}><Play size={15} /> Start training</button>} />
      {!latestSelection ? <p className="partition-message partition-error">No selection available. Go to Client Selection and execute a selection first.</p> : <div className="selection-summary-inline">
        <span>Selection: <b>{latestSelection.selectionId}</b></span>
        <span>Strategy: <b>{STRATEGY_LABELS[latestSelection.strategy]}</b></span>
        <span>Scenario: <b>{latestSelection.scenario}</b></span>
        <span>Selected: <b>{(latestSelection.selected || []).join(", ")}</b></span>
        <span>Relaxed: <b>{String(latestSelection.constraints_relaxed)}</b></span>
        <Provenance label="LIVE SELECTION" title="This selection came from the Python selection algorithm and is passed as a fixed selection file to training." />
      </div>}
      <div className="form-grid">
        <label>Experiment name<input value={form.name} onChange={e => update("name", e.target.value)} placeholder="Optional name" /></label>
        <label>Communication rounds<input type="number" min="1" max="20" value={form.rounds} onChange={e => update("rounds", e.target.value)} /></label>
        <label>Local epochs<input type="number" min="1" max="10" value={form.localEpochs} onChange={e => update("localEpochs", e.target.value)} /></label>
        <label>Batch size<input type="number" min="1" value={form.batchSize} onChange={e => update("batchSize", e.target.value)} /></label>
        <label>Learning rate<input type="number" step="0.0001" value={form.learningRate} onChange={e => update("learningRate", e.target.value)} /></label>
        <label>Validation fraction<input type="number" step="0.01" value={form.validationFraction} onChange={e => update("validationFraction", e.target.value)} /></label>
        <label>Max samples/client<input type="number" value={form.maxSamplesPerClient} onChange={e => update("maxSamplesPerClient", e.target.value)} placeholder="Full dataset" /></label>
        <label>Class weights<select value={form.classWeightMode} onChange={e => update("classWeightMode", e.target.value)}><option value="none">None</option><option value="balanced">Balanced (federated counts)</option></select></label>
        <label>CPU threads<input type="number" min="1" max="32" value={form.numThreads} onChange={e => update("numThreads", e.target.value)} /></label>
      </div>
      {error && <p className="partition-message partition-error">{error}</p>}
    </section>

    <section className="panel">
      <PanelTitle title="Federated learning workflow" subtitle="Actual execution stages for the latest dashboard run" />
      <div className="workflow-bar">
        {flSteps.map((step, index) => {
          const state = activeJob?.status === "completed" ? "done" : index <= (activeJob?.currentRound || 0) ? "active" : "pending";
          return <div key={step} className={`workflow-step ${state}`}><span>{index + 1}</span><small>{step}</small></div>;
        })}
      </div>
      <p className="dataset-note">Model parameters are aggregated by sample-weighted FedAvg. Validation uses a held-out validation split from the training data; final evaluation uses the separate test split.</p>
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Training status" subtitle="Real execution status from the Spring-managed Python process" action={<button className="btn-secondary small" onClick={onRefreshJobs}><RefreshCw size={14} /> Refresh</button>} />
        {activeJob ? <>
          <div className="partition-summary">
            <div><span>Job</span><b>{activeJob.jobId}</b></div>
            <div><span>Run ID</span><b>{activeJob.runId}</b></div>
            <div><span>Status</span><b>{activeJob.status}</b></div>
            <div><span>Round</span><b>{activeJob.currentRound || 0} / {activeJob.totalRounds || "?"}</b></div>
            <div><span>Strategy</span><b>{STRATEGY_LABELS[activeJob.strategy] || activeJob.strategy}</b></div>
            <div><span>Selected clients</span><b>{(activeJob.request?.selectedClients || []).join(", ") || "N/A"}</b></div>
          </div>
          {activeJob.error && <p className="partition-message partition-error">{activeJob.error}</p>}
          <details className="advanced-details" open={activeJob.status === "running" || activeJob.status === "starting"}><summary>Execution log</summary><pre className="raw-json log-block">{(activeJob.log || []).join("\n") || "No log output yet."}</pre></details>
        </> : <p className="dataset-note">No active dashboard training job. Start a run to see real progress and metrics.</p>}
      </article>
      <article className="panel">
        <PanelTitle title="Result summary" subtitle="Available after the run completes and summary.json is written" />
        {roundSummaries ? <div className="table-scroll"><table><thead><tr><th>STRATEGY</th><th>VAL ACC</th><th>VAL MACRO-F1</th><th>TEST ACC</th><th>TEST MACRO-F1</th><th>COMM</th><th>CPU</th></tr></thead><tbody>
          {roundSummaries.map(row => <tr key={row.strategy}><td><b>{STRATEGY_LABELS[row.strategy] || row.strategy}</b></td><td>{formatPercent(row.validation_accuracy)}</td><td>{formatPercent(row.validation_macro_f1)}</td><td>{formatPercent(row.test_accuracy)}</td><td>{formatPercent(row.test_macro_f1)}</td><td>{formatNumber(row.communication_megabytes_total, 3)} MB</td><td>{formatNumber(row.cpu_seconds_total, 1)} s</td></tr>)}
        </tbody></table></div> : <p className="dataset-note">Round-wise and final evaluation metrics are shown only after actual execution completes. No simulated training animation is displayed.</p>}
      </article>
    </section>

    {roundResults?.rounds?.length > 0 && <section className="panel dataset-files">
      <PanelTitle title="Round-wise results" subtitle="Actual validation metrics and resource usage per communication round" />
      <div className="table-scroll"><table><thead><tr><th>ROUND</th><th>SELECTED CLIENTS</th><th>VAL ACCURACY</th><th>VAL MACRO-F1</th><th>COMMUNICATION</th><th>CPU TIME</th></tr></thead><tbody>
        {roundResults.rounds.map(round => <tr key={round.round}><td>{round.round}</td><td>{(round.selected_clients || []).join(", ")}</td><td>{formatPercent(round.validation?.accuracy)}</td><td>{formatPercent(round.validation?.macro_f1)}</td><td>{formatNumber((round.communication_bytes_round || 0) / (1024 * 1024), 3)} MB</td><td>{formatNumber(round.cpu_seconds_round, 1)} s</td></tr>)}
      </tbody></table></div>
      <p className="dataset-note">Validation metrics come from the held-out validation split. Final test metrics are separate and are shown in the result summary.</p>
    </section>}
  </>;
}

function ExperimentsPage({ aggregate, runs, jobs, onRefresh }) {
  const [scenario, setScenario] = useState("iid");
  const [selectedRuns, setSelectedRuns] = useState([]);
  const [strategyResults, setStrategyResults] = useState(null);

  const agg = aggregate.filter(row => row.scenario === scenario);
  const performanceData = agg.map(row => ({ strategy: STRATEGY_LABELS[row.strategy], accuracy: Number(row.test_accuracy_mean || 0) * 100, std: Number(row.test_accuracy_std || 0) * 100 }));
  const communicationData = agg.map(row => ({ strategy: STRATEGY_LABELS[row.strategy], mb: Number(row.communication_megabytes_total_mean || 0) }));
  const cpuData = agg.map(row => ({ strategy: STRATEGY_LABELS[row.strategy], seconds: Number(row.cpu_seconds_total_mean || 0) }));

  async function loadStrategy(runId, strategy) {
    try {
      const result = await get(`/api/experiments/${runId}/strategy/${strategy}`);
      setStrategyResults(result);
    } catch {}
  }

  function toggleRun(runId) {
    setSelectedRuns(prev => prev.includes(runId) ? prev.filter(id => id !== runId) : [...prev, runId]);
  }

  const compared = runs.filter(run => selectedRuns.includes(run.runId));

  return <>
    <section className="metric-grid">
      <MetricCard title="Historical runs" value={runs.filter(r => r.source === "historical_artifact").length} icon={Database} tone="blue" foot="Preserved federated result directories" />
      <MetricCard title="Dashboard runs" value={runs.filter(r => r.source === "dashboard_execution").length} icon={PlayCircle} tone="green" foot="New executions via unified workflow" />
      <MetricCard title="Active jobs" value={jobs.filter(j => j.status === "running" || j.status === "starting").length} icon={Activity} tone="orange" foot="Managed by Spring training service" />
      <MetricCard title="Static aggregate" value={aggregate.length} icon={BarChart3} tone="purple" foot="IID/non-IID strategy means (3 seeds)" />
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="Model performance" subtitle={`${scenario.toUpperCase()} test accuracy by strategy`} action={<div className="partition-switch"><button className={scenario === "iid" ? "active" : ""} onClick={() => setScenario("iid")}>IID</button><button className={scenario === "non_iid" ? "active" : ""} onClick={() => setScenario("non_iid")}>Non-IID</button></div>} />
        <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={performanceData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="strategy" tick={{ fill: "#7f8ba3", fontSize: 9 }} interval={0} angle={-12} textAnchor="end" height={45} axisLine={false} tickLine={false} />
          <YAxis domain={[60, 80]} tick={{ fill: "#7f8ba3", fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Bar dataKey="accuracy" name="Test accuracy" fill="#5b8cff" radius={[4, 4, 0, 0]} />
        </BarChart></ResponsiveContainer></div>
      </article>
      <article className="panel">
        <PanelTitle title="Communication volume" subtitle="Total megabytes for the selected scenario" />
        <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={communicationData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="strategy" tick={{ fill: "#7f8ba3", fontSize: 9 }} interval={0} angle={-12} textAnchor="end" height={45} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#7f8ba3", fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(value) => `${Number(value).toFixed(3)} MB`} contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Bar dataKey="mb" name="Communication" fill="#20c997" radius={[4, 4, 0, 0]} />
        </BarChart></ResponsiveContainer></div>
      </article>
    </section>

    <section className="chart-grid">
      <article className="panel">
        <PanelTitle title="CPU processing time" subtitle="Total CPU seconds for the selected scenario" />
        <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={cpuData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
          <CartesianGrid stroke="#202a3c" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="strategy" tick={{ fill: "#7f8ba3", fontSize: 9 }} interval={0} angle={-12} textAnchor="end" height={45} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#7f8ba3", fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(value) => `${Number(value).toFixed(1)} s`} contentStyle={{ background: "#121b2b", border: "1px solid #29364b", borderRadius: 10, color: "#eaf0fa" }} />
          <Bar dataKey="seconds" name="CPU time" fill="#f59e0b" radius={[4, 4, 0, 0]} />
        </BarChart></ResponsiveContainer></div>
      </article>
      <article className="panel">
        <PanelTitle title="Verified strategy comparison" subtitle="Historical aggregate over seeds 42, 43, 44. Results are measured, not fabricated." />
        <div className="table-scroll"><table><thead><tr><th>STRATEGY</th><th>TEST ACCURACY</th><th>BALANCED ACC</th><th>MACRO-F1</th><th>WEIGHTED-F1</th><th>COMMUNICATION</th><th>CPU TIME</th><th>CLIENTS/ROUND</th><th>PROVENANCE</th></tr></thead><tbody>
          {agg.map(row => <tr key={`${row.scenario}-${row.strategy}`}><td><b>{STRATEGY_LABELS[row.strategy]}</b></td><td>{formatPercent(row.test_accuracy_mean)} <small>+/- {formatPercent(row.test_accuracy_std, 3)}</small></td><td>{formatPercent(row.test_balanced_accuracy_mean)}</td><td>{formatPercent(row.test_macro_f1_mean)} <small>+/- {formatPercent(row.test_macro_f1_std, 3)}</small></td><td>{formatPercent(row.test_weighted_f1_mean)}</td><td>{formatNumber(row.communication_megabytes_total_mean, 3)} MB</td><td>{formatNumber(row.cpu_seconds_total_mean, 1)} s</td><td>{row.strategy === "all" ? 5 : 3}</td><td><Provenance label="HISTORICAL" title="Measured from preserved federated result artifacts." /></td></tr>)}
        </tbody></table></div>
        <p className="dataset-note">Context-aware selection did not consistently outperform random or resource-aware selection across these seeds. Read differences with standard deviations and protocol constraints.</p>
        <div className="heading-actions"><a className="btn-secondary" href="/data/experiments/aggregate_full.md" download><Download size={14} /> Markdown</a><a className="btn-secondary" href="/data/experiments/aggregate_full.csv" download><Download size={14} /> CSV</a><a className="btn-secondary" href="/data/experiments/aggregate_full.json" download><Download size={14} /> JSON</a></div>
      </article>
    </section>

    <section className="panel dataset-files">
      <PanelTitle title="Experiment history" subtitle="Historical artifacts and new dashboard executions. Existing results are never overwritten." action={<button className="btn-secondary small" onClick={onRefresh}><RefreshCw size={14} /> Refresh</button>} />
      <div className="table-scroll"><table><thead><tr><th>COMPARE</th><th>RUN ID</th><th>SCENARIO</th><th>STRATEGIES</th><th>CREATED</th><th>SOURCE</th><th>DETAILS</th></tr></thead><tbody>
        {runs.map(run => <tr key={run.runId}><td><input type="checkbox" checked={selectedRuns.includes(run.runId)} onChange={() => toggleRun(run.runId)} /></td><td><b>{run.runId}</b></td><td>{run.scenario}</td><td>{(run.strategies || []).join(", ")}</td><td>{run.createdAt ? new Date(run.createdAt).toLocaleString() : "N/A"}</td><td><Provenance label={run.source === "dashboard_execution" ? "NEW EXECUTION" : "HISTORICAL"} /></td><td><button className="btn-secondary small" onClick={() => loadStrategy(run.runId, (run.strategies || ["all"])[0])}>Inspect</button></td></tr>)}
      </tbody></table>{runs.length === 0 && <div className="empty-state">No experiment history available from the results API.</div>}</div>
    </section>

    {compared.length > 0 && <section className="panel dataset-files">
      <PanelTitle title="Selected run comparison" subtitle="Side-by-side summary rows from selected run directories" />
      <div className="table-scroll"><table><thead><tr><th>RUN</th><th>SOURCE</th><th>SCENARIO</th><th>STRATEGY</th><th>TEST ACC</th><th>MACRO-F1</th><th>COMM</th><th>CPU</th><th>CLIENTS</th></tr></thead><tbody>
        {compared.flatMap(run => (Array.isArray(run.summary) ? run.summary : []).map(row => <tr key={`${run.runId}-${row.strategy}`}><td>{run.runId}</td><td><Provenance label={run.source === "dashboard_execution" ? "NEW" : "HISTORICAL"} /></td><td>{run.scenario || row.scenario}</td><td>{STRATEGY_LABELS[row.strategy] || row.strategy}</td><td>{formatPercent(row.test_accuracy)}</td><td>{formatPercent(row.test_macro_f1)}</td><td>{formatNumber(row.communication_megabytes_total, 3)} MB</td><td>{formatNumber(row.cpu_seconds_total, 1)} s</td><td>{row.num_select || (row.strategy === "all" ? 5 : 3)}</td></tr>))}
      </tbody></table></div>
    </section>}

    {strategyResults && <section className="panel dataset-files">
      <PanelTitle title={`Run details: ${strategyResults.strategy}`} subtitle="Round-wise metrics from the saved results.json artifact" action={<button className="btn-secondary small" onClick={() => setStrategyResults(null)}>Close</button>} />
      <div className="table-scroll"><table><thead><tr><th>ROUND</th><th>SELECTED CLIENTS</th><th>VAL ACC</th><th>MACRO-F1</th><th>COMM</th><th>CPU</th></tr></thead><tbody>
        {(strategyResults.rounds || []).map(round => <tr key={round.round}><td>{round.round}</td><td>{(round.selected_clients || []).join(", ")}</td><td>{formatPercent(round.validation?.accuracy)}</td><td>{formatPercent(round.validation?.macro_f1)}</td><td>{formatNumber((round.communication_bytes_round || 0) / (1024 * 1024), 3)} MB</td><td>{formatNumber(round.cpu_seconds_round, 1)} s</td></tr>)}
      </tbody></table></div>
      <details className="advanced-details"><summary>Raw strategy result</summary><pre className="raw-json">{JSON.stringify(strategyResults, null, 2)}</pre></details>
    </section>}
  </>;
}

function AdvancedPage({ simulation, jobs, latestSelection }) {
  const weightSum = Object.values(DEFAULT_SELECTION.weights).reduce((sum, value) => sum + Number(value || 0), 0);
  const warnings = [];
  if (DEFAULT_SELECTION.numSelect < 1 || DEFAULT_SELECTION.numSelect > 5) warnings.push("Default client count must be between 1 and 5.");
  if (weightSum <= 0) warnings.push("Context-aware weights must sum to a positive value.");
  if (Object.values(DEFAULT_SELECTION.weights).some(value => Number(value) < 0)) warnings.push("Weights must be non-negative.");
  if (DEFAULT_SELECTION.weights.cost > 1) warnings.push("Cost weight must be 1 or less.");
  if (DEFAULT_SELECTION.minAvailability < 0 || DEFAULT_SELECTION.minAvailability > 1) warnings.push("Availability threshold must be between 0 and 1.");
  if (DEFAULT_SELECTION.maxCpuPercent < 0 || DEFAULT_SELECTION.maxCpuPercent > 100) warnings.push("CPU threshold must be between 0 and 100.");
  if (DEFAULT_SELECTION.maxDiskPercent < 0 || DEFAULT_SELECTION.maxDiskPercent > 100) warnings.push("Disk threshold must be between 0 and 100.");
  if (DEFAULT_SELECTION.maxPacketLossPercent < 0 || DEFAULT_SELECTION.maxPacketLossPercent > 100) warnings.push("Packet-loss threshold must be between 0 and 100.");

  return <>
    <section className="panel">
      <PanelTitle title="Advanced configuration and diagnostics" subtitle="Technical parameters, logs and API diagnostics are kept out of the normal workflow view" />
      <div className="partition-summary">
        <div><span>Default selection strategy</span><b>Context-aware</b></div>
        <div><span>Default selection count</span><b>3 of 5 clients</b></div>
        <div><span>Default FL rounds / epochs</span><b>2 rounds / 1 local epoch</b></div>
        <div><span>Default optimizer / aggregation</span><b>Adam lr 0.001 / sample-weighted FedAvg</b></div>
      </div>
      <details className="advanced-details" open><summary>Configuration validation</summary>
        {warnings.length ? <div className="validation-list">{warnings.map((warning, index) => <div key={index}><AlertTriangle size={16} />{warning}</div>)}</div> : <div className="validation-list"><div><CheckCircle2 size={16} />Default thresholds and weights pass basic validation.</div></div>}
        <p className="dataset-note">Weights control category importance only after eligibility. Thresholds are hard constraints; ranking occurs only among eligible clients.</p>
      </details>
      <details className="advanced-details"><summary>Selection defaults and weights</summary><pre className="raw-json">{JSON.stringify(DEFAULT_SELECTION, null, 2)}</pre></details>
      <details className="advanced-details"><summary>Training defaults</summary><pre className="raw-json">{JSON.stringify(DEFAULT_TRAINING, null, 2)}</pre></details>
      <details className="advanced-details"><summary>Simulator status and logs</summary><pre className="raw-json log-block">{JSON.stringify(simulation, null, 2)}</pre></details>
      <details className="advanced-details"><summary>Active/recent training jobs</summary><pre className="raw-json log-block">{JSON.stringify(jobs, null, 2)}</pre></details>
      <details className="advanced-details"><summary>Latest selection payload</summary><pre className="raw-json">{JSON.stringify(latestSelection, null, 2)}</pre></details>
      <details className="advanced-details"><summary>API diagnostics</summary>
        <div className="validation-list">
          <div><CheckCircle2 size={16} />Dashboard APIs: /api/dashboard/overview, /api/dashboard/clients, /api/dashboard/timeseries</div>
          <div><CheckCircle2 size={16} />Selection APIs: /api/selection, /api/selection/latest, /api/selection/{"{id}"}</div>
          <div><CheckCircle2 size={16} />Training APIs: /api/training/jobs, /api/training/jobs/{"{id}"}, cancel</div>
          <div><CheckCircle2 size={16} />Experiment APIs: /api/experiments, /api/experiments/{"{runId}"}, strategy results</div>
          <div><CheckCircle2 size={16} />Simulation APIs: /api/simulation/status, /start, /stop</div>
          <div><CheckCircle2 size={16} />Legacy Express ingest remains available at :5000 if needed; dashboard simulation uses Spring ingest.</div>
        </div>
      </details>
    </section>
  </>;
}

function App() {
  const [active, setActive] = useState("Overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [overview, setOverview] = useState(null);
  const [overviewError, setOverviewError] = useState("");
  const [clients, setClients] = useState([]);
  const [clientsError, setClientsError] = useState("");
  const [timeseries, setTimeseries] = useState({ resource: [], network: [] });
  const [simulation, setSimulation] = useState({ running: false });
  const [aggregate, setAggregate] = useState([]);
  const [runs, setRuns] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [lastSelection, setLastSelection] = useState(loadStored("greenfed:lastSelection", null));
  const [lastUpdated, setLastUpdated] = useState(null);

  async function refresh() {
    const results = await Promise.allSettled([
      get("/api/dashboard/overview"),
      get("/api/dashboard/clients"),
      get("/api/dashboard/timeseries"),
      get("/api/simulation/status"),
      get("/data/experiments/aggregate_full.json"),
      get("/api/experiments"),
      get("/api/training/jobs"),
      get("/api/selection/latest")
    ]);

    const [overviewRes, clientsRes, timeseriesRes, simulationRes, aggregateRes, runsRes, jobsRes, selectionRes] = results;
    setOverviewError(overviewRes.status === "fulfilled" ? "" : "Dashboard API unavailable. Start Spring backend on :4000.");
    if (overviewRes.status === "fulfilled") setOverview(overviewRes.value);
    setClientsError(clientsRes.status === "fulfilled" ? "" : "Client API unavailable.");
    if (clientsRes.status === "fulfilled") setClients(Array.isArray(clientsRes.value) ? clientsRes.value : []);
    if (timeseriesRes.status === "fulfilled") setTimeseries(timeseriesRes.value || { resource: [], network: [] });
    if (simulationRes.status === "fulfilled") setSimulation(simulationRes.value || { running: false });
    if (aggregateRes.status === "fulfilled") setAggregate(Array.isArray(aggregateRes.value) ? aggregateRes.value : []);
    if (runsRes.status === "fulfilled") setRuns(Array.isArray(runsRes.value) ? runsRes.value : []);
    if (jobsRes.status === "fulfilled") setJobs(Array.isArray(jobsRes.value) ? jobsRes.value : []);
    if (selectionRes.status === "fulfilled") {
      setLastSelection(selectionRes.value);
      localStorage.setItem("greenfed:lastSelection", JSON.stringify(selectionRes.value));
    }
    setLastUpdated(new Date());
  }

  useEffect(() => { refresh(); const timer = setInterval(refresh, 10000); return () => clearInterval(timer); }, []);

  async function startSimulation() {
    try { setSimulation(await post("/api/simulation/start")); await refresh(); }
    catch (err) { setSimulation(prev => ({ ...prev, error: err.response?.data?.message || err.message })); }
  }

  async function stopSimulation() {
    try { setSimulation(await post("/api/simulation/stop")); await refresh(); }
    catch (err) { setSimulation(prev => ({ ...prev, error: err.response?.data?.message || err.message })); }
  }

  function onSelectionExecuted(selection) {
    setLastSelection(selection);
    setActive("Federated Learning");
  }

  const heading = active;
  const connected = !overviewError;

  return <div className="app-shell">
    {mobileOpen && <button className="scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
    <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
      <div className="brand">
        <div className="brand-mark"><Activity size={21} /></div>
        <div><strong>GreenFed<span>-IDS</span></strong><small>UNIFIED RESEARCH DASHBOARD</small></div>
        <button className="mobile-close" onClick={() => setMobileOpen(false)}><X size={18} /></button>
      </div>
      <div className="workspace"><div className="workspace-icon"><ShieldCheck size={17} /></div><div><b>Single workflow</b><small>Dataset to comparison</small></div><ChevronDown size={15} /></div>
      <div className="nav-label">WORKSPACE</div>
      <nav>{nav.map(item => <button key={item.label} className={`nav-item ${active === item.label ? "selected" : ""}`} onClick={() => { setActive(item.label); setMobileOpen(false); }}>
        <item.icon size={18} /><span>{item.label}</span>
      </button>)}</nav>
      <div className="sidebar-bottom">
        <div className="system-status"><span className="pulse-dot" /><div><b>Spring backend</b><small>{connected ? "Connected" : "Unavailable"}</small></div></div>
        <div className="user-row"><div className="avatar">GF</div><div><b>Research dashboard</b><small>Project interface</small></div><ChevronDown size={15} /></div>
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <div className="top-left"><button className="menu-btn" onClick={() => setMobileOpen(true)}><Menu size={20} /></button><div className="breadcrumb">GreenFed-IDS <span>/</span> <b>{active}</b></div></div>
        <div className="top-actions">
          <div className="environment"><span className="pulse-dot" />{connected ? "LIVE / HISTORICAL" : "OFFLINE"}</div>
          <button className="icon-button" title="Refresh" onClick={refresh}><RefreshCw size={17} /></button>
          <button className="icon-button notification" title="Status"><Bell size={17} /><i /></button>
        </div>
      </header>

      <div className="content">
        <div className="page-heading">
          <div>
            <div className="eyebrow">UNIFIED RESEARCH WORKFLOW</div>
            <h1>{heading}</h1>
            <p>{active === "Overview" && "Monitor the complete GreenFed-IDS workflow, live telemetry, current selection, and verified experiment evidence."}
               {active === "Dataset" && "Inspect CICIoT2023, train/test split, IID/non-IID partitions, and validation status."}
               {active === "IoT Clients" && "Manage simulated IoT clients, view latest context telemetry, and keep registrations stable across restarts."}
               {active === "Client Selection" && "Execute the actual selection algorithm, inspect scores, and understand selected and rejected clients."}
               {active === "Federated Learning" && "Run FedAvg training using the exact selected clients and inspect real execution outputs."}
               {active === "Experiments & Results" && "Create, review, rerun and compare historical and newly executed experiments."}
               {active === "Advanced Configuration" && "Inspect thresholds, defaults, logs, diagnostics and raw payloads."}
            </p>
          </div>
          <div className="heading-actions">
            <span className="updated"><RefreshCw size={14} /> {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Loading..."}</span>
            <button className="btn-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button>
          </div>
        </div>

        {active === "Overview" && <OverviewPage overview={overview} overviewError={overviewError} timeseries={timeseries} latestSelection={lastSelection} jobs={jobs} aggregate={aggregate} simulation={simulation} onNavigate={setActive} onRefresh={refresh} />}
        {active === "Dataset" && <DatasetPage />}
        {active === "IoT Clients" && <IoTClientsPage clients={clients} clientsError={clientsError} simulation={simulation} onStart={startSimulation} onStop={stopSimulation} onRefresh={refresh} />}
        {active === "Client Selection" && <SelectionPage selection={lastSelection} setSelection={setLastSelection} lastSelection={lastSelection} onExecuted={onSelectionExecuted} />}
        {active === "Federated Learning" && <FederatedLearningPage latestSelection={lastSelection} jobs={jobs} onStarted={job => { setJobs(prev => [job, ...prev]); refresh(); }} onRefreshJobs={refresh} />}
        {active === "Experiments & Results" && <ExperimentsPage aggregate={aggregate} runs={runs} jobs={jobs} onRefresh={refresh} />}
        {active === "Advanced Configuration" && <AdvancedPage simulation={simulation} jobs={jobs} latestSelection={lastSelection} />}

        <footer className="footer"><span>© 2026 GreenFed-IDS · Unified research dashboard</span><span><span className="pulse-dot" /> {connected ? "Backend connected" : "Backend unavailable"}</span></footer>
      </div>
    </main>
  </div>;
}

export default App;
