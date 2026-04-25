export type ChartKind = "bar" | "line" | "table" | "metric" | "pie";
export type ColumnKind = "dimension" | "metric" | "temporal";
export type DatasetOrigin = "builtin" | "view_table";
export type ExploreJoinType = "inner" | "left";
export type ExploreOrderDirection = "asc" | "desc";
export type QueryCell = string | number | boolean | null;
export type QueryRow = Record<string, QueryCell>;

export type DatasetColumn = {
  name: string;
  label: string;
  kind: ColumnKind;
};

export type Dataset = {
  name: string;
  label: string;
  description: string;
  columns: DatasetColumn[];
  origin: DatasetOrigin;
};

export type ViewTable = {
  name: string;
  description: string;
  source_sql: string;
  columns: DatasetColumn[];
};

export type QueryResult = {
  columns: string[];
  rows: QueryRow[];
  chart: {
    chart_kind: ChartKind;
    x_axis: string | null;
    y_axis: string | null;
    series_axis: string | null;
  };
};

export type ExploreQueryRequest = {
  dataset: string;
  columns: string[];
  joins: Array<{
    dataset: string;
    left_column: string;
    right_column: string;
    join_type: ExploreJoinType;
  }>;
  order_by: string | null;
  order_direction: ExploreOrderDirection;
  row_limit: number;
};

type CreateViewTableRequest = {
  name: string;
  description: string;
  sourceSql: string;
};

type AnalyticsErrorPayload = {
  error_code?: string;
  message?: string;
  rejected_reason?: string | null;
};

const ANALYTICS_API_BASE_PATH = "/api/analytics";
const JSON_HEADERS = { "content-type": "application/json" };

export async function fetchDatasets(): Promise<Dataset[]> {
  return analyticsRequest<Dataset[]>("/datasets");
}

export async function fetchViewTables(): Promise<ViewTable[]> {
  return analyticsRequest<ViewTable[]>("/view-tables");
}

export async function runAnalyticsQuery(sql: string): Promise<QueryResult> {
  return analyticsRequest<QueryResult>("/query", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ sql, row_limit: 500 }),
  });
}

export async function runExploreQuery(
  request: ExploreQueryRequest,
): Promise<QueryResult> {
  return analyticsRequest<QueryResult>("/explore-query", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(request),
  });
}

export async function previewViewTable(sourceSql: string): Promise<QueryResult> {
  return analyticsRequest<QueryResult>("/view-tables/preview", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ source_sql: sourceSql, row_limit: 50 }),
  });
}

export async function createViewTable({
  name,
  description,
  sourceSql,
}: CreateViewTableRequest): Promise<Dataset> {
  return analyticsRequest<Dataset>("/view-tables", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      name,
      description,
      source_sql: sourceSql,
    }),
  });
}

export async function deleteViewTable(name: string): Promise<void> {
  await analyticsRequest<void>(`/view-tables/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

async function analyticsRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${ANALYTICS_API_BASE_PATH}${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await analyticsErrorMessage(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function analyticsErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as AnalyticsErrorPayload;
    return payload.message ?? `Analytics request failed (${response.status})`;
  } catch {
    return `Analytics request failed (${response.status})`;
  }
}
