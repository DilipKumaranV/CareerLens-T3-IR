// Shapes of the CareerLens API responses (see docs/API.md). Only the fields the UI relies on are typed.
export interface Job {
  id: number; title: string; company: string; location: string | null; country: string; workplace: string; schedule: string; role_family: string;
  skills: string[]; posted: string; salary_year: number | null; salary_hour: number | null; salary_rate: string | null; via: string | null;
  listings: number; no_degree: boolean; health_insurance: boolean;
}
export interface FitSkill { skill: string; key: string; matched_by?: string }
export interface Fit {
  career_fit: number | null; skill_match?: number | null; role_similarity?: number | null; covered: FitSkill[]; missing: FitSkill[];
  skills_covered?: number; skills_required?: number; components: Record<string, { score: number; weight: number; share: number }>;
  not_available?: string[]; reason?: string;
}
export interface Result {
  rank: number | null; job: Job; ir_relevance: number | null; cosine: number | null; jaccard: number | null; flat_cosine: number | null;
  zone_scores: Record<string, number>; matched_terms: Record<string, string[]>; reasons: string[]; career_fit?: Fit | null;
  diversity: { penalty: number; max_similarity: number };
  debug?: { term_contributions: { zone: string; surface: string; query_weight: number; doc_tf: number; df: number; idf: number; doc_tfidf: number; doc_weight: number; zone_share: number; contribution: number }[] };
}
export interface Personalization { available: boolean; message: string | null }
export interface Notice { kind: string; text: string; terms?: string[]; suggestions?: Record<string, string[]> }
export interface SearchResponse {
  query: string; results: Result[]; notices: Notice[]; personalization: Personalization;
  analysis: { raw: string; tokens: string[]; removed: { token: string; reason: string }[]; stems: { token: string; stem: string }[]; biwords: string[];
    query_skills: string[]; routing: { surface: string; df: Record<string, number>; routed_to: string[] }[]; active_zones: string[]; unknown: string[];
    suggestions: Record<string, string[]>; terms: { zone: string; surface: string; tf: number; df: number; idf: number }[] };
  stats: { N: number; candidates: number; documents_never_scored: number; postings_traversed: number; filtered_to: number | null; time_ms: number };
}
export interface Meta {
  dataset: any; listings: number; zones: string[]; zone_weights: Record<string, number>; default_config: any; filter_fields: Record<string, string>;
  filter_options: Record<string, [string, number][]>; vocabulary: Record<string, number>; skill_vocabulary: number; fit_weights: Record<string, number>;
  career_thresholds: Record<string, number>; no_profile_message: string; index_build_ms: number;
}
export type Filters = Record<string, string[]>;
