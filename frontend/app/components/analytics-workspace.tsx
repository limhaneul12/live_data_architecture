"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type ChartKind,
  type Dataset,
  type PresetQuery,
  type QueryResult,
  fetchDatasets,
  fetchPresets,
  runAnalyticsQuery,
} from "../lib/api";
import { ChartPreview } from "./chart-preview";
import { ResultTable } from "./result-table";

const DEFAULT_SQL =
  "SELECT event_type, event_count\nFROM event_type_counts\nORDER BY event_count DESC\nLIMIT 100";
const ROW_LIMIT_OPTIONS = [20, 50, 100, 500] as const;
const CHART_KIND_OPTIONS: Array<{ value: ChartKind; label: string }> = [
  { value: "bar", label: "Bar chart" },
  { value: "line", label: "Line chart" },
  { value: "metric", label: "Big number" },
  { value: "table", label: "Table" },
];

type WorkspaceMode = "explore" | "sql-lab";
type QueryStatus = "idle" | "loading" | "success" | "error";

export function AnalyticsWorkspace() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [presets, setPresets] = useState<PresetQuery[]>([]);
  const [mode, setMode] = useState<WorkspaceMode>("explore");
  const [selectedDatasetName, setSelectedDatasetName] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [selectedChartKind, setSelectedChartKind] = useState<ChartKind>("bar");
  const [orderBy, setOrderBy] = useState("");
  const [rowLimit, setRowLimit] = useState<number>(100);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [sqlLabSql, setSqlLabSql] = useState(DEFAULT_SQL);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queryStatus, setQueryStatus] = useState<QueryStatus>("idle");
  const [bootLoading, setBootLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadInitialData() {
      setBootLoading(true);
      try {
        const [loadedDatasets, loadedPresets] = await Promise.all([
          fetchDatasets(),
          fetchPresets(),
        ]);
        if (!mounted) {
          return;
        }
        setDatasets(loadedDatasets);
        setPresets(loadedPresets);
        const defaultDataset = preferredDataset(loadedDatasets);
        if (defaultDataset !== undefined) {
          applyDatasetDefaults(defaultDataset);
        }
        const firstPreset = loadedPresets[0];
        if (firstPreset !== undefined) {
          setActivePreset(firstPreset.slug);
          setSqlLabSql(firstPreset.sql);
        }
      } catch (loadError) {
        if (mounted) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "초기 데이터를 불러오지 못했습니다.",
          );
          setQueryStatus("error");
        }
      } finally {
        if (mounted) {
          setBootLoading(false);
        }
      }
    }

    void loadInitialData();
    return () => {
      mounted = false;
    };
  }, []);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.name === selectedDatasetName),
    [datasets, selectedDatasetName],
  );

  const generatedSql = useMemo(() => {
    if (selectedDataset === undefined) {
      return DEFAULT_SQL;
    }
    return buildExploreSql({
      dataset: selectedDataset,
      selectedColumns,
      orderBy,
      rowLimit,
    });
  }, [orderBy, rowLimit, selectedColumns, selectedDataset]);

  const metadataLoaded = datasets.length > 0 && presets.length > 0;
  const statusLabel = bootLoading
    ? "Loading metadata"
    : metadataLoaded
      ? "Connected"
      : "Backend unavailable";

  async function runSql(sql: string) {
    setQueryStatus("loading");
    setError(null);
    try {
      setResult(await runAnalyticsQuery(sql));
      setQueryStatus("success");
    } catch (queryError) {
      setResult(null);
      setError(
        queryError instanceof Error ? queryError.message : "SQL 실행에 실패했습니다.",
      );
      setQueryStatus("error");
    }
  }

  function applyDatasetDefaults(dataset: Dataset) {
    setSelectedDatasetName(dataset.name);
    setSelectedColumns(defaultColumnsFor(dataset));
    setOrderBy(defaultOrderFor(dataset));
    setSelectedChartKind(defaultChartFor(dataset));
    setActivePreset(null);
  }

  function handlePresetClick(preset: PresetQuery) {
    setMode("sql-lab");
    setActivePreset(preset.slug);
    setSqlLabSql(preset.sql);
    setSelectedChartKind(preset.chart_kind);
  }

  function handleColumnToggle(columnName: string) {
    setActivePreset(null);
    setSelectedColumns((currentColumns) => {
      if (currentColumns.includes(columnName)) {
        return currentColumns.filter((name) => name !== columnName);
      }
      return [...currentColumns, columnName];
    });
  }

  return (
    <main className="superset-shell">
      <header className="superset-topbar">
        <div className="brand-mark">LDA</div>
        <nav className="top-nav" aria-label="Primary">
          <strong>Event Analytics</strong>
          <span>Dashboards</span>
          <span>Charts</span>
          <span>SQL Lab</span>
          <span>Datasets</span>
        </nav>
        <div className={`connection-pill ${metadataLoaded ? "ok" : "error"}`}>
          <span />
          {statusLabel}
        </div>
      </header>

      <div className="superset-layout">
        <aside className="superset-sidebar">
          <section className="sidebar-card">
            <p className="eyebrow">Explore workflow</p>
            <h1>Superset-style Event BI</h1>
            <p>
              generated dataset을 고르고 chart control을 조절하면 안전한 SELECT를
              생성해 바로 시각화합니다.
            </p>
          </section>

          <section className="sidebar-section">
            <h2>Saved queries</h2>
            <div className="saved-query-list">
              {presets.map((preset) => (
                <button
                  key={preset.slug}
                  className={
                    activePreset === preset.slug
                      ? "saved-query active"
                      : "saved-query"
                  }
                  type="button"
                  onClick={() => handlePresetClick(preset)}
                >
                  <strong>{preset.label}</strong>
                  <span>{preset.description}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="sidebar-section compact">
            <h2>Guardrails</h2>
            <ul className="guardrail-list">
              <li>generated view allowlist</li>
              <li>single SELECT only</li>
              <li>no functions / joins / subqueries</li>
              <li>read-only transaction + timeout</li>
            </ul>
          </section>
        </aside>

        <section className="superset-main">
          <div className="page-toolbar">
            <div>
              <p className="breadcrumb">Charts / Explore / Event analytics</p>
              <h2>Untitled event chart</h2>
            </div>
            <div className="toolbar-actions">
              <button
                className={mode === "explore" ? "tab-button active" : "tab-button"}
                type="button"
                onClick={() => setMode("explore")}
              >
                Explore
              </button>
              <button
                className={mode === "sql-lab" ? "tab-button active" : "tab-button"}
                type="button"
                onClick={() => setMode("sql-lab")}
              >
                SQL Lab
              </button>
            </div>
          </div>

          {mode === "explore" ? (
            <section className="explore-grid">
              <aside className="control-panel">
                <div className="control-header">
                  <h2>Chart controls</h2>
                  <span>{datasets.length} datasets</span>
                </div>

                <label className="control-label" htmlFor="dataset-select">
                  Datasource
                </label>
                <select
                  id="dataset-select"
                  className="superset-select"
                  value={selectedDatasetName}
                  onChange={(event) => {
                    const dataset = datasets.find(
                      (item) => item.name === event.target.value,
                    );
                    if (dataset !== undefined) {
                      applyDatasetDefaults(dataset);
                    }
                  }}
                  disabled={datasets.length === 0}
                >
                  {datasets.map((dataset) => (
                    <option key={dataset.name} value={dataset.name}>
                      {dataset.label}
                    </option>
                  ))}
                </select>

                <label className="control-label" htmlFor="chart-kind">
                  Visualization type
                </label>
                <select
                  id="chart-kind"
                  className="superset-select"
                  value={selectedChartKind}
                  onChange={(event) =>
                    setSelectedChartKind(event.target.value as ChartKind)
                  }
                >
                  {CHART_KIND_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>

                <div className="control-row">
                  <div>
                    <label className="control-label" htmlFor="order-by">
                      Sort by
                    </label>
                    <select
                      id="order-by"
                      className="superset-select"
                      value={orderBy}
                      onChange={(event) => setOrderBy(event.target.value)}
                    >
                      <option value="">No sort</option>
                      {selectedDataset?.columns.map((column) => (
                        <option key={column.name} value={column.name}>
                          {column.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="control-label" htmlFor="row-limit">
                      Row limit
                    </label>
                    <select
                      id="row-limit"
                      className="superset-select"
                      value={rowLimit}
                      onChange={(event) => setRowLimit(Number(event.target.value))}
                    >
                      {ROW_LIMIT_OPTIONS.map((limit) => (
                        <option key={limit} value={limit}>
                          {limit}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="control-label">Columns</div>
                <div className="column-list">
                  {selectedDataset?.columns.map((column) => (
                    <label key={column.name} className="column-chip">
                      <input
                        type="checkbox"
                        checked={selectedColumns.includes(column.name)}
                        onChange={() => handleColumnToggle(column.name)}
                      />
                      <span>
                        <strong>{column.label}</strong>
                        <small>{column.kind}</small>
                      </span>
                    </label>
                  ))}
                </div>

                <button
                  className="primary-button"
                  type="button"
                  onClick={() => runSql(generatedSql)}
                  disabled={bootLoading || queryStatus === "loading"}
                >
                  {queryStatus === "loading" ? "Running..." : "Run chart"}
                </button>
              </aside>

              <section className="explore-canvas">
                <div className="canvas-header">
                  <div>
                    <p className="breadcrumb">
                      {selectedDataset?.name ?? "dataset"} / {selectedChartKind}
                    </p>
                    <h2>{selectedDataset?.label ?? "Dataset"}</h2>
                  </div>
                  <span className={`query-status ${queryStatus}`}>
                    {queryStatusLabel(queryStatus)}
                  </span>
                </div>

                {error !== null ? <div className="error-banner">{error}</div> : null}

                <div className="result-grid">
                  <ChartPreview
                    result={result}
                    chartKindOverride={selectedChartKind}
                  />
                  <ResultTable result={result} />
                </div>

                <section className="sql-preview-panel">
                  <div className="panel-header horizontal">
                    <div>
                      <h2>Generated SQL</h2>
                      <p>Explore controls에서 생성된 제한 SQL입니다.</p>
                    </div>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setMode("sql-lab");
                        setSqlLabSql(generatedSql);
                      }}
                    >
                      Open in SQL Lab
                    </button>
                  </div>
                  <pre>{generatedSql}</pre>
                </section>
              </section>
            </section>
          ) : (
            <section className="sql-lab-grid">
              <section className="sql-lab-editor">
                <div className="panel-header horizontal">
                  <div>
                    <p className="breadcrumb">SQL Lab</p>
                    <h2>Query editor</h2>
                  </div>
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => runSql(sqlLabSql)}
                    disabled={bootLoading || queryStatus === "loading"}
                  >
                    {queryStatus === "loading" ? "Running..." : "Run SQL"}
                  </button>
                </div>
                <textarea
                  className="sql-editor"
                  value={sqlLabSql}
                  onChange={(event) => {
                    setActivePreset(null);
                    setSqlLabSql(event.target.value);
                  }}
                  spellCheck={false}
                  aria-label="SQL Lab editor"
                />
                {error !== null ? <div className="error-banner">{error}</div> : null}
              </section>

              <aside className="metadata-panel">
                <h2>Datasets</h2>
                <div className="metadata-list">
                  {datasets.map((dataset) => (
                    <article key={dataset.name} className="metadata-card">
                      <strong>{dataset.label}</strong>
                      <code>{dataset.name}</code>
                      <p>{dataset.description}</p>
                      <div className="metadata-columns">
                        {dataset.columns.map((column) => (
                          <span key={column.name}>{column.name}</span>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </aside>

              <div className="sql-lab-results">
                <ChartPreview result={result} />
                <ResultTable result={result} />
              </div>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

function preferredDataset(datasets: Dataset[]): Dataset | undefined {
  return (
    datasets.find((dataset) => dataset.name === "event_type_counts") ?? datasets[0]
  );
}

function defaultColumnsFor(dataset: Dataset): string[] {
  const displayColumns = dataset.columns.filter(
    (column) => column.name !== "sort_order",
  );
  if (dataset.name === "error_event_ratio") {
    return displayColumns.map((column) => column.name);
  }
  const dimensions = displayColumns.filter((column) => column.kind !== "metric");
  const metrics = displayColumns.filter((column) => column.kind === "metric");
  return [...dimensions.slice(0, 2), ...metrics.slice(0, 1)].map(
    (column) => column.name,
  );
}

function defaultOrderFor(dataset: Dataset): string {
  if (dataset.name === "commerce_funnel_counts") {
    return "sort_order";
  }
  const metric = dataset.columns.find((column) => column.kind === "metric");
  return metric?.name ?? dataset.columns[0]?.name ?? "";
}

function defaultChartFor(dataset: Dataset): ChartKind {
  if (dataset.name === "hourly_event_counts") {
    return "line";
  }
  if (dataset.name === "error_event_ratio") {
    return "metric";
  }
  return "bar";
}

function buildExploreSql({
  dataset,
  selectedColumns,
  orderBy,
  rowLimit,
}: {
  dataset: Dataset;
  selectedColumns: string[];
  orderBy: string;
  rowLimit: number;
}): string {
  const validColumnNames = new Set(dataset.columns.map((column) => column.name));
  const columns = selectedColumns.filter((column) => validColumnNames.has(column));
  const projection = columns.length > 0 ? columns : defaultColumnsFor(dataset);
  const lines = [
    `SELECT ${projection.map(formatIdentifier).join(", ")}`,
    `FROM ${formatIdentifier(dataset.name)}`,
  ];
  if (orderBy.length > 0 && validColumnNames.has(orderBy)) {
    lines.push(`ORDER BY ${formatIdentifier(orderBy)}${orderSuffix(orderBy)}`);
  }
  lines.push(`LIMIT ${rowLimit}`);
  return lines.join("\n");
}

function orderSuffix(columnName: string): string {
  if (columnName === "sort_order") {
    return "";
  }
  return columnName.endsWith("_count") || columnName.endsWith("_ratio") ? " DESC" : "";
}

function formatIdentifier(identifier: string): string {
  if (!/^[a-z][a-z0-9_]*$/.test(identifier)) {
    throw new Error(`Invalid analytics identifier: ${identifier}`);
  }
  return identifier;
}

function queryStatusLabel(status: QueryStatus): string {
  if (status === "loading") {
    return "running";
  }
  if (status === "success") {
    return "success";
  }
  if (status === "error") {
    return "error";
  }
  return "idle";
}
