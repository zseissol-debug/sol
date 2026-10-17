// 与 backend/studio/models.py 一一对应

export type Source = "park_public" | "local";

export interface Evidence { start: number; end: number; quote: string }
export interface Conclusion { text: string; evidence: Evidence[] }
export interface Segment {
  index: number; label: string; drift: boolean; start: number; end: number;
  summary: string; reason: string; text: string;
}
export interface Opening { seconds: number; analysis: string; transcript: string }

export interface Report {
  id: string; title: string; author: string | null; source_url: string | null;
  generated_at: string; duration_seconds: number;
  facts: Record<string, number | null>;
  thesis: Conclusion; opening: Opening | null; segments: Segment[];
  drift_seconds: number; drift_share: number;
  why_boom: Conclusion[]; why_scatter: Conclusion[];
  hypothesis_note: string; source: Source; archived: boolean; topic_id: string | null;
}
export interface ReportBrief {
  id: string; title: string; author: string | null; generated_at: string;
  multiple: number | null; source: Source; archived: boolean;
}

export interface NewsItem {
  id: string; title: string; url: string | null; source: string | null;
  summary: string; topic_id: string | null;
}
export interface NewsGroup { name: string | null; items: NewsItem[] }
export interface NewsSection {
  kind: "brief" | "deep" | "radar" | "other"; title: string; groups: NewsGroup[]; text: string | null;
}
export interface NewsIssue {
  id: string; title: string; published_at: string | null; source: Source;
  sections: NewsSection[]; brief_count: number;
}
export interface NewsIssueBrief { id: string; title: string; source: Source; brief_count: number }

export type Stage = "选题" | "提纲" | "录制" | "剪辑" | "待发" | "已发出";
export type QAConclusion = "go" | "patch" | "thin";
export interface Topic {
  id: string; title: string; excerpt: string; stage: Stage;
  status: "pool" | "scheduled" | "trash";
  focal: boolean; qa_conclusion: QAConclusion;
  spoken_text: string | null; video_project_path: string | null;
  origin: { kind: "news" | "report" | "manual"; ref: string | null; url: string | null };
  created_at: string; updated_at: string;
}

export interface AccountWork {
  id: string; title: string; url: string;
  likes: number; collects: number; shares: number; comments: number;
  publish_at: string; likes_multiple: number | null; work_type: string | null;
}
export interface Account {
  id: string; name: string; platform: "douyin" | "xiaohongshu" | "x" | "bilibili";
  sec_uid: string | null; url: string; role: "teacher" | "peer";
  followers: number | null; likes_median: number | null;
  works_count: number; boom_count: number; works: AccountWork[];
  last_synced: string; created_at: string; updated_at: string;
}
export interface AccountBrief {
  id: string; name: string; platform: "douyin" | "xiaohongshu" | "x" | "bilibili";
  role: "teacher" | "peer"; followers: number | null;
  works_count: number; boom_count: number; last_synced: string;
}

export interface Job {
  id: string; kind: "teardown" | "newsletter"; input: string;
  state: "queued" | "running" | "done" | "failed";
  stage: string; error: string | null; result: Record<string, unknown>;
  log: string[]; created_at: string; updated_at: string;
}

export interface EnvCheck { key: string; label: string; ok: boolean; fix: string }
export interface EngineStatus {
  installed: boolean; configured: boolean; has_venv: boolean;
  doctor_ok: boolean | null; doctor_output: string; fix: string;
}
export interface Counts { reports: number; candidates: number; reports_archived: number; topics: number; issues: number }
