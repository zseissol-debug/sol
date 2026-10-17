import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { notifyChanged } from "../components/Layout";
import type { Stage, Topic } from "../types";

const STAGES: Stage[] = ["选题", "提纲", "录制", "剪辑", "待发", "已发出"];
const ORIGIN: Record<string, string> = { news: "来自日报", report: "来自拆解", manual: "手动添加" };

export default function Working() {
  const navigate = useNavigate();
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [focal, setFocal] = useState<Topic | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const ts = await api.topics();
      setTopics(ts);
      const focusedTopic = ts.find((t) => t.focal);
      setFocal(focusedTopic ?? null);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("studio:changed", load);
    return () => window.removeEventListener("studio:changed", load);
  }, [load]);

  async function run(fn: () => Promise<unknown>) {
    try {
      setError(null);
      await fn();
      await load();
      notifyChanged();
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  async function selectTopic(t: Topic) {
    await run(() => api.setFocalTopic(t.id));
  }

  function openDetail(t: Topic) {
    navigate(`/working/${t.id}`);
  }

  async function changeStage(newStage: Stage) {
    if (!focal) return;
    await run(() => api.patchTopic(focal.id, { stage: newStage }));
  }

  async function unfocus() {
    if (!focal) return;
    await run(() => api.clearFocalTopic());
  }

  return (
    <div>
      <div className="crumb warm">02 · 加工中</div>
      <h1 className="page">今天做哪一条</h1>
      <p className="lead">任何时候只做一条：选题 → 提纲 → 录制是你的，剪辑和待发交给机器和别人。其他的都在选题池里等。</p>
      {error && <div className="err" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="work-grid">
        {/* 左栏：选题池 */}
        <div className="card">
          <h3 style={{ margin: 0, padding: "16px 18px 8px", display: "flex", justifyContent: "space-between" }}>
            <span>选题池 {topics?.filter((t) => t.status === "pool").length ?? 0}</span>
            <span className="muted small" style={{ fontWeight: 400 }}>从「进项」入池</span>
          </h3>
          {topics?.filter((t) => t.status === "pool").length === 0 && (
            <div className="empty"><b>选题池是空的</b>去「进项」里挑一条，点「入选题池」。</div>
          )}
          {topics
            ?.filter((t) => t.status === "pool")
            .map((t) => (
              <div
                key={t.id}
                className={`topic ${t.focal ? "focal" : ""}`}
                onClick={() => selectTopic(t)}
                style={{ cursor: "pointer" }}
              >
                <div className="row">
                  <span className="tag">{t.stage}</span>
                  <span className="tag">{ORIGIN[t.origin.kind]}</span>
                  <span className="spacer" />
                  <button
                    className="btn sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      run(() => api.patchTopic(t.id, { status: "trash" }));
                    }}
                  >
                    不做了
                  </button>
                </div>
                <div className="tt">{t.title}</div>
                {t.excerpt && <div className="ex">{t.excerpt}</div>}
              </div>
            ))}
        </div>

        {/* 右上：焦点卡 + 进度条 */}
        <div className="card pad">
          {focal ? (
            <>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ margin: "0 0 8px 0", fontSize: 16 }}>{focal.title}</h3>
                <div className="stagebar">
                  {STAGES.map((s) => {
                    const completed = STAGES.indexOf(focal.stage) > STAGES.indexOf(s);
                    const isCurrent = focal.stage === s;
                    return (
                      <span
                        key={s}
                        onClick={() => changeStage(s)}
                        style={{
                          cursor: "pointer",
                          opacity: isCurrent ? 1 : completed ? 0.6 : 0.4,
                          fontWeight: isCurrent ? 600 : 400,
                        }}
                        title={`点击切换到「${s}」`}
                      >
                        {completed ? "●" : isCurrent ? "◯" : "○"} {s}
                      </span>
                    );
                  })}
                </div>
              </div>

              <div className="row" style={{ gap: 8, marginTop: 16 }}>
                <button
                  className="btn blue"
                  onClick={() => openDetail(focal)}
                >
                  打开
                </button>
                {focal.stage !== "提纲" && (
                  <button
                    className="btn"
                    onClick={() => changeStage("提纲")}
                  >
                    退回提纲
                  </button>
                )}
                <button
                  className="btn"
                  onClick={unfocus}
                >
                  放回选题池
                </button>
              </div>
            </>
          ) : (
            <div style={{ textAlign: "center", color: "#999", padding: "32px 16px" }}>
              <p>
                <b>正在做的这一条</b>
              </p>
              <p className="small muted">从左边选题池点一条来设为焦点卡</p>
            </div>
          )}

          <h3 style={{ margin: "22px 0 4px", fontSize: 15 }}>接下来拍</h3>
          <p className="muted small" style={{ margin: 0 }}>拖进日历排期、后面的整列往后挪、漏拍自动顺延——第 3 期。</p>
        </div>
      </div>
    </div>
  );
}
