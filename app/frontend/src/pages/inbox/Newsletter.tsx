import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { notifyChanged } from "../../components/Layout";
import type { EngineStatus, Job, NewsIssue, NewsIssueBrief, NewsItem, NewsSection } from "../../types";

export default function Newsletter() {
  const [issues, setIssues] = useState<NewsIssueBrief[] | null>(null);
  const [id, setId] = useState<string | null>(null);
  const [issue, setIssue] = useState<NewsIssue | null>(null);
  const [busy, setBusy] = useState<"sync" | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [engine, setEngine] = useState<EngineStatus | "loading" | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const loadIssues = useCallback(async (select?: string) => {
    const list = await api.issues();
    setIssues(list);
    setId((cur) => select ?? cur ?? list[0]?.id ?? null);
  }, []);

  useEffect(() => { loadIssues().catch((e) => setMsg({ kind: "err", text: e.message })); }, [loadIssues]);
  useEffect(() => {
    if (!id) { setIssue(null); return; }
    api.issue(id).then(setIssue).catch((e) => setMsg({ kind: "err", text: e.message }));
  }, [id]);

  // 生成任务：轮询到结束
  useEffect(() => {
    if (!job || (job.state !== "queued" && job.state !== "running")) return;
    timer.current = window.setTimeout(async () => {
      try {
        const next = await api.job(job.id);
        setJob(next);
        if (next.state === "done") await loadIssues(String(next.result.issue_id ?? ""));
      } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); }
    }, 2000);
    return () => window.clearTimeout(timer.current);
  }, [job, loadIssues]);

  async function sync() {
    setBusy("sync"); setMsg(null);
    try {
      const r = await api.syncNewsletter();
      await loadIssues();
      setMsg({ kind: "ok", text: `已同步 Park 公开日报：取到 ${r.fetched} 期` });
    } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); } finally { setBusy(null); }
  }

  async function generate() {
    setMsg(null);
    try { setJob(await api.generateNewsletter()); } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); }
  }

  async function checkEngine() {
    setEngine("loading");
    try { setEngine(await api.engineStatus()); } catch (e) { setEngine(null); setMsg({ kind: "err", text: (e as Error).message }); }
  }

  async function addTopic(item: NewsItem) {
    if (!issue) return;
    try {
      const t = await api.topicFromNews(issue.id, item.id);
      setIssue((cur) => cur && {
        ...cur,
        sections: cur.sections.map((s) => ({
          ...s, groups: s.groups.map((g) => ({ ...g, items: g.items.map((i) => (i.id === item.id ? { ...i, topic_id: t.id } : i)) })),
        })),
      });
      notifyChanged();
    } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); }
  }

  const running = job && (job.state === "queued" || job.state === "running");

  return (
    <div>
      <div className="row" style={{ marginBottom: 14 }}>
        {issues && issues.length > 0 && (
          <select value={id ?? ""} onChange={(e) => setId(e.target.value)} style={{ padding: "5px 8px", borderRadius: 8 }}>
            {issues.map((i) => <option key={i.id} value={i.id}>{i.id} · {i.source === "local" ? "本地生成" : "Park 公开"} · 快讯 {i.brief_count}</option>)}
          </select>
        )}
        <span className="spacer" />
        <button className="btn" onClick={sync} disabled={busy === "sync"}>{busy === "sync" ? "同步中…" : "同步 Park 公开日报"}</button>
        <button className="btn" onClick={checkEngine}>检查日报引擎</button>
        <button className="btn primary" onClick={generate} disabled={!!running}>{running ? "生成中…" : "生成今日日报"}</button>
      </div>

      {msg && <div className={msg.kind === "ok" ? "note" : "err"} style={{ marginBottom: 12 }}>{msg.text}</div>}

      {engine && (
        <div className="card pad" style={{ marginBottom: 12 }}>
          {engine === "loading" ? "检查中…（会跑一次引擎的 doctor，最多一分钟）" : (
            <>
              <div className="row"><b>日报引擎</b>
                <span className={"tag " + (engine.doctor_ok ? "local" : "")}>
                  {!engine.installed ? "未安装" : !engine.configured ? "未配置" : engine.doctor_ok ? "可用" : "有缺项"}
                </span>
                <span className="spacer" />
                <button className="btn sm" onClick={() => setEngine(null)}>收起</button>
              </div>
              {engine.fix && <p className="muted" style={{ margin: "6px 0 0" }}>{engine.fix}</p>}
              {engine.doctor_output && <pre className="small mono" style={{ whiteSpace: "pre-wrap", margin: "8px 0 0" }}>{engine.doctor_output}</pre>}
            </>
          )}
        </div>
      )}

      {job && (
        <div className="card job" style={{ marginBottom: 12 }}>
          <div className="row">
            <b>生成今日日报</b>
            <span className={"tag " + (job.state === "done" ? "local" : "")}>
              {{ queued: "排队中", running: "运行中", done: "完成", failed: "失败" }[job.state]}
            </span>
            <span className="muted small">抓取来源 + AI 写日报，通常要十几分钟到半小时</span>
          </div>
          {job.error && <div className="err" style={{ marginTop: 8 }}>{job.error}</div>}
          {job.log.length > 0 && (
            <pre className="small mono muted" style={{ whiteSpace: "pre-wrap", margin: "8px 0 0", maxHeight: 140, overflow: "auto" }}>
              {job.log.slice(-12).join("\n")}
            </pre>
          )}
        </div>
      )}

      {issues && issues.length === 0 && (
        <div className="card empty">
          <b>还没有日报</b>
          点右上角「同步 Park 公开日报」，拉取 Park 每天公开的 AI 日报（RSS，最近约 30 期）；
          想自己生成，先点「检查日报引擎」看缺什么。
        </div>
      )}

      {issue && <IssueView issue={issue} newest={issues?.[0]?.id === issue.id} onAdd={addTopic} />}
    </div>
  );
}

function IssueView({ issue, newest, onAdd }: { issue: NewsIssue; newest: boolean; onAdd: (i: NewsItem) => void }) {
  const deepUrls = new Set(
    issue.sections.filter((s) => s.kind === "deep").flatMap((s) => s.groups.flatMap((g) => g.items.map((i) => i.url)).filter(Boolean) as string[]),
  );
  return (
    <div className="card issue">
      <div className="kicker">{newest ? "今天这一期" : issue.id}　<span className={"tag " + (issue.source === "local" ? "local" : "park")}>{issue.source === "local" ? "本地生成" : "Park 公开日报"}</span></div>
      <h2 className="title">{issue.title}</h2>
      <p className="muted small" style={{ margin: 0 }}>每条快讯单独入选题池：放进去的是那一条的原文（有深读就带上深读），不是整份日报。</p>
      {issue.sections.map((s) => <Section key={s.title} section={s} deepUrls={deepUrls} onAdd={onAdd} />)}
    </div>
  );
}

function Section({ section, deepUrls, onAdd }: { section: NewsSection; deepUrls: Set<string>; onAdd: (i: NewsItem) => void }) {
  const count = section.groups.reduce((n, g) => n + g.items.length, 0);
  const radar = section.kind === "radar";
  let seq = 0;
  return (
    <div>
      <div className="sec-title">{section.title}{count > 0 && <small>{count} 条</small>}</div>
      {section.groups.map((g, gi) => (
        <div key={gi}>
          {g.name && <div className="grp">{g.name}</div>}
          {g.items.map((item) => (
            <Entry key={item.id} item={item} kind={section.kind} n={radar ? ++seq : 0} hasDeep={section.kind === "brief" && !!item.url && deepUrls.has(item.url)} onAdd={onAdd} />
          ))}
        </div>
      ))}
      {section.text && <p className="muted" style={{ whiteSpace: "pre-wrap" }}>{section.text}</p>}
    </div>
  );
}

function Entry({ item, kind, n, hasDeep, onAdd }: { item: NewsItem; kind: NewsSection["kind"]; n: number; hasDeep: boolean; onAdd: (i: NewsItem) => void }) {
  const canTopic = kind === "brief"; // 原版：每条快讯单独入池；深读跟着快讯走，自己没有入池入口
  return (
    <div className={"item" + (kind === "deep" ? " deep" : "")}>
      {item.source && <div className="src">{item.source}</div>}
      <div className="ttl">
        {n > 0 && <span className="muted">{n}. </span>}
        {item.title}
        {item.url && <a className="ext" href={item.url} target="_blank" rel="noreferrer">原文 ↗</a>}
      </div>
      {item.summary && <p className="sum">{item.summary}</p>}
      {kind === "deep" && <div className="muted small">深读：跟着上面对应的快讯一起入选题池</div>}
      {canTopic && (
        <div className="acts">
          {item.topic_id ? (
            <Link className="btn sm done" to="/working">已在选题池 →</Link>
          ) : (
            <button className="btn sm primary" onClick={() => onAdd(item)}>入选题池</button>
          )}
          <button className="btn sm" disabled title="写 X 帖子需要接入 AI，后面做">发 X</button>
          {hasDeep && <span className="tag">含深读</span>}
        </div>
      )}
    </div>
  );
}
