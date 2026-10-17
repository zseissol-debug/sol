import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { notifyChanged } from "../../components/Layout";
import type { Stage, Topic, Report } from "../../types";

const STAGES: Stage[] = ["选题", "提纲", "录制", "剪辑", "待发", "已发出"];

interface CreationDetailProps {
  data?: { topic: Topic; report: Report | null };
}

export default function CreationDetail({ data: initialData }: CreationDetailProps) {
  const navigate = useNavigate();
  const { topic_id } = useParams<{ topic_id: string }>();
  const [topic, setTopic] = useState<Topic | null>(initialData?.topic ?? null);
  const [loading, setLoading] = useState(!initialData);
  const [tab, setTab] = useState<"spoken" | "skeleton" | "bond" | "edit">("spoken");
  const [spokenText, setSpokenText] = useState(topic?.spoken_text ?? "");
  const [spokenTitle, setSpokenTitle] = useState(topic?.title ?? "");
  const [error, setError] = useState<string | null>(null);
  const spokenTextRef = useRef<HTMLTextAreaElement>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // 如果没有初始数据，加载数据
  useEffect(() => {
    if (initialData || !topic_id) return;
    api
      .getTopicWithReport(topic_id)
      .then((data) => {
        setTopic(data.topic);
        setSpokenText(data.topic.spoken_text ?? "");
        setSpokenTitle(data.topic.title);
        setLoading(false);
      })
      .catch((e) => {
        setError(String((e as Error).message));
        setLoading(false);
      });
  }, [initialData, topic_id]);

  // localStorage 自动保存
  const localStorageKey = `spoken_text_draft_${topic_id}`;
  useEffect(() => {
    const saved = localStorage.getItem(localStorageKey);
    if (saved) setSpokenText(saved);
  }, [localStorageKey]);

  // 清除待处理的防抖 timer
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const saveLocalStorage = useCallback((text: string) => {
    localStorage.setItem(localStorageKey, text);
  }, [localStorageKey]);

  const handleSpokenTextChange = (text: string) => {
    setSpokenText(text);
    saveLocalStorage(text);
  };

  const handleSpokenTitleChange = (title: string) => {
    setSpokenTitle(title);
    // debounce 更新 topic.title
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      if (topic && title.trim() !== topic.title) {
        api
          .patchTopic(topic_id!, { title: title.trim() })
          .then((updated) => {
            setTopic(updated);
            notifyChanged();
          })
          .catch((e) => setError(String((e as Error).message)));
      }
    }, 500);
  };

  const saveSpokenText = async () => {
    if (!topic_id) return;
    try {
      setError(null);
      const updated = await api.saveSpokenText(topic_id, spokenText);
      setTopic(updated);
      notifyChanged();
    } catch (e) {
      setError(String((e as Error).message));
    }
  };

  const goBack = () => {
    navigate("/working");
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "32px" }}>
        <p>加载中...</p>
      </div>
    );
  }

  if (!topic) {
    return (
      <div style={{ textAlign: "center", padding: "32px" }}>
        <p>没找到这条选题</p>
        <button className="btn" onClick={goBack}>
          返回
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="crumb">
        <button className="btn link" onClick={goBack}>
          ← 加工中
        </button>
      </div>
      <h1 className="page">{spokenTitle}</h1>
      {error && <div className="err">{error}</div>}

      {/* 进度条 */}
      <div className="stagebar">
        {STAGES.map((s) => {
          const completed = STAGES.indexOf(topic!.stage) > STAGES.indexOf(s);
          const isCurrent = topic!.stage === s;
          return (
            <span
              key={s}
              style={{
                opacity: isCurrent ? 1 : completed ? 0.6 : 0.4,
                fontWeight: isCurrent ? 600 : 400,
              }}
            >
              {completed ? "●" : isCurrent ? "◯" : "○"} {s}
            </span>
          );
        })}
      </div>

      {/* Tab 导航 */}
      <nav className="tabs" style={{ marginTop: 16, marginBottom: 16 }}>
        <button
          className={`tab ${tab === "spoken" ? "active" : ""}`}
          onClick={() => setTab("spoken")}
        >
          你说一遍 {topic!.spoken_text ? <small>已存</small> : null}
        </button>
        <button
          className={`tab ${tab === "skeleton" ? "active" : ""}`}
          onClick={() => setTab("skeleton")}
        >
          骨架 <small>已写</small>
        </button>
        <button
          className={`tab ${tab === "bond" ? "active" : ""}`}
          onClick={() => setTab("bond")}
        >
          付息稿 <small>已写</small>
        </button>
        <button
          className={`tab ${tab === "edit" ? "active" : ""}`}
          onClick={() => setTab("edit")}
        >
          剪辑进度
        </button>
      </nav>

      {/* Tab 内容 */}
      <div className="card">
        {tab === "spoken" && (
          <div>
            <h3 style={{ marginBottom: 16 }}>你说一遍</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {/* 左栏：拆解 */}
              <div
                style={{
                  padding: 12,
                  backgroundColor: "#f5f5f5",
                  borderRadius: 6,
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: "#666",
                }}
              >
                {initialData?.report ? (
                  <>
                    <b>拆解结构</b>
                    <div style={{ marginTop: 8 }}>
                      <p><b>论点：</b> {initialData.report.thesis.text}</p>
                      {initialData.report.segments.slice(0, 5).map((seg: any) => (
                        <div key={seg.index} style={{ marginTop: 8, paddingLeft: 8, borderLeft: "2px solid #ddd" }}>
                          <b>{seg.label}</b> ({seg.start.toFixed(0)}s - {seg.end.toFixed(0)}s)
                          <p style={{ margin: "4px 0 0" }}>{seg.summary}</p>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="muted">看着这里的拆解，直接说你的想法</p>
                )}
              </div>

              {/* 右栏：文本框 */}
              <div>
                <label style={{ display: "block", marginBottom: 8, fontSize: 13 }}>
                  标题
                  <input
                    type="text"
                    className="input"
                    value={spokenTitle}
                    onChange={(e) => handleSpokenTitleChange(e.target.value)}
                    style={{ marginTop: 4 }}
                  />
                </label>
                <label style={{ display: "block", marginBottom: 8, fontSize: 13 }}>
                  直接说
                  <textarea
                    ref={spokenTextRef}
                    className="input"
                    value={spokenText}
                    onChange={(e) => handleSpokenTextChange(e.target.value)}
                    placeholder="用电脑的语音输入法往这里说，说的都是你自己的经历和判断。边说边存，刷新不丢。"
                    style={{ marginTop: 4, minHeight: 200, fontFamily: "monospace", fontSize: 12 }}
                  />
                </label>
                <button className="btn blue" onClick={saveSpokenText}>
                  保存
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === "skeleton" && (
          <div>
            <h3>骨架</h3>
            <p className="muted">一勾式骨架拆解。Phase 3 占位。</p>
          </div>
        )}

        {tab === "bond" && (
          <div>
            <h3>付息稿</h3>
            <p className="muted">「本金」段 + 「发债」段 + 「第 1 笔息」… Phase 3 占位。</p>
          </div>
        )}

        {tab === "edit" && (
          <div>
            <h3>剪辑进度</h3>
            <p className="muted">视频项目关联和进度跟踪。Phase 3 占位。</p>
          </div>
        )}
      </div>
    </div>
  );
}
