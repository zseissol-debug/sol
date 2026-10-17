// 还没做的页面：先立好路由和页面名，把原版的功能点列在上面，后面按期来填。
// 来源：docs/01-信息架构与主流程.md

export interface ShellSpec {
  crumb: string;
  title: string;
  lead: string;
  phase: string;
  planned: string[];
  note?: string;
}

export const SHELLS: Record<string, ShellSpec> = {
  today: {
    crumb: "今天", title: "今天", lead: "现在做哪一件。", phase: "第 3 期",
    planned: ["今日唯一要事（本人决定拍哪条）", "KPI 排序", "AI 帮你挑选题", "周历 / 月历", "连续出摊天数", "周复盘（数据回流到写稿）"],
    note: "原版没有这一页的截图，具体布局和规则需要你来定。",
  },
  pack: {
    crumb: "03 · 打包", title: "定个标题，剩下的自动备好", phase: "第 6 期",
    lead: "你只定标题。封面、X 图文、插图、公众号排版会一步接一步做完；全好了就去发布。",
    planned: ["标题：AI 出 6–10 条候选，超长自动标出", "描述和话题：5 个平台文案一次填写", "自动准备 4 项：封面、X 图文文章、插图、公众号排版（可查看 / 修改）", "自动档：失败停下等重试，重启自动续跑"],
  },
  publish: {
    crumb: "04 · 发布", title: "每条内容发在哪", phase: "第 6 期",
    lead: "一行一条内容、一列一个平台，点 ↗ 打开那个平台上的这一条。",
    planned: ["内容 × 7 平台矩阵（X、抖音、小红书、视频号、B 站、YouTube、公众号）", "补发工作台：挑格子 → 再看一遍 → 开始发", "下载表格", "出错闭环：为什么 → 你做什么 → 自己再发"],
    note: "补发工作台只有第 1 步（挑格子）有截图。任何会真实对外发布的动作，做的时候都保留人工确认。",
  },
  sent: {
    crumb: "05 · 已发出", title: "这一周怎么样", phase: "第 6 期",
    lead: "触达是第一个数。每个数字旁边的「?」说明它怎么算的。",
    planned: ["概览：今天 / 本周触达、各平台卡片、往日日结、每条内容在每个平台的累计触达", "总览：5 项 KPI、时长 × 播放散点图、作品明细表（完播、跳出、封面点击、倍数）", "看报告 / 拆解（自己的视频会多出「前 N 秒」分析）"],
  },
  x: {
    crumb: "单独一条线", title: "单独一条线", lead: "X：短帖打勾、长文。", phase: "第 6 期",
    planned: ["短帖打勾", "长文", "每晚排短贴"],
    note: "原版没有这一页的截图。",
  },
  traffic: {
    crumb: "流量视频", title: "流量视频", lead: "看到就想转的，先存下来。", phase: "第 5 期",
    planned: ["粘贴视频链接（抖音、X、小红书），回车存下来", "卡片：我为什么想转它（一句话）、换成我的归哪个合集", "开始复刻", "抖音每天最多存 5 条（用你的登录），X、小红书不限"],
  },
  settings: {
    crumb: "设置", title: "设置", lead: "只保存在本机。", phase: "第 6 期",
    planned: ["通用", "视频动效：快出 / 标准 / 精品，密度、表现方式、证据素材", "Skills", "助手读什么", "版本"],
  },
};

export function ShellPage({ spec }: { spec: ShellSpec }) {
  return (
    <div className="shell">
      <div className="crumb warm">{spec.crumb}</div>
      <h1 className="page">{spec.title}</h1>
      <p className="lead">{spec.lead}</p>
      <div className="card pad">
        <div className="row"><b>这一页还没做</b><span className="tag">{spec.phase}</span></div>
        <p className="muted" style={{ margin: "6px 0 0" }}>原版在这一页有这些功能：</p>
        <ul>{spec.planned.map((p) => <li key={p}>{p}</li>)}</ul>
        {spec.note && <p className="note" style={{ marginTop: 14 }}>{spec.note}</p>}
      </div>
    </div>
  );
}
