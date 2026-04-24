import type { QueryResult } from "../lib/api";

type ResultTableProps = {
  result: QueryResult | null;
};

export function ResultTable({ result }: ResultTableProps) {
  if (result === null) {
    return (
      <section className="table-panel empty-panel">
        <h2>Result table</h2>
        <p>아직 실행한 SQL 결과가 없습니다.</p>
      </section>
    );
  }

  return (
    <section className="table-panel">
      <div className="panel-header horizontal">
        <div>
          <h2>Result table</h2>
          <p>{result.rows.length} rows · {result.columns.length} columns</p>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {result.columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {result.columns.map((column) => (
                  <td key={column}>{formatCell(row[column])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatCell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return String(value);
}
