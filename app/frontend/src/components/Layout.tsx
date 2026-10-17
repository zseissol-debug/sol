import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import type { Counts } from "../types";

interface NavSpec { to: string; title: string; sub: string; badge?: (c: Counts | null) => number | null; hot?: boolean }

// 侧栏顺序与副标题取自原版 B 版界面；K 线日报 / 咨询客户 / 「我是谁」按需求不做
const FLOW: NavSpec[] = [
  { to: "/inbox", title: "进项", sub: "读进来什么", badge: (c) => c?.candidates ?? null },
  { to: "/working", title: "加工中", sub: "正在做哪几条", badge: (c) => c?.topics ?? null, hot: true },
  { to: "/pack", title: "打包", sub: "发布前准备好一切" },
  { to: "/publish", title: "发布", sub: "一个个平台发出去" },
  { to: "/sent", title: "已发出", sub: "数据和复盘" },
];

const PAGE_NAME: Record<string, string> = {
  "/inbox": "进项", "/working": "加工中", "/today": "今天", "/pack": "打包", "/publish": "发布",
  "/sent": "已发出", "/x": "单独一条线", "/traffic": "流量视频", "/settings": "设置",
};

export default function Layout() {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [anna, setAnna] = useState(false);
  const loc = useLocation();

  const refresh = useCallback(() => {
    api.counts().then(setCounts).catch(() => setCounts(null));
  }, []);
  useEffect(refresh, [loc.pathname, refresh]);
  useEffect(() => {
    window.addEventListener("studio:changed", refresh);
    return () => window.removeEventListener("studio:changed", refresh);
  }, [refresh]);

  const here = PAGE_NAME["/" + loc.pathname.split("/")[1]] ?? "";

  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><b>Sol's</b><small>内容工作台</small></div>
        <NavLink to="/today" className={({ isActive }) => "nav" + (isActive ? " active" : "")}>
          <span className="t"><b>今天</b><small>现在做哪一件</small></span>
        </NavLink>
        <div className="rail">
          {FLOW.map((n) => {
            const num = n.badge?.(counts) ?? null;
            return (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => "nav" + (isActive ? " active" : "")}>
                <span className="t"><b>{n.title}</b><small>{n.sub}</small></span>
                {num ? <span className={"badge" + (n.hot ? " hot" : "")}>{num}</span> : null}
              </NavLink>
            );
          })}
        </div>
        <hr />
        <NavLink to="/x" className={({ isActive }) => "nav" + (isActive ? " active" : "")}>
          <span className="t"><b>单独一条线</b><small>短帖打勾 · 长文</small></span>
        </NavLink>
        <NavLink to="/traffic" className={({ isActive }) => "nav" + (isActive ? " active" : "")}>
          <span className="t"><b>流量视频</b><small>看到就想转的，先存下来</small></span>
        </NavLink>
        <button className="nav" onClick={() => setAnna((v) => !v)}>
          <span className="t"><b>Anna</b><small>内容主编 · 叫她过来</small></span>
        </button>
        <div className="grow" />
        <NavLink to="/settings" className={({ isActive }) => "nav" + (isActive ? " active" : "")}>
          <span className="t"><b>设置与 Skills</b></span>
        </NavLink>
      </aside>

      <main className="main"><Outlet /></main>

      {anna && (
        <div className="drawer" role="dialog" aria-label="Anna">
          <header>
            <span><b>Anna</b> <span className="muted small">内容主编 · 正在看「{here || "—"}」</span></span>
            <button className="btn sm" onClick={() => setAnna(false)}>去忙吧</button>
          </header>
          <div className="body">
            <div className="note">
              Anna 还没接入 AI。接入后，这里会知道你正在看哪个页面，并能围绕当前页面的内容回答
              （原版的 Anna 标题下会写「正在看『加工中』」）。
            </div>
          </div>
          <footer>
            <input className="input" disabled placeholder="问 Anna…（回车发送，Shift+回车换行）" style={{ minWidth: 0 }} />
            <button className="btn primary" disabled>发送</button>
          </footer>
        </div>
      )}
    </div>
  );
}

export const notifyChanged = () => window.dispatchEvent(new Event("studio:changed"));
