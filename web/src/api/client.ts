/**
 * 极简 API client（原生 fetch，不引第三方库）。
 *
 * - base URL 读 import.meta.env.VITE_ZHESI_API_BASE，默认本地后端 http://127.0.0.1:8010
 * - token 存 localStorage["zhesi_token"]（顶栏输入框设置，开发态）
 * - 问/辩/谱三个引擎端点接线期并行开发：网络错误、超时、5xx（含接线期的 404/501，
 *   wired 端点）统一抛 ApiUnavailableError，界面据此渲染「该能力接线中」降级态。
 */

export const API_BASE: string = (() => {
  const raw = import.meta.env?.VITE_ZHESI_API_BASE;
  return typeof raw === "string" && raw.trim() ? raw.trim().replace(/\/+$/, "") : "http://127.0.0.1:8010";
})();

export const TOKEN_KEY = "zhesi_token";
const TIMEOUT_MS = 30_000;

// ---- token 存取（非浏览器环境退化为内存 shim，测试可用） ----

const memoryStore = new Map<string, string>();
const shim: Pick<Storage, "getItem" | "setItem" | "removeItem"> = {
  getItem: (k) => memoryStore.get(k) ?? null,
  setItem: (k, v) => void memoryStore.set(k, v),
  removeItem: (k) => void memoryStore.delete(k),
};
function store(): Pick<Storage, "getItem" | "setItem" | "removeItem"> {
  try {
    if (typeof localStorage !== "undefined") return localStorage;
  } catch {
    /* 隐私模式等场景落到内存 shim */
  }
  return shim;
}
export function getToken(): string {
  return store().getItem(TOKEN_KEY) ?? "";
}
export function setToken(token: string): void {
  if (token) store().setItem(TOKEN_KEY, token);
  else store().removeItem(TOKEN_KEY);
}

// ---- 错误类型 ----

/** 「该能力接线中」：网络失败/超时/5xx，或 wired 端点 404/501（尚未接线）。 */
export class ApiUnavailableError extends Error {
  constructor(message = "capability not wired yet") {
    super(message);
    this.name = "ApiUnavailableError";
  }
}

/** 业务错误（4xx 等），message 携带后端 detail。 */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---- 请求 ----

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  query?: Record<string, string>;
  /** 问辩谱接线期端点：404/501 也视为「未接线」而非业务错误 */
  wired?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  for (const [k, v] of Object.entries(opts.query ?? {})) url.searchParams.set(k, v);

  const token = getToken();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const hasBody = opts.body !== undefined;
  if (hasBody) headers["Content-Type"] = "application/json";

  let resp: Response;
  try {
    resp = await fetch(url, {
      method: opts.method ?? (hasBody ? "POST" : "GET"),
      headers,
      body: hasBody ? JSON.stringify(opts.body) : undefined,
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    // 网络拒绝 / DNS / CORS / 超时（AbortError/TimeoutError）→ 接线中降级
    throw new ApiUnavailableError();
  }

  if (!resp.ok) {
    const unwired = resp.status >= 500 || resp.status === 501 || (opts.wired && resp.status === 404);
    if (unwired) throw new ApiUnavailableError();
    let detail: unknown = "";
    try {
      detail = (await resp.json())?.detail ?? "";
    } catch {
      /* 无 JSON body */
    }
    const message = typeof detail === "string" && detail ? detail : `HTTP ${resp.status}`;
    throw new ApiError(resp.status, message);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ---- 契约类型 ----

export type Stability = "stable" | "wavering" | "shelved";

export interface StanceCard {
  id: string;
  question: string;
  question_ref: string | null;
  position: string;
  reasons: string | null;
  strongest_objection: string | null;
  my_response: string | null;
  status: "active" | "sealed";
  stability: Stability;
  created_at: string;
  updated_at: string;
  sealed_at: string | null;
}

export interface ConceptCard {
  title: string;
  url: string;
  snippet: string;
}

export interface SurveyOption {
  label: string;
  label_zh?: string;
  pct: number;
}

export interface StanceQuestion {
  question: string;
  survey_round: string | number;
  options: SurveyOption[];
}

export interface AskResult {
  concept_cards: ConceptCard[];
  stance_questions: StanceQuestion[];
  engine?: string;
}

export interface ObjectionResult {
  objection: string;
  citations: unknown[];
  engine?: string;
}

export interface Neighbor {
  name_en: string;
  name_zh?: string;
  distance: number;
}

export interface Projection {
  id?: string;
  created_at?: string;
  axes: Record<string, number>;
  neighbors: Neighbor[];
  based_on_cards: string[];
  skipped: string[];
}

/** 张力簿条目（contract.py 口径：id/card_ids/description/source；防御式可选）。 */
export interface TensionItem {
  id: string;
  card_ids?: string[];
  description?: string;
  source?: string;
}

export interface AnnalEntry {
  id: string;
  card_id: string;
  kind: string;
  snapshot: StanceCard;
  at: string;
}

/** 引用条目防御式取文案：string 直出；对象按常见字段拼。 */
export function citationText(c: unknown): string {
  if (typeof c === "string") return c;
  if (c && typeof c === "object") {
    const o = c as Record<string, unknown>;
    const text = [o.title, o.text, o.quote, o.label].find((v) => typeof v === "string" && v);
    if (text) return String(text);
    const url = [o.url, o.link].find((v) => typeof v === "string" && v);
    if (url) return String(url);
    try {
      return JSON.stringify(c);
    } catch {
      return String(c);
    }
  }
  return String(c ?? "");
}

// ---- API 面（对齐 ../server 契约） ----

export const api = {
  // 问辩谱（接线期，wired：404/5xx → 接线中降级）
  ask: (text: string) =>
    request<AskResult>("/api/v1/ask", { method: "POST", body: { text }, wired: true }),
  strongestObjection: (card_id: string) =>
    request<ObjectionResult>("/api/v1/debate/strongest-objection", { method: "POST", body: { card_id }, wired: true }),
  project: () =>
    request<Projection>("/api/v1/synthesis/project", { method: "POST", body: {}, wired: true }),
  listProjections: () =>
    request<{ results: Projection[] }>("/api/v1/synthesis/projections", { wired: true }),
  listTensions: () =>
    request<{ results: TensionItem[] }>("/api/v1/synthesis/tensions", { wired: true }),

  // 个人层（已上线）
  listCards: (status: "active" | "sealed" = "active") =>
    request<{ results: StanceCard[] }>("/api/v1/cards", { query: { status } }),
  getCard: (id: string) => request<StanceCard>(`/api/v1/cards/${encodeURIComponent(id)}`),
  createCard: (b: { question: string; position: string; reasons?: string; question_ref?: string }) =>
    request<StanceCard>("/api/v1/cards", { method: "POST", body: b }),
  recordObjection: (id: string, objection: string) =>
    request<StanceCard>(`/api/v1/cards/${encodeURIComponent(id)}/objection`, { method: "POST", body: { objection } }),
  respond: (id: string, b: { my_response: string; stability?: Stability }) =>
    request<StanceCard>(`/api/v1/cards/${encodeURIComponent(id)}/response`, { method: "POST", body: b }),
  changePosition: (id: string, b: { position: string; reasons?: string }) =>
    request<StanceCard>(`/api/v1/cards/${encodeURIComponent(id)}/change`, { method: "POST", body: b }),
  annals: () => request<{ results: AnnalEntry[] }>("/api/v1/cards/annals"),
};
