// Thin client for the FastAPI backend. All retrieval, ranking and matching happens server-side.
import type { Filters, Meta, SearchResponse } from "./types";

export class ApiError extends Error {
  status: number; code?: string;
  constructor(message: string, status: number, code?: string) { super(message); this.status = status; this.code = code; }
}

/* Fields each page relies on. A response without them (different backend version, another program on port 8000)
   becomes a readable error instead of a crash. */
export const REQUIRED: Record<string, string[]> = {
  meta: ["dataset", "listings", "zones", "zone_weights", "filter_options", "no_profile_message", "career_thresholds"],
  search: ["results", "notices", "personalization", "analysis.terms", "analysis.routing", "stats.N", "stats.candidates"],
  job: ["job", "similar", "personalization"],
  transition: ["profile_match", "have", "to_develop", "preparation_plan", "recommended_jobs", "target", "requirements", "notes"],
  resume: ["file", "steps", "profile", "warnings"],
  evaluation: ["systems", "queries", "ablations", "significance", "by_type", "explanations", "splits", "setup"],
  trace: ["analysis", "index", "query_vectors", "postings", "candidates", "ranking", "comparison"],
  analytics: ["totals", "role_family", "country", "skill", "company"],
};

export function missingFields(obj: any, paths: string[]): string[] {
  return paths.filter((p) => p.split(".").reduce((o: any, k) => (o === null || o === undefined ? undefined : o[k]), obj) === undefined);
}
function need<T>(label: string, key: keyof typeof REQUIRED, obj: T): T {
  const m = missingFields(obj, REQUIRED[key]);
  if (m.length) throw new ApiError(`Unexpected response from ${label}: missing ${m.join(", ")}. Check that the backend on port 8000 is the CareerLens backend of this project.`, 502);
  return obj;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Can't reach the CareerLens API. Start the backend (python -m uvicorn app.main:app --port 8000 in the backend folder) and try again.", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`, code: string | undefined;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      code = body?.code;
    } catch { if (res.status >= 500) detail = "The CareerLens API is not responding. Is the backend running on port 8000?"; }
    throw new ApiError(detail, res.status, code);
  }
  return res.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export type ApiProfile = { current_role?: string; department?: string; experience_years?: number | null; skills: string[]; target_role?: string; target_company?: string };

export const api = {
  meta: () => request<Meta>("/api/meta").then((r) => need("/api/meta", "meta", r)),
  search: (b: { query: string; k?: number; filters?: Filters; sort?: string; debug?: boolean; profile?: ApiProfile | null; config?: any }) =>
    request<SearchResponse>("/api/search", json(b)).then((r) => need("/api/search", "search", r)),
  job: (id: number, query = "", profile: ApiProfile | null = null) =>
    request<any>(`/api/jobs/${id}/explain`, json({ query, profile })).then((r) => need("/api/jobs/{id}/explain", "job", r)),
  companies: (q: string) => request<{ companies: { company: string; listings: number }[] }>(`/api/companies?q=${encodeURIComponent(q)}`),
  skills: (q: string) => request<{ skills: { name: string; key: string; type: string | null }[] }>(`/api/skills/suggest?q=${encodeURIComponent(q)}`),
  demos: () => request<{ demos: { key: string; title: string; blurb: string; available: boolean }[]; label: string }>("/api/resume/demos"),
  analyzeResume: (file: File) => { const f = new FormData(); f.append("file", file); return request<any>("/api/resume/analyze", { method: "POST", body: f }).then((r) => need("/api/resume/analyze", "resume", r)); },
  analyzeDemo: (key: string) => request<any>(`/api/resume/demo/${key}`, { method: "POST" }).then((r) => need("/api/resume/demo", "resume", r)),
  normalizeProfile: (p: ApiProfile) => request<any>("/api/profile", json(p)),
  transition: (b: { profile: ApiProfile; target_role: string; target_company?: string | null; k?: number }) =>
    request<any>("/api/career-transition", json(b)).then((r) => need("/api/career-transition", "transition", r)),
  evaluation: () => request<any>("/api/evaluation").then((r) => need("/api/evaluation", "evaluation", r)),
  runEvaluation: () => request<any>("/api/evaluation/run", { method: "POST" }).then((r) => need("/api/evaluation/run", "evaluation", r)),
  trace: (b: { query: string; k?: number; filters?: Filters; config?: any }) => request<any>("/api/research/trace", json(b)).then((r) => need("/api/research/trace", "trace", r)),
  analytics: () => request<any>("/api/analytics").then((r) => need("/api/analytics", "analytics", r)),
};
