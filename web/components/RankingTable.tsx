import type { ReactNode } from "react";

export type Column<T> = {
  key: keyof T;
  label: string;
  numeric?: boolean;
  /** Render as a magnitude bar + value, scaled across the visible rows. */
  meter?: boolean;
  format?: (value: T[keyof T], row: T) => ReactNode;
};

function Meter({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className="meter">
      <span className="meter-val">{value.toFixed(1)}</span>
      <span className="meter-track">
        <span
          className={`meter-fill${value < 0 ? " is-neg" : ""}`}
          style={{ width: `${value < 0 ? 4 : pct}%` }}
        />
      </span>
    </div>
  );
}

export default function RankingTable<T extends { symbol: string }>({
  columns,
  rows,
  rankOffset = 1,
}: {
  columns: Column<T>[];
  rows: T[];
  rankOffset?: number;
}) {
  if (rows.length === 0) {
    return <div className="empty">No data yet — check back after the next scheduled scan.</div>;
  }

  // Scale every meter column against the strongest value on screen.
  const maxima = new Map<keyof T, number>();
  for (const col of columns) {
    if (!col.meter) continue;
    maxima.set(col.key, Math.max(...rows.map((r) => Number(r[col.key]) || 0), 0));
  }

  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th aria-label="Rank" />
            {columns.map((col) => (
              <th key={String(col.key)} className={col.numeric || col.meter ? "is-num" : undefined}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.symbol}>
              <td className="rank">{i + rankOffset}</td>
              {columns.map((col) => (
                <td
                  key={String(col.key)}
                  className={col.numeric || col.meter ? "is-num" : undefined}
                >
                  {col.meter ? (
                    <Meter value={Number(row[col.key]) || 0} max={maxima.get(col.key) ?? 0} />
                  ) : col.format ? (
                    col.format(row[col.key], row)
                  ) : (
                    <span className={col.key === "symbol" ? "sym" : undefined}>
                      {String(row[col.key])}
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
