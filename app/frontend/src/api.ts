import type {
  Account, AccountBrief, Counts, EngineStatus, EnvCheck, Job, NewsIssue, NewsIssueBrief, Report, ReportBrief, Topic,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* 非 JSON 响应 */ }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T,>(path: string, body: unknown) =>
  req<T>(path, { method: "PATCH", body: JSON.stringify(body) });

export const api = {
  counts: () => req<Counts>("/api/counts"),

  issues: () => req<NewsIssueBrief[]>("/api/newsletter/issues"),
  issue: (id: string) => req<NewsIssue>(`/api/newsletter/issues/${id}`),
  syncNewsletter: () => post<{ fetched: number; saved: number }>("/api/newsletter/sync"),
  engineStatus: () => req<EngineStatus>("/api/newsletter/engine"),
  generateNewsletter: () => post<Job>("/api/newsletter/generate"),
  topicFromNews: (issueId: string, itemId: string) =>
    post<Topic>(`/api/newsletter/issues/${issueId}/items/${itemId}/topic`),

  reports: (archived = false) => req<ReportBrief[]>(`/api/reports?archived=${archived}`),
  report: (id: string) => req<Report>(`/api/reports/${id}`),
  archiveReport: (id: string, archived: boolean) => patch<Report>(`/api/reports/${id}`, { archived }),
  syncReports: () => post<{ fetched: number; saved: number }>("/api/reports/sync-public"),
  topicFromReport: (id: string) => post<Topic>(`/api/reports/${id}/topic`),

  teardownEnv: () => req<EnvCheck[]>("/api/teardown/env"),
  startTeardown: (url: string, workId?: string) => post<Job>("/api/teardown", { url, work_id: workId }),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
  jobs: () => req<Job[]>("/api/jobs"),

  topics: () => req<Topic[]>("/api/topics"),
  createTopic: (title: string) =>
    post<Topic>("/api/topics", { title, origin: { kind: "manual" } }),
  patchTopic: (id: string, body: Partial<Pick<Topic, "status" | "stage" | "title" | "qa_conclusion" | "spoken_text" | "video_project_path">>) =>
    patch<Topic>(`/api/topics/${id}`, body),
  setFocalTopic: (id: string) => post<Topic>(`/api/topics/${id}/set-focal`),
  clearFocalTopic: () => post<{ cleared: boolean }>("/api/topics/clear-focal"),
  getTopicWithReport: (id: string) => req<{ topic: Topic; report: Report | null }>(`/api/topics/${id}/with-report`),
  saveSpokenText: (id: string, spokenText: string) =>
    post<Topic>(`/api/topics/${id}/spoken-text`, { spoken_text: spokenText }),

  accounts: () => req<AccountBrief[]>("/api/accounts"),
  getAccount: (id: string) => req<Account>(`/api/accounts/${id}`),
  createAccount: (name: string, platform: string, url: string, role: "teacher" | "peer" = "peer") =>
    post<Account>("/api/accounts", { name, platform, url, role }),
  patchAccount: (id: string, role: "teacher" | "peer") =>
    patch<Account>(`/api/accounts/${id}`, { role }),
  deleteAccount: (id: string) => post<{ deleted: boolean }>(`/api/accounts/${id}`, undefined),
  syncAccount: (id: string) => post<Account>(`/api/accounts/${id}/sync`),
  syncAccountReal: (id: string) => post<Account>(`/api/accounts/${id}/sync-real`),
};
