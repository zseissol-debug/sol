import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { notifyChanged } from "../../components/Layout";
import type { AccountBrief, AccountWork } from "../../types";

const PLATFORM_LABEL: Record<string, string> = {
  douyin: "抖音",
  xiaohongshu: "小红书",
  x: "X",
  bilibili: "B站",
};

// 简单的折线图组件（纯 SVG）
function TrendChart({ works }: { works: AccountWork[] }) {
  if (!works || works.length === 0) return null;

  const likes = works.map(w => w.likes);
  const maxLikes = Math.max(...likes);
  const minLikes = Math.min(...likes);
  const range = maxLikes - minLikes || 1;

  const width = 120;
  const height = 40;
  const padding = 4;

  // 计算爆款倍数
  const sorted = [...likes].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  const threshold = median * 2.5;

  // 生成路径点
  const points = likes.map((l, i) => {
    const x = padding + (i / (likes.length - 1 || 1)) * (width - 2 * padding);
    const y = height - padding - ((l - minLikes) / range) * (height - 2 * padding);
    return [x, y];
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ');

  return (
    <svg width={width} height={height} style={{ border: "1px solid #e0e0e0", borderRadius: 4 }}>
      {/* 面积 */}
      <path d={`${pathD} L ${points[points.length-1][0]} ${height - padding} L ${points[0][0]} ${height - padding} Z`}
        fill="#e3f2fd" opacity="0.6" />

      {/* 曲线 */}
      <path d={pathD} stroke="#2196F3" strokeWidth="1.5" fill="none" />

      {/* 爆款点（金色） */}
      {likes.map((l, i) => {
        if (l >= threshold) {
          const x = padding + (i / (likes.length - 1 || 1)) * (width - 2 * padding);
          const y = height - padding - ((l - minLikes) / range) * (height - 2 * padding);
          return <circle key={`boom_${i}`} cx={x} cy={y} r="2" fill="#FFA500" />;
        }
        return null;
      })}
    </svg>
  );
}

export default function Peers() {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<AccountBrief[] | null>(null);
  const [accountDetails, setAccountDetails] = useState<Record<string, AccountWork[]>>({});
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState({ name: "", platform: "douyin" as const, url: "", role: "peer" as const });
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  // 爆款列表筛选
  const [boomThreshold, setBoomThreshold] = useState(2.5);
  const [timeRange, setTimeRange] = useState("30"); // 天数
  const [sortBy, setSortBy] = useState<"multiple" | "likes" | "date">("multiple");

  const load = useCallback(async () => {
    try {
      setError(null);
      const accts = await api.accounts();
      setAccounts(accts);

      // 加载每个账号的详细信息（作品列表）
      const details: Record<string, AccountWork[]> = {};
      for (const acct of accts) {
        try {
          const fullAcct = await api.getAccount(acct.id);
          if (fullAcct?.works) {
            details[acct.id] = fullAcct.works;
          }
        } catch {
          // 暂时忽略单个账号的加载错误
        }
      }
      setAccountDetails(details);
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

  async function handleAddAccount() {
    const name = addForm.name.trim();
    const url = addForm.url.trim();
    if (!name || !url) {
      setError("账号名和链接不能为空");
      return;
    }

    setAdding(true);
    try {
      await run(() =>
        api.createAccount(name, addForm.platform, url, addForm.role)
      );
      setShowAdd(false);
      setAddForm({ name: "", platform: "douyin", url: "", role: "peer" });
    } finally {
      setAdding(false);
    }
  }

  async function handleSync(id: string) {
    await run(() => api.syncAccount(id));
  }

  async function handleToggleRole(id: string, currentRole: "teacher" | "peer") {
    const newRole = currentRole === "teacher" ? "peer" : "teacher";
    await run(() => api.patchAccount(id, newRole));
  }

  async function handleDelete(id: string) {
    if (!confirm("确定删除这个账号吗？")) return;
    await run(() => api.deleteAccount(id));
  }

  // 生成爆款列表（合并所有账号的爆款作品）
  const allWorks: (AccountWork & { accountName: string; accountId: string })[] = [];
  accounts?.forEach(acct => {
    const works = accountDetails[acct.id] || [];
    const median = (acct as any).likes_median || 10000;
    works.forEach(work => {
      const multiple = work.likes ? work.likes / median : 0;
      if (multiple >= boomThreshold) {
        allWorks.push({ ...work, accountName: acct.name, accountId: acct.id });
      }
    });
  });

  // 排序
  allWorks.sort((a, b) => {
    if (sortBy === "multiple") {
      return (b.likes_multiple || 0) - (a.likes_multiple || 0);
    } else if (sortBy === "likes") {
      return b.likes - a.likes;
    } else {
      return new Date(b.publish_at).getTime() - new Date(a.publish_at).getTime();
    }
  });

  return (
    <div>
      {error && <div className="err" style={{ marginBottom: 12 }}>{error}</div>}

      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0 }}>账号 {accounts?.length ?? 0}</h3>
          <p className="muted small" style={{ margin: 0, marginTop: 4 }}>每天 9:30 自动同步 · 每个号只看最新一页</p>
        </div>
        <button className="btn blue" onClick={() => setShowAdd(true)}>+ 加一个老师或对标</button>
      </div>

      {/* 账号卡片网格（4 列）*/}
      {accounts && accounts.length === 0 ? (
        <div className="card empty">
          <b>还没有关注任何账号</b>
          点右上角「+ 加一个老师或对标」开始添加。
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          {accounts?.map((a) => (
            <div key={a.id} className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 12 }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 8 }}>
                  <button
                    className={"tag " + (a.role === "teacher" ? "blue" : "gray")}
                    onClick={() => handleToggleRole(a.id, a.role)}
                    style={{ cursor: "pointer" }}
                  >
                    {a.role === "teacher" ? "老师" : "对标"}
                  </button>
                  <button
                    className="btn sm"
                    onClick={() => handleDelete(a.id)}
                    style={{ padding: "2px 6px", fontSize: 12 }}
                  >
                    ✕
                  </button>
                </div>
                <h4 style={{ margin: "0 0 4px 0", fontSize: 14 }}>{a.name}</h4>
                <p className="muted small" style={{ margin: "0 0 8px 0" }}>
                  {PLATFORM_LABEL[a.platform]} · {a.followers ? `${(a.followers / 10000).toFixed(1)}万` : "—"} 粉
                </p>

                {/* 走势图 */}
                <div style={{ marginBottom: 8 }}>
                  <TrendChart works={accountDetails[a.id] || []} />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8, fontSize: 12 }}>
                  <div>
                    <div className="muted small">中位数</div>
                    <div style={{ fontWeight: 600 }}>{a.followers ? (a as any).likes_median?.toLocaleString() || "—" : "—"}</div>
                  </div>
                  <div>
                    <div className="muted small">作品数</div>
                    <div style={{ fontWeight: 600 }}>{a.works_count}</div>
                  </div>
                  <div>
                    <div className="muted small">爆款数</div>
                    <div style={{ fontWeight: 600, color: "#FFA500" }}>{a.boom_count}</div>
                  </div>
                </div>
              </div>

              <div>
                <p className="muted small" style={{ margin: "0 0 8px 0" }}>
                  {a.last_synced ? new Date(a.last_synced).toLocaleString('zh-CN').split(' ')[0] : "未同步"}
                </p>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn sm" onClick={() => handleSync(a.id)} style={{ flex: 1, fontSize: 12 }}>
                    同步
                  </button>
                  <button className="btn sm" onClick={() => window.open(a.platform === "douyin" ? `https://www.douyin.com/user/${a.id}` : a.id, "_blank")} style={{ flex: 1, fontSize: 12 }}>
                    主页 ↗
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 爆款列表 */}
      {accounts && accounts.length > 0 && (
        <div>
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ margin: 0 }}>爆款样本 {allWorks.length} 条</h3>

            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              <span className="muted">门槛</span>
              <input
                type="range"
                min="1" max="5" step="0.5"
                value={boomThreshold}
                onChange={(e) => setBoomThreshold(parseFloat(e.target.value))}
                style={{ width: 100 }}
              />
              <span style={{ minWidth: 40 }}>{boomThreshold}×</span>
            </label>

            <select
              className="input"
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              style={{ fontSize: 13, padding: "4px 8px" }}
            >
              <option value="7">最近 7 天</option>
              <option value="30">30 天</option>
              <option value="90">90 天</option>
              <option value="999">全部</option>
            </select>

            <select
              className="input"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              style={{ fontSize: 13, padding: "4px 8px" }}
            >
              <option value="multiple">按倍数</option>
              <option value="likes">按点赞</option>
              <option value="date">按日期</option>
            </select>
          </div>

          {allWorks.length === 0 ? (
            <div className="card empty">
              <p className="muted small">暂无爆款作品</p>
            </div>
          ) : (
            <div className="card">
              {allWorks.map((work, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex", gap: 12, paddingBottom: 12, marginBottom: 12,
                    borderBottom: i < allWorks.length - 1 ? "1px solid #e0e0e0" : "none"
                  }}
                >
                  {/* 倍数 */}
                  <div style={{ minWidth: 50, textAlign: "center" }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "#FFA500" }}>
                      {(work.likes_multiple ?? 0).toFixed(1)}×
                    </div>
                    <div className="muted small">倍数</div>
                  </div>

                  {/* 内容 */}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{work.title}</div>
                    <div className="muted small" style={{ marginBottom: 4 }}>
                      {work.accountName} · {new Date(work.publish_at).toLocaleDateString('zh-CN')}
                    </div>
                    <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#666" }}>
                      <span>赞 {work.likes.toLocaleString()}</span>
                      <span>收藏 {work.collects.toLocaleString()}</span>
                      <span>转发 {work.shares.toLocaleString()}</span>
                      <span>评论 {work.comments.toLocaleString()}</span>
                    </div>
                  </div>

                  {/* 互动结构 */}
                  <div style={{ minWidth: 120 }}>
                    <div className="muted small" style={{ marginBottom: 4 }}>{work.work_type}</div>
                    <div style={{ display: "flex", height: 8, borderRadius: 2, overflow: "hidden", gap: 1 }}>
                      <div style={{
                        flex: work.collects,
                        backgroundColor: "#4CAF50"
                      }} />
                      <div style={{
                        flex: work.shares,
                        backgroundColor: "#2196F3"
                      }} />
                      <div style={{
                        flex: work.comments,
                        backgroundColor: "#9C27B0"
                      }} />
                    </div>
                  </div>

                  {/* 按钮组 */}
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="btn sm blue" onClick={() => navigate(`/inbox/reports?work=${work.accountId}:${work.id}`)}>看报告</button>
                    {work.report_id ? (
                      <button className="btn sm" style={{ opacity: 0.6 }} disabled>✓ 已拆解</button>
                    ) : (
                      <a className="btn sm" href={work.url} target="_blank" rel="noreferrer">看视频</a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 添加弹窗 */}
      {showAdd && (
        <div style={{
          position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000
        }}>
          <div className="card" style={{ maxWidth: 400, width: "90%", padding: 20 }}>
            <h3 style={{ margin: "0 0 12px 0" }}>加一个老师或对标</h3>
            <p className="muted small" style={{ margin: "0 0 16px 0" }}>
              粘贴对方的主页链接。抖音账号加入后会立即同步近期作品、算出他自己的爆款基准。
            </p>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span className="muted small" style={{ display: "block", marginBottom: 4 }}>账号名</span>
              <input
                type="text"
                className="input"
                value={addForm.name}
                onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                placeholder="如：小胡也是小狐"
              />
            </label>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span className="muted small" style={{ display: "block", marginBottom: 4 }}>平台</span>
              <select
                className="input"
                value={addForm.platform}
                onChange={(e) => setAddForm({ ...addForm, platform: e.target.value as any })}
              >
                <option value="douyin">抖音</option>
                <option value="xiaohongshu">小红书</option>
                <option value="x">X</option>
                <option value="bilibili">B站</option>
              </select>
            </label>

            <label style={{ display: "block", marginBottom: 12 }}>
              <span className="muted small" style={{ display: "block", marginBottom: 4 }}>主页链接</span>
              <input
                type="text"
                className="input"
                value={addForm.url}
                onChange={(e) => setAddForm({ ...addForm, url: e.target.value })}
                placeholder="例如 https://www.douyin.com/user/MS4wLjAB…"
              />
            </label>

            <p className="muted small" style={{ margin: 0, marginBottom: 16 }}>
              角色默认为「对标」，添加后可以在卡片上切换。
            </p>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setShowAdd(false)}>取消</button>
              <button className="btn blue" onClick={handleAddAccount} disabled={adding}>
                {adding ? "添加中…" : "加入"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
