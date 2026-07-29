import type { ReactNode } from "react";

export type Column<T> = {
  key: keyof T;
  label: string;
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
    return <p style={{ color: "#57606a" }}>No data yet — check back after the next scheduled scan.</p>;
  }

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th
              key={String(col.key)}
              style={{
                textAlign: "left",
                padding: "8px 12px",
                borderBottom: "2px solid #d0d7de",
                color: "#57606a",
                fontWeight: 600,
              }}
            >
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={row.symbol} style={{ backgroundColor: i % 2 === 0 ? "#fff" : "#f6f8fa" }}>
            {columns.map((col) => (
              <td key={String(col.key)} style={{ padding: "8px 12px", borderBottom: "1px solid #eaeef2" }}>
                {col.format ? col.format(row[col.key], row) : String(row[col.key])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
