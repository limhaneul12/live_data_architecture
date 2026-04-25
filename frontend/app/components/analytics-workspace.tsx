"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type ChartKind,
  type Dataset,
  type ExploreOrderDirection,
  type ExploreJoinType,
  type QueryResult,
  type ViewTable,
  createViewTable,
  fetchDatasets,
  fetchViewTables,
  previewViewTable,
  runAnalyticsQuery,
  runExploreQuery,
} from "../lib/api";
import { ChartPreview } from "./chart-preview";
import { ResultTable } from "./result-table";

const DEFAULT_SQL =
  "SELECT event_type, event_count\nFROM event_type_counts\nORDER BY event_count DESC\nLIMIT 100";
const DEFAULT_VIEW_TABLE_SQL =
  "SELECT\n  user_id,\n  event_type,\n  COUNT(*)::bigint AS event_count\nFROM events\nGROUP BY user_id, event_type";
const ROW_LIMIT_OPTIONS = [20, 50, 100, 500] as const;
const CHART_KIND_OPTIONS: Array<{ value: ChartKind; label: string }> = [
  { value: "bar", label: "Bar chart" },
  { value: "line", label: "Line chart" },
  { value: "pie", label: "Donut chart" },
  { value: "metric", label: "Big number" },
  { value: "table", label: "Table" },
];

type WorkspaceMode = "explore" | "sql-lab" | "view-tables";
type QueryStatus = "idle" | "loading" | "success" | "error";

export function AnalyticsWorkspace() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [viewTables, setViewTables] = useState<ViewTable[]>([]);
  const [mode, setMode] = useState<WorkspaceMode>("explore");
  const [selectedDatasetName, setSelectedDatasetName] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [selectedChartKind, setSelectedChartKind] = useState<ChartKind>("bar");
  const [orderBy, setOrderBy] = useState("");
  const [orderDirection, setOrderDirection] =
    useState<ExploreOrderDirection>("desc");
  const [rowLimit, setRowLimit] = useState<number>(100);
  const [joinEnabled, setJoinEnabled] = useState(false);
  const [joinDatasetName, setJoinDatasetName] = useState("");
  const [joinType, setJoinType] = useState<ExploreJoinType>("inner");
  const [joinLeftColumn, setJoinLeftColumn] = useState("");
  const [joinRightColumn, setJoinRightColumn] = useState("");
  const [sqlLabSql, setSqlLabSql] = useState(DEFAULT_SQL);
  const [viewTableName, setViewTableName] = useState("user_event_type_counts");
  const [viewTableDescription, setViewTableDescription] = useState(
    "유저별 이벤트 타입 발생 수",
  );
  const [viewTableSql, setViewTableSql] = useState(DEFAULT_VIEW_TABLE_SQL);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queryStatus, setQueryStatus] = useState<QueryStatus>("idle");
  const [bootLoading, setBootLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadInitialData() {
      setBootLoading(true);
      try {
        const [loadedDatasets, loadedViewTables] = await Promise.all([
          fetchDatasets(),
          fetchViewTables(),
        ]);
        if (!mounted) {
          return;
        }
        setDatasets(loadedDatasets);
        setViewTables(loadedViewTables);
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
  const selectedJoinDataset = useMemo(
    () => datasets.find((dataset) => dataset.name === joinDatasetName),
    [datasets, joinDatasetName],
  );
  const activeJoin = useMemo(
    () =>
      joinEnabled &&
      selectedDataset !== undefined &&
      selectedJoinDataset !== undefined &&
      joinLeftColumn.length > 0 &&
      joinRightColumn.length > 0
        ? {
            dataset: selectedJoinDataset,
            leftColumn: joinLeftColumn,
            rightColumn: joinRightColumn,
            joinType,
          }
        : null,
    [
      joinEnabled,
      joinLeftColumn,
      joinRightColumn,
      joinType,
      selectedDataset,
      selectedJoinDataset,
    ],
  );
  const chartColumnOptions = useMemo(
    () =>
      chartColumnsFor({
        dataset: selectedDataset,
        joinDataset: activeJoin?.dataset,
      }),
    [activeJoin?.dataset, selectedDataset],
  );

  const generatedSql = useMemo(() => {
    if (selectedDataset === undefined) {
      return DEFAULT_SQL;
    }
    return buildExploreSql({
      dataset: selectedDataset,
      join: activeJoin,
      selectedColumns,
      orderBy,
      orderDirection,
      rowLimit,
    });
  }, [
    activeJoin,
    orderBy,
    orderDirection,
    rowLimit,
    selectedColumns,
    selectedDataset,
  ]);

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
            joinDataset: activeJoin?.dataset,
            selectedColumns,
          }),
          joins:
            activeJoin === null
              ? []
              : [
                  {
                    dataset: activeJoin.dataset.name,
                    left_column: activeJoin.leftColumn,
                    right_column: activeJoin.rightColumn,
                    join_type: activeJoin.joinType,
                  },
                ],
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
    setJoinEnabled(false);
    setJoinDatasetName("");
    setJoinLeftColumn("");
    setJoinRightColumn("");
  }

  function handleColumnToggle(columnName: string) {
    setSelectedColumns((currentColumns) => {
      if (currentColumns.includes(columnName)) {
        return currentColumns.filter((name) => name !== columnName);
      }
      return [...currentColumns, columnName];
    });
  }

  function enableDefaultJoin() {
    if (selectedDataset === undefined) {
      return;
    }
    const defaultJoinDataset = datasets.find(
      (dataset) => dataset.name !== selectedDataset.name,
    );
    if (defaultJoinDataset === undefined) {
      return;
    }
    const [leftColumn, rightColumn] = defaultJoinColumns(
      selectedDataset,
      defaultJoinDataset,
    );
    setJoinEnabled(true);
    setJoinDatasetName(defaultJoinDataset.name);
    setJoinLeftColumn(leftColumn);
    setJoinRightColumn(rightColumn);
    setSelectedColumns(defaultColumnsForJoinedDatasets(selectedDataset, defaultJoinDataset));
    setOrderBy(qualifiedColumnName(selectedDataset.name, defaultOrderFor(selectedDataset)));
  }

  async function reloadMetadata(preferredDatasetName: string | null) {
    const [loadedDatasets, loadedViewTables] = await Promise.all([
      fetchDatasets(),
      fetchViewTables(),
    ]);
    setDatasets(loadedDatasets);
    setViewTables(loadedViewTables);
    const preferred = loadedDatasets.find(
      (dataset) => dataset.name === preferredDatasetName,
    );
    if (preferred !== undefined) {
      applyDatasetDefaults(preferred);
    }
  }

  async function runViewTablePreview() {
    setQueryStatus("loading");
    setError(null);
    try {
      setResult(await previewViewTable(viewTableSql));
      setQueryStatus("success");
    } catch (previewError) {
      setResult(null);
      setError(
        previewError instanceof Error
          ? previewError.message
          : "View table preview에 실패했습니다.",
      );
      setQueryStatus("error");
    }
  }

  async function saveViewTable() {
    setQueryStatus("loading");
    setError(null);
    try {
      const savedDataset = await createViewTable({
        name: viewTableName,
        description: viewTableDescription,
        sourceSql: viewTableSql,
      });
      await reloadMetadata(savedDataset.name);
      setMode("explore");
      setResult(null);
      setQueryStatus("success");
    } catch (saveError) {
      setResult(null);
      setError(
        saveError instanceof Error
          ? saveError.message
          : "View table 저장에 실패했습니다.",
      );
      setQueryStatus("error");
    }
  }

  return (
    <main className="superset-shell">
      <header className="superset-topbar">
        <div className="brand-mark">LDA</div>
        <nav className="top-nav" aria-label="Analytics workspace navigation">
          <strong>Event Analytics</strong>
          <button
            className={topNavClass(mode, "explore")}
            type="button"
            onClick={() => setMode("explore")}
          >
            Charts
          </button>
          <button
            className={topNavClass(mode, "sql-lab")}
            type="button"
            onClick={() => setMode("sql-lab")}
          >
            SQL Lab
          </button>
          <button
            className={topNavClass(mode, "view-tables")}
            type="button"
            onClick={() => setMode("view-tables")}
          >
            View Tables
          </button>
        </nav>
        <div className={`status-pill ${metadataLoaded ? "ok" : "error"}`}>
          <span />
          {statusLabel}
        </div>
      </header>

      <div className="superset-layout">
        <section className="superset-main">
          <div className="page-toolbar">
            <div>
              <p className="breadcrumb">{workspaceBreadcrumb()}</p>
              <h2>{workspaceTitle(mode)}</h2>
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

                <div className="join-builder">
                  <label className="join-toggle">
                    <input
                      type="checkbox"
                      checked={joinEnabled}
                      onChange={(event) => {
                        if (event.target.checked) {
                          enableDefaultJoin();
                        } else {
                          setJoinEnabled(false);
                          setJoinDatasetName("");
                          setJoinLeftColumn("");
                          setJoinRightColumn("");
                          setSelectedColumns(
                            selectedDataset === undefined
                              ? []
                              : defaultColumnsFor(selectedDataset),
                          );
                          setOrderBy(
                            selectedDataset === undefined
                              ? ""
                              : defaultOrderFor(selectedDataset),
                          );
                        }
                      }}
                    />
                    <span>
                      <strong>Join table</strong>
                      <small>base dataset 기준 1개 JOIN</small>
                    </span>
                  </label>

                  {joinEnabled ? (
                    <div className="join-controls">
                      <label className="control-label" htmlFor="join-dataset">
                        Join target
                      </label>
                      <select
                        id="join-dataset"
                        className="superset-select"
                        value={joinDatasetName}
                        onChange={(event) => {
                          const nextJoinDataset = datasets.find(
                            (dataset) => dataset.name === event.target.value,
                          );
                          setJoinDatasetName(event.target.value);
                          if (
                            selectedDataset !== undefined &&
                            nextJoinDataset !== undefined
                          ) {
                            const [leftColumn, rightColumn] = defaultJoinColumns(
                              selectedDataset,
                              nextJoinDataset,
                            );
                            setJoinLeftColumn(leftColumn);
                            setJoinRightColumn(rightColumn);
                            setSelectedColumns(
                              defaultColumnsForJoinedDatasets(
                                selectedDataset,
                                nextJoinDataset,
                              ),
                            );
                          }
                        }}
                      >
                        {datasets
                          .filter((dataset) => dataset.name !== selectedDatasetName)
                          .map((dataset) => (
                            <option key={dataset.name} value={dataset.name}>
                              {dataset.name}
                            </option>
                          ))}
                      </select>

                      <div className="control-row compact">
                        <div>
                          <label className="control-label" htmlFor="join-type">
                            Join type
                          </label>
                          <select
                            id="join-type"
                            className="superset-select"
                            value={joinType}
                            onChange={(event) =>
                              setJoinType(event.target.value as ExploreJoinType)
                            }
                          >
                            <option value="inner">INNER</option>
                            <option value="left">LEFT</option>
                          </select>
                        </div>
                        <div>
                          <label className="control-label" htmlFor="join-left">
                            Base key
                          </label>
                          <select
                            id="join-left"
                            className="superset-select"
                            value={joinLeftColumn}
                            onChange={(event) => setJoinLeftColumn(event.target.value)}
                          >
                            {selectedDataset?.columns.map((column) => (
                              <option key={column.name} value={column.name}>
                                {column.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="control-label" htmlFor="join-right">
                            Join key
                          </label>
                          <select
                            id="join-right"
                            className="superset-select"
                            value={joinRightColumn}
                            onChange={(event) => setJoinRightColumn(event.target.value)}
                          >
                            {selectedJoinDataset?.columns.map((column) => (
                              <option key={column.name} value={column.name}>
                                {column.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>

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
                      {chartColumnOptions.map((column) => (
                        <option key={column.value} value={column.value}>
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
                  {chartColumnOptions.map((column) => (
                    <label key={column.value} className="column-chip">
                      <input
                        type="checkbox"
                        checked={selectedColumns.includes(column.value)}
                        onChange={() => handleColumnToggle(column.value)}
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
          ) : mode === "sql-lab" ? (
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
          ) : (
            <section className="view-table-grid">
              <section className="sql-lab-editor">
                <div className="panel-header horizontal">
                  <div>
                    <p className="breadcrumb">View Tables</p>
                    <h2>Create dataset view</h2>
                    <p>
                      원본 events 또는 기존 dataset을 SELECT해서 Chart Builder용
                      view table로 저장합니다.
                    </p>
                  </div>
                  <div className="button-row">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => void runViewTablePreview()}
                      disabled={bootLoading || queryStatus === "loading"}
                    >
                      Preview
                    </button>
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => void saveViewTable()}
                      disabled={bootLoading || queryStatus === "loading"}
                    >
                      Save dataset
                    </button>
                  </div>
                </div>

                <label className="control-label" htmlFor="view-table-name">
                  View table name
                </label>
                <input
                  id="view-table-name"
                  className="superset-input"
                  value={viewTableName}
                  onChange={(event) => setViewTableName(event.target.value)}
                />

                <label className="control-label" htmlFor="view-table-description">
                  Description
                </label>
                <input
                  id="view-table-description"
                  className="superset-input"
                  value={viewTableDescription}
                  onChange={(event) => setViewTableDescription(event.target.value)}
                />

                <label className="control-label" htmlFor="view-table-sql">
                  Source SELECT
                </label>
                <textarea
                  id="view-table-sql"
                  className="sql-editor view-table-source-editor"
                  value={viewTableSql}
                  onChange={(event) => setViewTableSql(event.target.value)}
                  spellCheck={false}
                />
                {error !== null ? <div className="error-banner">{error}</div> : null}
              </section>

              <aside className="metadata-panel">
                <div className="metadata-header">
                  <h2>Saved view tables</h2>
                  <p>저장하면 dataset 목록에 추가되고 Charts에서 바로 선택됩니다.</p>
                </div>
                <div className="metadata-list">
                  {viewTables.length === 0 ? (
                    <p className="muted">아직 저장된 view table이 없습니다.</p>
                  ) : (
                    viewTables.map((viewTable) => (
                      <article key={viewTable.name} className="metadata-card">
                        <strong>{viewTable.name}</strong>
                        <p>{viewTable.description || "No description"}</p>
                        <div className="metadata-columns">
                          {viewTable.columns.map((column) => (
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
                            const dataset = datasets.find(
                              (item) => item.name === viewTable.name,
                            );
                            if (dataset !== undefined) {
                              applyDatasetDefaults(dataset);
                              setMode("explore");
                            }
                          }}
                        >
                          Open in Charts
                        </button>
                      </article>
                    ))
                  )}
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

function topNavClass(currentMode: WorkspaceMode, targetMode: WorkspaceMode): string {
  return currentMode === targetMode ? "top-nav-link active" : "top-nav-link";
}

function workspaceBreadcrumb(): string {
  return "Event analytics";
}

function workspaceTitle(mode: WorkspaceMode): string {
  if (mode === "explore") {
    return "Chart builder";
  }
  if (mode === "view-tables") {
    return "View Tables";
  }
  return "SQL Lab";
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
    join: null,
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
  join,
  selectedColumns,
  orderBy,
  orderDirection,
  rowLimit,
}: {
  dataset: Dataset;
  join: {
    dataset: Dataset;
    leftColumn: string;
    rightColumn: string;
    joinType: ExploreJoinType;
  } | null;
  selectedColumns: string[];
  orderBy: string;
  orderDirection: ExploreOrderDirection;
  rowLimit: number;
}): string {
  const validColumnNames = new Set(
    chartColumnsFor({ dataset, joinDataset: join?.dataset }).map(
      (column) => column.value,
    ),
  );
  const projection = selectedExploreColumns({
    dataset,
    joinDataset: join?.dataset,
    selectedColumns,
  });
  const lines = [
    `SELECT ${projection.map(formatColumnSelector).join(", ")}`,
    `FROM ${formatIdentifier(dataset.name)}`,
  ];
  if (join !== null) {
    lines.push(
      `${join.joinType.toUpperCase()} JOIN ${formatIdentifier(join.dataset.name)}`,
    );
    lines.push(
      `  ON ${formatIdentifier(dataset.name)}.${formatIdentifier(join.leftColumn)}` +
        ` = ${formatIdentifier(join.dataset.name)}.${formatIdentifier(join.rightColumn)}`,
    );
  }
  if (orderBy.length > 0 && validColumnNames.has(orderBy)) {
    lines.push(
      `ORDER BY ${formatColumnSelector(orderBy)} ${orderDirection.toUpperCase()}`,
    );
  }
  lines.push(`LIMIT ${rowLimit}`);
  return lines.join("\n");
}

function selectedExploreColumns({
  dataset,
  joinDataset,
  selectedColumns,
}: {
  dataset: Dataset;
  joinDataset?: Dataset;
  selectedColumns: string[];
}): string[] {
  const validColumnNames = new Set(
    chartColumnsFor({ dataset, joinDataset }).map((column) => column.value),
  );
  const columns = selectedColumns.filter((column) => validColumnNames.has(column));
  return columns.length > 0
    ? columns
    : joinDataset === undefined
      ? defaultColumnsFor(dataset)
      : defaultColumnsForJoinedDatasets(dataset, joinDataset);
}

function formatIdentifier(identifier: string): string {
  if (!/^[a-z][a-z0-9_]*$/.test(identifier)) {
    throw new Error(`Invalid analytics identifier: ${identifier}`);
  }
  return identifier;
}

function formatColumnSelector(selector: string): string {
  if (!selector.includes(".")) {
    return formatIdentifier(selector);
  }
  const [datasetName, columnName] = selector.split(".", 2);
  return `${formatIdentifier(datasetName)}.${formatIdentifier(columnName)}`;
}

function qualifiedColumnName(datasetName: string, columnName: string): string {
  return `${datasetName}.${columnName}`;
}

function chartColumnsFor({
  dataset,
  joinDataset,
}: {
  dataset: Dataset | undefined;
  joinDataset?: Dataset;
}): Array<{
  value: string;
  label: string;
  kind: string;
}> {
  if (dataset === undefined) {
    return [];
  }
  if (joinDataset === undefined) {
    return dataset.columns.map((column) => ({
      value: column.name,
      label: column.label,
      kind: column.kind,
    }));
  }
  return [dataset, joinDataset].flatMap((item) =>
    item.columns.map((column) => ({
      value: qualifiedColumnName(item.name, column.name),
      label: `${item.name}.${column.name}`,
      kind: column.kind,
    })),
  );
}

function defaultColumnsForJoinedDatasets(
  dataset: Dataset,
  joinDataset: Dataset,
): string[] {
  return [
    ...defaultColumnsFor(dataset)
      .slice(0, 2)
      .map((columnName) => qualifiedColumnName(dataset.name, columnName)),
    ...defaultColumnsFor(joinDataset)
      .slice(0, 2)
      .map((columnName) => qualifiedColumnName(joinDataset.name, columnName)),
  ];
}

function defaultJoinColumns(
  dataset: Dataset,
  joinDataset: Dataset,
): [string, string] {
  const joinColumnNames = new Set(joinDataset.columns.map((column) => column.name));
  const sharedColumn = dataset.columns.find((column) =>
    joinColumnNames.has(column.name),
  );
  if (sharedColumn !== undefined) {
    return [sharedColumn.name, sharedColumn.name];
  }
  return [
    dataset.columns[0]?.name ?? "",
    joinDataset.columns[0]?.name ?? "",
  ];
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
