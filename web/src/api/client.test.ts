/** client.ts 冒烟：URL 拼装、token 头、降级（网络挂/5xx/接线期 404）与业务错误（4xx）。 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE, api, ApiError, ApiUnavailableError, setToken } from "./client";

// --- 测试环境 localStorage stub（node 无 DOM） ---
class LocalStorageStub {
  private m = new Map<string, string>();
  getItem(k: string) {
    return this.m.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.m.set(k, v);
  }
  removeItem(k: string) {
    this.m.delete(k);
  }
}

const okJson = (body: unknown) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const failJson = (status: number, detail?: unknown) => ({
  ok: false,
  status,
  json: async () => (detail === undefined ? {} : { detail }),
});

beforeEach(() => {
  vi.stubGlobal("localStorage", new LocalStorageStub());
  setToken("ui-tok");
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("URL 拼装与 token 头", () => {
  it("GET 带 query：base + path + ?status=，并带 Bearer token", async () => {
    const fetchMock = vi.fn(async () => okJson({ results: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await api.listCards("active");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(String(url)).toBe(`${API_BASE}/api/v1/cards?status=active`);
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer ui-tok");
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("POST 带 JSON body 与 Content-Type（/api/v1/ask）", async () => {
    const fetchMock = vi.fn(async () => okJson({ concept_cards: [], stance_questions: [], engine: "x" }));
    vi.stubGlobal("fetch", fetchMock);

    await api.ask("我的选择是我自己做的吗？");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(String(url)).toBe(`${API_BASE}/api/v1/ask`);
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer ui-tok");
    expect(JSON.parse(String(init.body))).toEqual({ text: "我的选择是我自己做的吗？" });
  });

  it("路径参数走 encodeURIComponent", async () => {
    const fetchMock = vi.fn(async () => okJson({}));
    vi.stubGlobal("fetch", fetchMock);

    await api.respond("card id/1", { my_response: "r" });

    const [url] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(String(url)).toBe(`${API_BASE}/api/v1/cards/card%20id%2F1/response`);
  });

  it("未设 token 时不发 Authorization 头", async () => {
    setToken("");
    const fetchMock = vi.fn(async () => okJson({ results: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await api.listCards();

    const [, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(new Headers(init.headers).get("authorization")).toBeNull();
  });

  it("token 持久化在 localStorage['zhesi_token']", async () => {
    const ls = new LocalStorageStub();
    vi.stubGlobal("localStorage", ls);
    setToken("t2");
    expect(ls.getItem("zhesi_token")).toBe("t2");
    setToken("");
    expect(ls.getItem("zhesi_token")).toBeNull();
  });
});

describe("降级与错误映射", () => {
  it("fetch reject（网络/超时/拒绝连接）→ ApiUnavailableError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    await expect(api.ask("q")).rejects.toBeInstanceOf(ApiUnavailableError);
    await expect(api.listCards()).rejects.toBeInstanceOf(ApiUnavailableError);
  });

  it("5xx → ApiUnavailableError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => failJson(503, "boom")));
    await expect(api.listCards()).rejects.toBeInstanceOf(ApiUnavailableError);
  });

  it("接线期端点 404 → ApiUnavailableError；个人层 404 → ApiError", async () => {
    const notFound = vi.fn(async () => failJson(404, "Not Found"));
    vi.stubGlobal("fetch", notFound);
    // 问辩谱（wired）：404 视为未接线
    await expect(api.ask("q")).rejects.toBeInstanceOf(ApiUnavailableError);
    await expect(api.project()).rejects.toBeInstanceOf(ApiUnavailableError);
    await expect(api.listTensions()).rejects.toBeInstanceOf(ApiUnavailableError);
    // 个人层：404 是业务错误
    await expect(api.getCard("missing")).rejects.toBeInstanceOf(ApiError);
  });

  it("4xx 带 detail → ApiError(status, detail)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => failJson(401, "missing bearer token")));
    const err = await api.listCards().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as ApiError;
    expect(apiErr.status).toBe(401);
    expect(apiErr.message).toContain("missing bearer token");
  });
});
