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
    <div className="tile">
      <span className="label">{label}</span>
      <span className="tile-value num">{value}</span>
      {sub && <span className="tile-sub num">{sub}</span>}
    </div>
  );
}
