import type { ReactNode } from "react";

export type Column<T> = {
  key: keyof T;
  label: string;
  numeric?: boolean;
  format?: (value: T[keyof T], row: T) => ReactNode;
};

export default function RankingTable<T extends { symbol: string }>({
  columns,
  rows,
}: {
  columns: Column<T>[];
  rows: T[];
}) {
  if (rows.length === 0) {
    return (
      <div
        style={{
          border: "1px dashed var(--gridline)",
          borderRadius: 10,
          padding: "40px 20px",
          textAlign: "center",
          color: "var(--text-muted)",
        }}
      >
        No data yet — check back after the next scheduled scan.
      </div>
    );
  }

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 10,
        overflow: "auto",
        maxHeight: 640,
      }}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={String(col.key)}
                style={{
                  position: "sticky",
                  top: 0,
                  textAlign: col.numeric ? "right" : "left",
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--gridline)",
                  color: "var(--text-muted)",
                  fontWeight: 600,
                  fontSize: 12,
                  textTransform: "uppercase",
                  letterSpacing: 0.3,
                  background: "var(--surface-1)",
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={row.symbol}
              style={{ background: i % 2 === 0 ? "var(--surface-1)" : "var(--surface-2)" }}
            >
              {columns.map((col) => (
                <td
                  key={String(col.key)}
                  className={col.numeric ? "tabular-nums" : undefined}
                  style={{
                    padding: "9px 14px",
                    borderBottom: "1px solid var(--gridline)",
                    textAlign: col.numeric ? "right" : "left",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col.format ? col.format(row[col.key], row) : String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
