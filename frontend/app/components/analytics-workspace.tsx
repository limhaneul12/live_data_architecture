"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type ChartKind,
  type Dataset,
  type ExploreOrderDirection,
  type QueryResult,
  fetchDatasets,
  runAnalyticsQuery,
  runExploreQuery,
} from "../lib/api";
import { ChartPreview } from "./chart-preview";
import { ResultTable } from "./result-table";

const DEFAULT_SQL =
  "SELECT event_type, event_count\nFROM event_type_counts\nORDER BY event_count DESC\nLIMIT 100";
const ROW_LIMIT_OPTIONS = [20, 50, 100, 500] as const;
const CHART_KIND_OPTIONS: Array<{ value: ChartKind; label: string }> = [
  { value: "bar", label: "Bar chart" },
  { value: "line", label: "Line chart" },
  { value: "pie", label: "Donut chart" },
  { value: "metric", label: "Big number" },
  { value: "table", label: "Table" },
];

type WorkspaceMode = "explore" | "sql-lab";
type QueryStatus = "idle" | "loading" | "success" | "error";

export function AnalyticsWorkspace() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [mode, setMode] = useState<WorkspaceMode>("explore");
  const [selectedDatasetName, setSelectedDatasetName] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [selectedChartKind, setSelectedChartKind] = useState<ChartKind>("bar");
  const [orderBy, setOrderBy] = useState("");
  const [orderDirection, setOrderDirection] =
    useState<ExploreOrderDirection>("desc");
  const [rowLimit, setRowLimit] = useState<number>(100);
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
        const loadedDatasets = await fetchDatasets();
        if (!mounted) {
          return;
        }
        setDatasets(loadedDatasets);
        const defaultDataset = preferredDataset(loadedDatasets);
        if (defaultDataset !== undefined) {
          applyDatasetDefaults(defaultDataset);
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
      orderDirection,
      rowLimit,
    });
  }, [orderBy, orderDirection, rowLimit, selectedColumns, selectedDataset]);

  const metadataLoaded = datasets.length > 0;
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

  async function runExplore() {
    if (selectedDataset === undefined) {
      setResult(null);
      setError("실행할 table을 먼저 선택해주세요.");
      setQueryStatus("error");
      return;
    }
    setQueryStatus("loading");
    setError(null);
    try {
      setResult(
        await runExploreQuery({
          dataset: selectedDataset.name,
          columns: selectedExploreColumns({
            dataset: selectedDataset,
            selectedColumns,
          }),
          order_by: orderBy.length > 0 ? orderBy : null,
          order_direction: orderDirection,
          row_limit: rowLimit,
        }),
      );
      setQueryStatus("success");
    } catch (queryError) {
      setResult(null);
      setError(
        queryError instanceof Error
          ? queryError.message
          : "Chart query 실행에 실패했습니다.",
      );
      setQueryStatus("error");
    }
  }

  function applyDatasetDefaults(dataset: Dataset) {
    setSelectedDatasetName(dataset.name);
    setSelectedColumns(defaultColumnsFor(dataset));
    setOrderBy(defaultOrderFor(dataset));
    setOrderDirection(defaultOrderDirectionFor(dataset));
    setSelectedChartKind(defaultChartFor(dataset));
  }

  function handleColumnToggle(columnName: string) {
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
        <div className="top-nav">
          <strong>Event Analytics</strong>
        </div>
        <div className={`connection-pill ${metadataLoaded ? "ok" : "error"}`}>
          <span />
          {statusLabel}
        </div>
      </header>

      <div className="superset-layout">
        <section className="superset-main">
          <div className="page-toolbar">
            <div>
              <p className="breadcrumb">Event analytics</p>
              <h2>{mode === "explore" ? "Chart builder" : "SQL Lab"}</h2>
            </div>
            <div className="toolbar-actions">
              <button
                className={mode === "explore" ? "tab-button active" : "tab-button"}
                type="button"
                onClick={() => setMode("explore")}
              >
                Chart Builder
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
                  <span>{datasets.length} tables</span>
                </div>

                <label className="control-label" htmlFor="dataset-select">
                  Table
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
                      {dataset.name}
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
                    <label className="control-label" htmlFor="order-direction">
                      Direction
                    </label>
                    <select
                      id="order-direction"
                      className="superset-select"
                      value={orderDirection}
                      onChange={(event) =>
                        setOrderDirection(
                          event.target.value as ExploreOrderDirection,
                        )
                      }
                      disabled={orderBy.length === 0}
                    >
                      <option value="desc">Descending</option>
                      <option value="asc">Ascending</option>
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
                  onClick={() => void runExplore()}
                  disabled={bootLoading || queryStatus === "loading"}
                >
                  {queryStatus === "loading" ? "Running..." : "Run chart"}
                </button>
              </aside>

              <section className="explore-canvas">
                <div className="canvas-header">
                  <div>
                    <p className="breadcrumb">
                      {selectedDataset?.name ?? "table"} / {selectedChartKind}
                    </p>
                    <h2>{selectedDataset?.name ?? "Table"}</h2>
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
                      <p>
                        실제 실행은 `/analytics/explore-query` structured API가
                        처리하고, 아래 SQL은 preview입니다.
                      </p>
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
                    setSqlLabSql(event.target.value);
                  }}
                  spellCheck={false}
                  aria-label="SQL Lab editor"
                />
                {error !== null ? <div className="error-banner">{error}</div> : null}
              </section>

              <aside className="metadata-panel">
                <div className="metadata-header">
                  <h2>Available tables</h2>
                  <p>SQL Lab에서 조회 가능한 generated table 목록입니다.</p>
                </div>
                <div className="metadata-list">
                  {datasets.map((dataset) => (
                    <article key={dataset.name} className="metadata-card">
                      <strong>{dataset.name}</strong>
                      <p>{dataset.description}</p>
                      <div className="metadata-columns">
                        {dataset.columns.map((column) => (
                          <span key={column.name}>
                            {column.name}
                            <small>{column.kind}</small>
                          </span>
                        ))}
                      </div>
                      <button
                        className="metadata-query-button"
                        type="button"
                        onClick={() => {
                          setSqlLabSql(exampleSqlForDataset(dataset));
                        }}
                      >
                        Insert sample SELECT
                      </button>
                    </article>
                  ))}
                </div>
              </aside>

              <div className="sql-lab-results">
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
  if (dataset.name === "event_type_counts") {
    return "pie";
  }
  return "bar";
}

function exampleSqlForDataset(dataset: Dataset): string {
  const columns = defaultColumnsFor(dataset);
  const orderBy = defaultOrderFor(dataset);
  const orderDirection = defaultOrderDirectionFor(dataset);
  return buildExploreSql({
    dataset,
    selectedColumns: columns,
    orderBy,
    orderDirection,
    rowLimit: 100,
  });
}

function defaultOrderDirectionFor(dataset: Dataset): ExploreOrderDirection {
  if (dataset.name === "commerce_funnel_counts") {
    return "asc";
  }
  return "desc";
}

function buildExploreSql({
  dataset,
  selectedColumns,
  orderBy,
  orderDirection,
  rowLimit,
}: {
  dataset: Dataset;
  selectedColumns: string[];
  orderBy: string;
  orderDirection: ExploreOrderDirection;
  rowLimit: number;
}): string {
  const validColumnNames = new Set(dataset.columns.map((column) => column.name));
  const projection = selectedExploreColumns({ dataset, selectedColumns });
  const lines = [
    `SELECT ${projection.map(formatIdentifier).join(", ")}`,
    `FROM ${formatIdentifier(dataset.name)}`,
  ];
  if (orderBy.length > 0 && validColumnNames.has(orderBy)) {
    lines.push(
      `ORDER BY ${formatIdentifier(orderBy)} ${orderDirection.toUpperCase()}`,
    );
  }
  lines.push(`LIMIT ${rowLimit}`);
  return lines.join("\n");
}

function selectedExploreColumns({
  dataset,
  selectedColumns,
}: {
  dataset: Dataset;
  selectedColumns: string[];
}): string[] {
  const validColumnNames = new Set(dataset.columns.map((column) => column.name));
  const columns = selectedColumns.filter((column) => validColumnNames.has(column));
  return columns.length > 0 ? columns : defaultColumnsFor(dataset);
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
