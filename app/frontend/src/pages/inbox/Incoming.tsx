import { useState } from "react";
import Newsletter from "./Newsletter";

// 原版「进来的」有 8 个来源 Tab；K 线日报按需求不做。目前只接入了 AI 日报。
const SOURCES: { key: string; label: string; ready: boolean; why?: string }[] = [
  { key: "all", label: "全部", ready: true },
  { key: "daily", label: "AI 日报", ready: true },
  { key: "teachers", label: "老师", ready: false, why: "老师 / 对标账号的同步需要抖音登录，放在「老师和对标」那一期做" },
  { key: "peers", label: "对标", ready: false, why: "同上：每天 9:30 检查每个号最新一页，有新视频才进来" },
  { key: "raw", label: "自定义输入", ready: false, why: "你说一遍 → 存进 Obsidian 的原始输出，第 3 期做" },
  { key: "saved", label: "我收藏的", ready: false, why: "X 收藏、飞书收藏，需要对应平台的登录态" },
  { key: "clips", label: "Clippings", ready: false, why: "Obsidian Clippings 目录，后面按你的 vault 路径接" },
];

export default function Incoming() {
  const [src, setSrc] = useState("daily");
  const cur = SOURCES.find((s) => s.key === src)!;
  return (
    <div>
      <div className="subtabs">
        {SOURCES.map((s) => (
          <button key={s.key} className={"subtab" + (s.key === src ? " active" : "") + (s.ready ? "" : " off")} onClick={() => setSrc(s.key)}>
            {s.label}
          </button>
        ))}
      </div>
      {cur.ready ? (
        <Newsletter />
      ) : (
        <div className="card empty"><b>「{cur.label}」这一栏还没接入</b>{cur.why}</div>
      )}
    </div>
  );
}
