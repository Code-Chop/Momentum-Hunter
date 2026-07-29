export default function StatTile({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "14px 18px",
        minWidth: 140,
      }}
    >
      <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </div>
      <div className="tabular-nums" style={{ fontSize: 22, fontWeight: 600, marginTop: 4 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>{sub}</div>
      )}
    </div>
  );
}
