import type { QueryResult, QueryRow } from "../lib/api";

type ChartPreviewProps = {
  result: QueryResult | null;
};

type ChartPoint = {
  x: number;
  y: number;
  label: string;
};

const COLORS = ["#5b7cfa", "#35c2a1", "#ffb84d", "#ff6b87", "#9b7cff", "#4db6ff"];

export function ChartPreview({ result }: ChartPreviewProps) {
  if (result === null) {
    return (
      <section className="visual-panel empty-panel">
        <h2>Chart preview</h2>
        <p>SQL을 실행하면 결과 shape에 맞춰 bar, line, metric preview를 표시합니다.</p>
      </section>
    );
  }

  const { chart } = result;
  return (
    <section className="visual-panel">
      <div className="panel-header horizontal">
        <div>
          <h2>Chart preview</h2>
          <p>
            {chart.chart_kind} · x={chart.x_axis ?? "-"} · y={chart.y_axis ?? "-"}
            {chart.series_axis !== null ? ` · series=${chart.series_axis}` : ""}
          </p>
        </div>
      </div>
      {chart.chart_kind === "metric" ? <MetricPreview result={result} /> : null}
      {chart.chart_kind === "bar" ? <BarPreview result={result} /> : null}
      {chart.chart_kind === "line" ? <LinePreview result={result} /> : null}
      {chart.chart_kind === "table" ? <p className="muted">이 결과는 표 형태가 더 적합합니다.</p> : null}
    </section>
  );
}

function MetricPreview({ result }: ChartPreviewProps & { result: QueryResult }) {
  const firstRow = result.rows[0] ?? {};
  return (
    <div className="metric-grid">
      {result.columns.map((column) => (
        <article key={column} className="metric-card">
          <span>{column}</span>
          <strong>{formatValue(firstRow[column])}</strong>
        </article>
      ))}
    </div>
  );
}

function BarPreview({ result }: ChartPreviewProps & { result: QueryResult }) {
  const xAxis = result.chart.x_axis;
  const yAxis = result.chart.y_axis;
  if (xAxis === null || yAxis === null) {
    return <p className="muted">bar chart에 필요한 축을 찾지 못했습니다.</p>;
  }

  const bars = result.rows.map((row, index) => {
    const baseLabel = String(row[xAxis] ?? "-");
    const seriesLabel = seriesValue(row, result.chart.series_axis);
    return {
      label: seriesLabel === null ? baseLabel : `${baseLabel} · ${seriesLabel}`,
      value: numericValue(row[yAxis]),
      color: COLORS[index % COLORS.length],
    };
  });
  const maxValue = Math.max(...bars.map((bar) => bar.value), 1);

  return (
    <div className="bar-list">
      {bars.map((bar) => (
        <div key={`${bar.label}-${bar.value}`} className="bar-row">
          <span className="bar-label">{bar.label}</span>
          <div className="bar-track">
            <span
              className="bar-fill"
              style={{ width: `${(bar.value / maxValue) * 100}%`, background: bar.color }}
            />
          </div>
          <strong>{bar.value}</strong>
        </div>
      ))}
    </div>
  );
}

function LinePreview({ result }: ChartPreviewProps & { result: QueryResult }) {
  const xAxis = result.chart.x_axis;
  const yAxis = result.chart.y_axis;
  if (xAxis === null || yAxis === null || result.rows.length === 0) {
    return <p className="muted">line chart에 필요한 축을 찾지 못했습니다.</p>;
  }

  const seriesGroups = groupRowsBySeries(result.rows, result.chart.series_axis);
  const xLabels = uniqueLabels(result.rows.map((row) => String(row[xAxis] ?? "-")));
  const maxValue = Math.max(
    ...result.rows.map((row) => numericValue(row[yAxis])),
    1,
  );

  return (
    <div className="line-chart-wrap">
      <svg className="line-chart" viewBox="0 0 640 220" role="img" aria-label="Line chart preview">
        <path d="M 30 190 H 610" className="axis" />
        <path d="M 30 20 V 190" className="axis" />
        {seriesGroups.map((group, groupIndex) => {
          const points = buildLinePoints({ rows: group.rows, xAxis, yAxis, xLabels, maxValue });
          const path = linePath(points);
          const color = COLORS[groupIndex % COLORS.length];
          return (
            <g key={group.name}>
              <path d={path} className="line-path" style={{ stroke: color }} />
              {points.map((point) => (
                <circle
                  key={`${group.name}-${point.label}-${point.x}-${point.y}`}
                  cx={point.x}
                  cy={point.y}
                  r="4"
                  className="line-dot"
                  style={{ fill: color }}
                />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="legend-row">
        {seriesGroups.map((group, index) => (
          <span key={group.name} className="legend-item">
            <i style={{ background: COLORS[index % COLORS.length] }} />
            {group.name}
          </span>
        ))}
      </div>
      <p className="chart-caption">
        {xLabels[0] ?? "-"} → {xLabels.at(-1) ?? "-"}
      </p>
    </div>
  );
}

function groupRowsBySeries(rows: QueryRow[], seriesAxis: string | null): Array<{ name: string; rows: QueryRow[] }> {
  if (seriesAxis === null) {
    return [{ name: "result", rows }];
  }
  const grouped = new Map<string, QueryRow[]>();
  for (const row of rows) {
    const name = String(row[seriesAxis] ?? "unknown");
    const groupRows = grouped.get(name);
    if (groupRows === undefined) {
      grouped.set(name, [row]);
    } else {
      groupRows.push(row);
    }
  }
  return Array.from(grouped, ([name, groupRows]) => ({ name, rows: groupRows }));
}

function uniqueLabels(labels: string[]): string[] {
  return Array.from(new Set(labels));
}

function buildLinePoints({
  rows,
  xAxis,
  yAxis,
  xLabels,
  maxValue,
}: {
  rows: QueryRow[];
  xAxis: string;
  yAxis: string;
  xLabels: string[];
  maxValue: number;
}): ChartPoint[] {
  const width = 580;
  const step = xLabels.length <= 1 ? 0 : width / (xLabels.length - 1);
  return rows.map((row) => {
    const label = String(row[xAxis] ?? "-");
    const xIndex = Math.max(xLabels.indexOf(label), 0);
    return {
      label,
      x: 30 + step * xIndex,
      y: 190 - (numericValue(row[yAxis]) / maxValue) * 160,
    };
  });
}

function linePath(points: ChartPoint[]): string {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function seriesValue(row: QueryRow, seriesAxis: string | null): string | null {
  if (seriesAxis === null) {
    return null;
  }
  return String(row[seriesAxis] ?? "unknown");
}

function numericValue(value: QueryRow[string]): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatValue(value: QueryRow[string]): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return String(value);
}
