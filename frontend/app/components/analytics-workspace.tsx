"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type Dataset,
  type PresetQuery,
  type QueryResult,
  fetchDatasets,
  fetchPresets,
  runAnalyticsQuery,
} from "../lib/api";
import { ChartPreview } from "./chart-preview";
import { ResultTable } from "./result-table";

const FALLBACK_SQL = "SELECT event_type, event_count\nFROM event_type_counts\nORDER BY event_count DESC";

export function AnalyticsWorkspace() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [presets, setPresets] = useState<PresetQuery[]>([]);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [sql, setSql] = useState(FALLBACK_SQL);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);
  const metadataLoaded = datasets.length > 0 && presets.length > 0;
  const statusLabel = bootLoading
    ? "Loading metadata"
    : metadataLoaded
      ? "Backend API connected"
      : "Backend API error";
  const statusClassName = bootLoading
    ? "status-dot loading"
    : metadataLoaded
      ? "status-dot"
      : "status-dot error";

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
        const firstPreset = loadedPresets[0];
        if (firstPreset !== undefined) {
          setActivePreset(firstPreset.slug);
          setSql(firstPreset.sql);
        }
      } catch (loadError) {
        if (mounted) {
          setError(loadError instanceof Error ? loadError.message : "초기 데이터를 불러오지 못했습니다.");
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

  const selectedDatasetName = useMemo(() => {
    const matched = datasets.find((dataset) => sql.includes(dataset.name));
    return matched?.name ?? datasets[0]?.name ?? "";
  }, [datasets, sql]);

  async function handleRunQuery() {
    setLoading(true);
    setError(null);
    try {
      setResult(await runAnalyticsQuery(sql));
    } catch (queryError) {
      setResult(null);
      setError(queryError instanceof Error ? queryError.message : "SQL 실행에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  function handleDatasetChange(datasetName: string) {
    setActivePreset(null);
    setSql(`SELECT *\nFROM ${datasetName}\nLIMIT 100`);
  }

  function handlePresetClick(preset: PresetQuery) {
    setActivePreset(preset.slug);
    setSql(preset.sql);
  }

  return (
    <main className="workspace-shell">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Live data architecture assignment</p>
          <h1>Event Analytics SQL Workspace</h1>
          <p className="hero-copy">
            Redis Streams로 들어온 이벤트를 PostgreSQL generated view로 집계하고,
            안전하게 제한된 SQL 결과를 표와 차트 preview로 확인합니다.
          </p>
        </div>
        <div className="status-card" aria-live="polite">
          <span className={statusClassName} />
          <div>
            <strong>{statusLabel}</strong>
            <span>datasets {datasets.length} · presets {presets.length}</span>
          </div>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="side-panel">
          <div className="panel-header">
            <h2>Datasets</h2>
            <p>Allowlisted generated views only</p>
          </div>
          <label className="field-label" htmlFor="dataset-select">
            View selector
          </label>
          <select
            id="dataset-select"
            className="dataset-select"
            value={selectedDatasetName}
            onChange={(event) => handleDatasetChange(event.target.value)}
            disabled={datasets.length === 0}
          >
            {datasets.map((dataset) => (
              <option key={dataset.name} value={dataset.name}>
                {dataset.name}
              </option>
            ))}
          </select>
          <div className="dataset-list">
            {datasets.map((dataset) => (
              <article key={dataset.name} className="dataset-card">
                <strong>{dataset.label}</strong>
                <code>{dataset.name}</code>
                <p>{dataset.description}</p>
              </article>
            ))}
          </div>
        </aside>

        <section className="query-panel">
          <div className="panel-header horizontal">
            <div>
              <h2>SQL</h2>
              <p>SELECT + generated view allowlist + max 500 rows</p>
            </div>
            <button className="run-button" type="button" onClick={handleRunQuery} disabled={loading || bootLoading}>
              {loading ? "Running..." : "Run SQL"}
            </button>
          </div>

          <div className="preset-row" aria-label="Preset queries">
            {presets.map((preset) => (
              <button
                key={preset.slug}
                type="button"
                className={activePreset === preset.slug ? "preset active" : "preset"}
                onClick={() => handlePresetClick(preset)}
                title={preset.description}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <textarea
            className="sql-editor"
            value={sql}
            onChange={(event) => {
              setActivePreset(null);
              setSql(event.target.value);
            }}
            spellCheck={false}
            aria-label="SQL editor"
          />

          {error !== null ? <div className="error-banner">{error}</div> : null}
        </section>
      </section>

      <section className="result-grid">
        <ChartPreview result={result} />
        <ResultTable result={result} />
      </section>
    </main>
  );
}
