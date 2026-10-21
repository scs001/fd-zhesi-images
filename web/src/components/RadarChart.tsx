/**
 * 六轴雷达图 —— 原生 SVG，不引图表库。
 * 轴名来自投影 axes 的键（键序即轴序）；数值量纲未知（-1..1 / 0..1 / 0..100 / 其他），
 * 归一化到 [0,1] 后画多边形。
 */

function normalize(values: number[]): number[] {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min >= -1 && max <= 1) return values.map((v) => (v + 1) / 2); // -1..1 → 0..1
  if (min >= 0 && max <= 1) return values.map((v) => v); // 已是 0..1
  if (min >= 0 && max <= 100) return values.map((v) => v / 100); // 百分比
  const span = max - min || 1;
  return values.map((v) => (v - min) / span); // 其他线性量纲
}

const INK = "#171717"; // neutral-900
const GRID = "#e5e5e5"; // neutral-200

export default function RadarChart({
  axes,
  size = 340,
}: {
  axes: Record<string, number>;
  size?: number;
}) {
  const entries = Object.entries(axes);
  const n = entries.length;
  if (n < 3) return null;

  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 44; // 留标签边距
  const norm = normalize(entries.map(([, v]) => (Number.isFinite(v) ? v : 0)));

  const point = (i: number, radius: number) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    return [cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)] as const;
  };
  const ring = (f: number) =>
    Array.from({ length: n }, (_, i) => point(i, r * f).join(",")).join(" ");
  const valuePoly = norm.map((v, i) => point(i, r * Math.max(0, Math.min(1, v))).join(",")).join(" ");

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="mx-auto w-full max-w-sm"
      role="img"
      aria-label="radar"
    >
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={ring(f)} fill="none" stroke={GRID} strokeWidth="1" />
      ))}
      {Array.from({ length: n }, (_, i) => {
        const [x, y] = point(i, r);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={GRID} strokeWidth="1" />;
      })}
      <polygon points={valuePoly} fill={INK} fillOpacity="0.08" stroke={INK} strokeWidth="1.5" />
      {norm.map((v, i) => {
        const [x, y] = point(i, r * Math.max(0, Math.min(1, v)));
        return <circle key={i} cx={x} cy={y} r="2.5" fill={INK} />;
      })}
      {entries.map(([name], i) => {
        const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
        const [x, y] = point(i, r + 16);
        const cos = Math.cos(angle);
        const anchor = cos < -0.3 ? "end" : cos > 0.3 ? "start" : "middle";
        return (
          <text
            key={name}
            x={x}
            y={y}
            textAnchor={anchor}
            dominantBaseline="middle"
            fontSize="11"
            fill="#525252"
          >
            {name}
          </text>
        );
      })}
    </svg>
  );
}
