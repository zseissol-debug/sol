export const LABEL_COLORS: Record<string, string> = {
  钩子: "#e0a93b", 承诺: "#8b8f98", 论点: "#3f8f6b", 案例: "#4a74c9",
  跑题: "#c0432b", 收束: "#8f6cc2", 引导: "#5d6572",
};
export const labelColor = (label: string) => LABEL_COLORS[label] ?? "#5d6572";

export function fmtTime(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
export const fmtClock = (sec: number) => fmtTime(sec); // 原版显示 0:00 / 7:28，不补零

export function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const int = (v: number) => v.toLocaleString("en-US");

/** facts 里的数值 → 展示文案；缺失（如新号不给倍数）显示破折号 */
export function fmtFact(key: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (key === "multiple_of_median") return `${value}×`;
  if (key.endsWith("_per_like") || key === "like_per_view") return pct(value);
  return int(value);
}
