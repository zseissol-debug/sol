import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";
import Incoming from "./inbox/Incoming";
import Peers from "./inbox/Peers";
import Reports from "./inbox/Reports";

const HEAD: Record<string, { crumb: string; title: string; lead: string }> = {
  incoming: {
    crumb: "01 · 进项", title: "进来了什么",
    lead: "Newsletter、Clippings、我收藏的、我写的。值得做的点「拿来做」，它会进加工中。",
  },
  peers: {
    crumb: "01 · 进项 · 老师和对标", title: "老师和对标",
    lead: "老师是学理念的，对标是看要不要复刻的；点卡片上的「老师 / 对标」切换。他们新发的视频在「进来的」的「老师」「对标」两栏里，你自己去看。这里不自动拆任何一条：想拆就点那条的「拆解」。",
  },
  reports: {
    crumb: "01 · 进项 · 拆解报告", title: "拆解报告",
    lead: "我的视频和对标爆款的结构拆解。下面是拆解队列，贴任意抖音链接就能加。",
  },
};

export default function Inbox() {
  const tab = useLocation().pathname.split("/")[2] ?? "incoming";
  const head = HEAD[tab] ?? HEAD.incoming;
  const [reportCount, setReportCount] = useState<number | null>(null);
  useEffect(() => {
    const load = () => api.counts().then((c) => setReportCount(c.reports)).catch(() => undefined);
    load();
    window.addEventListener("studio:changed", load);
    return () => window.removeEventListener("studio:changed", load);
  }, []);

  const tabCls = ({ isActive }: { isActive: boolean }) => "tab" + (isActive ? " active" : "");
  return (
    <div>
      <div className="crumb">{head.crumb}</div>
      <h1 className="page">{head.title}</h1>
      <p className="lead">{head.lead}</p>
      <nav className="tabs">
        <NavLink to="/inbox/incoming" className={tabCls}>进来的</NavLink>
        <NavLink to="/inbox/peers" className={tabCls}>老师和对标</NavLink>
        <NavLink to="/inbox/reports" className={tabCls}>拆解报告{reportCount ? <small>{reportCount}</small> : null}</NavLink>
      </nav>
      <Routes>
        <Route index element={<Navigate to="incoming" replace />} />
        <Route path="incoming" element={<Incoming />} />
        <Route path="peers" element={<Peers />} />
        <Route path="reports" element={<Reports />} />
        <Route path="reports/:id" element={<Reports />} />
      </Routes>
    </div>
  );
}
