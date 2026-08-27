import { useId } from "react";

export interface ChartSeries {
  name: string;
  points: Array<{ date: string; value: number }>;
}

const PALETTE = ["#2dd4bf", "#60a5fa", "#f59e0b", "#c084fc", "#fb7185", "#94a3b8"];

function compact(value: number): string {
  return new Intl.NumberFormat("zh-TW", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function percent(value: number): string {
  return new Intl.NumberFormat("zh-TW", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}

function dateTimestamp(value: string): number {
  return Date.parse(`${value}T00:00:00Z`);
}

function monthLabel(timestamp: number): string {
  return new Date(timestamp).toISOString().slice(0, 7);
}

export function LineChart({
  series,
  yFormat = "number",
  logScale = false,
  height = 330,
  title,
}: {
  series: ChartSeries[];
  yFormat?: "number" | "percent";
  logScale?: boolean;
  height?: number;
  title: string;
}) {
  const titleId = useId();
  const width = 1000;
  const padding = { top: 26, right: 24, bottom: 54, left: 84 };
  const drawablePoints = series.flatMap((item) =>
    item.points.filter(
      (point) =>
        Number.isFinite(point.value) &&
        Number.isFinite(dateTimestamp(point.date)) &&
        (!logScale || point.value > 0),
    ),
  );
  const values = drawablePoints.map((point) => point.value);
  const timestamps = drawablePoints.map((point) => dateTimestamp(point.date));
  const usableValues = logScale ? values.filter((value) => value > 0) : values;
  const minimum = usableValues.length ? Math.min(...usableValues) : 0;
  const maximum = usableValues.length ? Math.max(...usableValues) : 1;
  const low = logScale ? Math.log(Math.max(minimum, Number.MIN_VALUE)) : minimum;
  const high = logScale ? Math.log(Math.max(maximum, Number.MIN_VALUE)) : maximum;
  const span = Math.max(high - low, Math.abs(high) * 0.02, 1e-9);
  const domainStart = timestamps.length ? Math.min(...timestamps) : 0;
  const domainEnd = timestamps.length ? Math.max(...timestamps) : domainStart;
  const domainSpan = domainEnd - domainStart;
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const x = (date: string) => {
    const timestamp = dateTimestamp(date);
    if (!Number.isFinite(timestamp) || domainSpan <= 0) {
      return padding.left + innerWidth / 2;
    }
    return padding.left + ((timestamp - domainStart) / domainSpan) * innerWidth;
  };
  const y = (value: number) => {
    const transformed = logScale ? Math.log(Math.max(value, Number.MIN_VALUE)) : value;
    return padding.top + (1 - (transformed - low) / span) * innerHeight;
  };
  const ticks = Array.from({ length: 5 }, (_, index) => {
    const ratio = index / 4;
    const transformed = high - ratio * span;
    return logScale ? Math.exp(transformed) : transformed;
  });
  const dateLabels = domainSpan > 0
    ? [
        { timestamp: domainStart, anchor: "start" as const },
        { timestamp: domainStart + domainSpan / 2, anchor: "middle" as const },
        { timestamp: domainEnd, anchor: "end" as const },
      ]
    : timestamps.length
      ? [{ timestamp: domainStart, anchor: "middle" as const }]
      : [];

  if (!series.length || !values.length) {
    return <div className="empty-chart">尚無可繪製資料。</div>;
  }

  return (
    <figure className="chart-frame" aria-labelledby={titleId}>
      <figcaption id={titleId} className="sr-only">
        {title}
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={titleId}>
        <g aria-hidden="true">
          {ticks.map((tick, index) => {
            const coordinate = padding.top + (index / 4) * innerHeight;
            return (
              <g key={`${tick}-${index}`}>
                <line
                  x1={padding.left}
                  x2={width - padding.right}
                  y1={coordinate}
                  y2={coordinate}
                  className="chart-grid"
                />
                <text x={padding.left - 12} y={coordinate + 5} textAnchor="end" className="chart-axis">
                  {yFormat === "percent" ? percent(tick) : compact(tick)}
                </text>
              </g>
            );
          })}
          {dateLabels.map((label) => (
            <text
              key={`${label.timestamp}-${label.anchor}`}
              x={
                domainSpan > 0
                  ? padding.left + ((label.timestamp - domainStart) / domainSpan) * innerWidth
                  : padding.left + innerWidth / 2
              }
              y={height - 18}
              textAnchor={label.anchor}
              className="chart-axis"
            >
              {monthLabel(label.timestamp)}
            </text>
          ))}
        </g>
        {series.map((item, seriesIndex) => {
          const points = item.points.filter(
            (point) =>
              Number.isFinite(point.value) &&
              Number.isFinite(dateTimestamp(point.date)) &&
              (!logScale || point.value > 0),
          );
          const path = points
            .map((point, index) => `${index ? "L" : "M"}${x(point.date).toFixed(2)},${y(point.value).toFixed(2)}`)
            .join(" ");
          return (
            <path
              key={item.name}
              d={path}
              fill="none"
              stroke={PALETTE[seriesIndex % PALETTE.length]}
              strokeWidth="3"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>
      <div className="chart-legend" aria-label="圖例">
        {series.map((item, index) => (
          <span key={item.name}>
            <i style={{ background: PALETTE[index % PALETTE.length] }} />
            {item.name}
          </span>
        ))}
      </div>
    </figure>
  );
}

export function BarChart({
  labels,
  values,
  title,
}: {
  labels: string[];
  values: number[];
  title: string;
}) {
  const titleId = useId();
  const width = 1000;
  const height = 320;
  const padding = { top: 24, right: 24, bottom: 68, left: 70 };
  const maximum = Math.max(...values.map((value) => Math.abs(value)), 0.01);
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const zero = padding.top + innerHeight / 2;
  const slot = innerWidth / Math.max(labels.length, 1);
  return (
    <figure className="chart-frame" aria-labelledby={titleId}>
      <figcaption id={titleId} className="sr-only">
        {title}
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={titleId}>
        <line x1={padding.left} x2={width - padding.right} y1={zero} y2={zero} className="chart-grid strong" />
        {values.map((value, index) => {
          const barHeight = (Math.abs(value) / maximum) * (innerHeight / 2 - 8);
          const y = value >= 0 ? zero - barHeight : zero;
          return (
            <g key={`${labels[index] ?? index}-${value}`}>
              <rect
                x={padding.left + index * slot + slot * 0.17}
                y={y}
                width={slot * 0.66}
                height={Math.max(barHeight, 1)}
                className={value >= 0 ? "chart-bar positive" : "chart-bar negative"}
                rx="3"
              />
              <text
                x={padding.left + index * slot + slot / 2}
                y={height - 35}
                textAnchor="middle"
                className="chart-axis"
              >
                {labels[index]}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

export function MonthlyHeatmap({
  periods,
}: {
  periods: Array<{ period: string; value: number; partial: boolean }>;
}) {
  const rows = new Map<string, Map<number, { value: number; partial: boolean }>>();
  for (const item of periods) {
    const [yearText, monthText] = item.period.split("-");
    const year = yearText ?? "";
    const month = Number(monthText);
    if (!year || !month) continue;
    const row = rows.get(year) ?? new Map<number, { value: number; partial: boolean }>();
    row.set(month, { value: item.value, partial: item.partial });
    rows.set(year, row);
  }
  const years = [...rows.keys()].sort();
  if (!years.length) return <div className="empty-chart">尚無月報酬資料。</div>;
  return (
    <div className="heatmap-wrap" role="region" aria-label="月報酬熱圖" tabIndex={0}>
      <table className="heatmap-table">
        <thead>
          <tr>
            <th scope="col">年度</th>
            {Array.from({ length: 12 }, (_, index) => (
              <th scope="col" key={index}>{index + 1}月</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {years.map((year) => (
            <tr key={year}>
              <th scope="row">{year}</th>
              {Array.from({ length: 12 }, (_, index) => {
                const value = rows.get(year)?.get(index + 1);
                if (!value) return <td key={index}>—</td>;
                const intensity = Math.min(Math.abs(value.value) / 0.15, 1);
                const background = value.value >= 0
                  ? `color-mix(in srgb, var(--positive) ${Math.round(18 + intensity * 62)}%, transparent)`
                  : `color-mix(in srgb, var(--negative) ${Math.round(18 + intensity * 62)}%, transparent)`;
                return (
                  <td key={index} style={{ background }} title={`${year}-${String(index + 1).padStart(2, "0")}: ${percent(value.value)}`}>
                    {percent(value.value)}{value.partial ? "*" : ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="table-note">* 表示不完整月份。</p>
    </div>
  );
}
