import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { notifyChanged } from "../../components/Layout";
import { fmtClock, fmtDate, fmtFact, fmtTime, labelColor, LABEL_COLORS } from "../../format";
import type { EnvCheck, Job, Report, ReportBrief } from "../../types";

const STEPS: [string, string][] = [["downloading", "下载"], ["transcribing", "转文字"], ["analyzing", "拆结构"]];

export default function Reports() {
  const { id } = useParams();
  const nav = useNavigate();
  const [list, setList] = useState<ReportBrief[] | null>(null);
  const [archived, setArchived] = useState<ReportBrief[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [env, setEnv] = useState<EnvCheck[] | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [syncing, setSyncing] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  const load = useCallback(async () => {
    const [live, arch] = await Promise.all([api.reports(false), api.reports(true)]);
    setList(live);
    setArchived(arch);
    return live;
  }, []);

  useEffect(() => { load().catch((e) => setMsg({ kind: "err", text: e.message })); }, [load]);

  // 没选中时默认打开最新一份
  useEffect(() => {
    if (!id && list && list.length > 0) nav(`/inbox/reports/${list[0].id}`, { replace: true });
  }, [id, list, nav]);

  // 页面刷新后接上还在跑的拆解任务
  useEffect(() => {
    api.jobs().then((js) => {
      const active = js.find((j) => j.kind === "teardown" && (j.state === "queued" || j.state === "running"));
      if (active) setJob(active);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!job || (job.state !== "queued" && job.state !== "running")) return;
    timer.current = window.setTimeout(async () => {
      try {
        const next = await api.job(job.id);
        setJob(next);
        if (next.state === "done") {
          await load();
          notifyChanged();
          nav(`/inbox/reports/${String(next.result.report_id)}`);
        }
      } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); }
    }, 1500);
    return () => window.clearTimeout(timer.current);
  }, [job, load, nav]);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    const u = url.trim();
    if (!u) return;
    setMsg(null);
    try {
      setJob(await api.startTeardown(u));
      setUrl("");
    } catch (err) { setMsg({ kind: "err", text: (err as Error).message }); }
  }

  async function syncPublic() {
    setSyncing(true); setMsg(null);
    try {
      const r = await api.syncReports();
      await load();
      notifyChanged();
      setMsg({ kind: "ok", text: `已导入 Park 公开拆解库：取到 ${r.fetched} 份（标注为「Park 公开库」，原话版权归原作者，仅供学习）` });
    } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); } finally { setSyncing(false); }
  }

  async function checkEnv() {
    try { setEnv(await api.teardownEnv()); } catch (e) { setMsg({ kind: "err", text: (e as Error).message }); }
  }

  const running = job && (job.state === "queued" || job.state === "running");
  const rows = showArchived ? archived : list ?? [];

  return (
    <div>
      <form className="row" onSubmit={start} style={{ marginBottom: 12 }}>
        <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="贴任意抖音链接，回车拆解（例：https://v.douyin.com/xxxx/）" />
        <button className="btn primary" disabled={!url.trim()}>拆解</button>
        <button type="button" className="btn" onClick={checkEnv}>检查拆解环境</button>
        <button type="button" className="btn" onClick={syncPublic} disabled={syncing}>{syncing ? "导入中…" : "导入 Park 公开拆解库"}</button>
      </form>

      {msg && <div className={msg.kind === "ok" ? "note" : "err"} style={{ marginBottom: 12 }}>{msg.text}</div>}

      {env && (
        <div className="card pad" style={{ marginBottom: 12 }}>
          <div className="row"><b>拆解环境</b><span className="spacer" /><button className="btn sm" onClick={() => setEnv(null)}>收起</button></div>
          <ul className="checks">
            {env.map((c) => (
              <li key={c.key}>{c.ok ? "✓" : "✗"} {c.label}{!c.ok && c.fix && <span className="fix">→ {c.fix}</span>}</li>
            ))}
          </ul>
        </div>
      )}

      {job && <JobStrip job={job} />}

      {list && list.length === 0 && archived.length === 0 && !running && (
        <div className="card empty">
          <b>还没有拆解报告</b>
          贴一条抖音链接拆解（需要先配好抖音 cookies 和 AI，点「检查拆解环境」看缺什么）；
          或者先点「导入 Park 公开拆解库」，看他拆好的 50 份是什么样。
        </div>
      )}

      {(list?.length || archived.length) ? (
        <div className="rep-grid">
          <div className="card rep-list">
            <h3>
              <span>{showArchived ? "已归档" : "拆过的"} {rows.length}{!showArchived && <small className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>最新在上</small>}</span>
              <button className="btn sm" onClick={() => setShowArchived((v) => !v)}>{showArchived ? "返回" : `已归档 ${archived.length}`}</button>
            </h3>
            {rows.map((r) => (
              <button key={r.id} className={"rep-row" + (r.id === id ? " active" : "")} onClick={() => nav(`/inbox/reports/${r.id}`)}>
                <div className="a">{r.author ?? "未知作者"}{r.source === "park_public" && <span className="tag park" style={{ marginLeft: 6 }}>Park 公开库</span>}</div>
                <div className="t">{r.title}</div>
                <div className="m">{fmtDate(r.generated_at)} · {r.multiple != null ? `${r.multiple}×` : "无倍数"}</div>
              </button>
            ))}
          </div>
          {id ? <ReportView id={id} onChanged={() => { load(); notifyChanged(); }} /> : <div />}
        </div>
      ) : null}
    </div>
  );
}

function JobStrip({ job }: { job: Job }) {
  const idx = STEPS.findIndex(([k]) => k === job.stage);
  return (
    <div className="card job" style={{ marginBottom: 12 }}>
      <div className="row">
        <b>拆解</b><span className="muted small" style={{ wordBreak: "break-all" }}>{job.input}</span>
        <span className="spacer" />
        <span className={"tag " + (job.state === "done" ? "local" : "")}>{{ queued: "排队中", running: "进行中", done: "完成", failed: "失败" }[job.state]}</span>
      </div>
      <div className="steps" style={{ marginTop: 10 }}>
        {STEPS.map(([k, label], i) => {
          const cls = job.state === "done" || i < idx ? "ok" : i === idx && job.state === "running" ? "cur" : i === idx && job.state === "failed" ? "fail" : "";
          return <span key={k} className={"step " + cls}>{i + 1} {label}</span>;
        })}
      </div>
      {job.error && (
        <div className="err" style={{ marginTop: 10 }}>
          {job.error}
          {"\n"}<span className="muted">排查：点上面的「检查拆解环境」，会逐项说明缺什么（抖音 cookies、AI、转写）。</span>
        </div>
      )}
    </div>
  );
}

function ReportView({ id, onChanged }: { id: string; onChanged: () => void }) {
  const [r, setR] = useState<Report | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [flash, setFlash] = useState<number | null>(null);

  useEffect(() => {
    setR(null); setErr(null);
    api.report(id).then(setR).catch((e) => setErr(e.message));
  }, [id]);

  if (err) return <div className="err">{err}</div>;
  if (!r) return <div className="card empty">加载中…</div>;

  const dur = r.duration_seconds || r.segments[r.segments.length - 1]?.end || 1;
  const labels = Array.from(new Set(r.segments.map((s) => s.label)));

  async function toTopic() {
    const t = await api.topicFromReport(r!.id);
    setR({ ...r!, topic_id: t.id });
    notifyChanged();
  }
  async function toggleArchive() {
    setR(await api.archiveReport(r!.id, !r!.archived));
    onChanged();
  }
  function jump(i: number) {
    document.getElementById(`seg-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlash(i);
    window.setTimeout(() => setFlash(null), 1200);
  }

  const metric = (k: string, label: string, hot = false) => {
    const v = r.facts[k];
    const missing = v === null || v === undefined;
    return (
      <div className="metric" key={k} title={missing && k === "multiple_of_median" ? "作者不到 20 条，或点赞中位数不到 50 赞，不给倍数" : undefined}>
        <div className="k">{label}</div>
        <div className={"v" + (hot && !missing ? " hot" : "") + (missing ? " dim" : "")}>{fmtFact(k, v)}</div>
      </div>
    );
  };

  return (
    <div>
      <div className="card rep-head">
        <div className="row">
          <span className="by">{r.source === "park_public" ? "对标拆解 · " : "拆解 · "}{r.author ?? "未知作者"}</span>
          <span className={"tag " + (r.source === "local" ? "local" : "park")}>{r.source === "local" ? "本地拆解" : "Park 公开库"}</span>
          <span className="spacer" />
          {r.topic_id ? <Link className="btn done" to="/working">在选题池里 →</Link> : <button className="btn primary" onClick={toTopic}>入选题池</button>}
          <button className="btn" onClick={toggleArchive}>{r.archived ? "取消归档" : "看完了，归档"}</button>
          {r.source_url && <a className="btn" href={r.source_url} target="_blank" rel="noreferrer">在抖音打开 ↗</a>}
        </div>
        <h2>{r.title}</h2>
        <div className="muted small">时长 {fmtTime(dur)} · 生成于 {fmtDate(r.generated_at)}</div>
        <div className="metrics">
          {metric("multiple_of_median", "账号中位数倍数", true)}
          {metric("likes", "点赞")}
          {metric("collect_per_like", "收藏/赞")}
          {metric("share_per_like", "转发/赞")}
          {metric("comment_per_like", "评论/赞")}
          {metric("account_median_likes", "账号点赞中位数")}
        </div>
      </div>

      {r.opening && (
        <div className="card pad" style={{ marginTop: 18 }}>
          <b>观众平均看到的前 {Math.round(r.opening.seconds)} 秒</b>
          <p style={{ margin: "6px 0" }}>{r.opening.analysis}</p>
          {r.opening.transcript && <p className="muted small" style={{ margin: 0 }}>这段原文：{r.opening.transcript}</p>}
        </div>
      )}

      <div className="rep-cols">
        <div className="card panel">
          <h3><span>主线结构</span><span className="muted small" style={{ fontWeight: 400 }}>跑题 {Math.round(r.drift_seconds)} 秒 · 占 {Math.round(r.drift_share * 100)}%</span></h3>
          <div className="thesis">
            {r.thesis.text}
            {r.thesis.evidence[0] && <span className="ev">证据：[{fmtClock(r.thesis.evidence[0].start)}] {r.thesis.evidence[0].quote}</span>}
          </div>
          <div className="band">
            {r.segments.map((s) => (
              <button
                key={s.index}
                className={s.drift ? "drift" : ""}
                style={{ flex: Math.max(s.end - s.start, 0.5), background: labelColor(s.label) }}
                title={`${fmtClock(s.start)}–${fmtClock(s.end)} ${s.label}\n${s.summary}`}
                onClick={() => jump(s.index)}
              >
                {(s.end - s.start) / dur > 0.07 ? s.label : ""}
              </button>
            ))}
          </div>
          <div className="axis"><span>0:00</span><span>{fmtTime(dur / 2)}</span><span>{fmtTime(dur)}</span></div>
          <div className="legend">
            {labels.map((l) => <span key={l}><i style={{ background: LABEL_COLORS[l] ?? "#5d6572" }} />{l}</span>)}
            <span style={{ color: "var(--red)" }}>斜纹 = 不服务主线</span>
          </div>
          {r.segments.map((s) => (
            <div key={s.index} id={`seg-${s.index}`} className={"seg" + (flash === s.index ? " flash" : "")}>
              <div className="tm">{fmtClock(s.start)}</div>
              <div className="lb" style={{ color: labelColor(s.label) }}>{s.label}</div>
              <div>
                <div className="sm">{s.summary}</div>
                <div className={"rs" + (s.drift ? " drift" : "")}>{s.drift ? "不服务主线：" : ""}{s.reason}</div>
                {s.text && (
                  <details>
                    <summary>展开这段原文（{fmtClock(s.start)}–{fmtClock(s.end)}）</summary>
                    <p>{s.text}</p>
                  </details>
                )}
              </div>
            </div>
          ))}
        </div>

        <div>
          <div className="card panel">
            <h3><span>为什么爆</span></h3>
            {r.why_boom.map((c, i) => <Why key={i} c={c} />)}
          </div>
          {r.why_scatter.length > 0 && (
            <div className="card panel" style={{ marginTop: 18 }}>
              <h3><span>为什么散</span></h3>
              {r.why_scatter.map((c, i) => <Why key={i} c={c} />)}
            </div>
          )}
          {r.hypothesis_note && <div className="note" style={{ marginTop: 18 }}>{r.hypothesis_note}</div>}
        </div>
      </div>
    </div>
  );
}

function Why({ c }: { c: Report["why_boom"][number] }) {
  return (
    <div className="why">
      <p>{c.text}</p>
      {c.evidence[0] && <div className="ev"><span className="ts">{fmtClock(c.evidence[0].start)}</span>{c.evidence[0].quote}</div>}
    </div>
  );
}
