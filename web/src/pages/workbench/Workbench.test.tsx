/**
 * Workbench 冒烟：API 全挂（mock fetch reject）时三个 tab 的降级渲染。
 * 无 jsdom 依赖，用 react-dom/server renderToString 直渲视图层
 * （视图与容器同文件，容器 useEffect 走的就是同一 mapApiError 映射，
 *  client.test.ts 已覆盖 fetch reject → ApiUnavailableError）。
 */
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import "../../i18n";
import { api, ApiUnavailableError } from "../../api/client";
import { mapApiError } from "../../api/state";
import { AskView } from "./AskPanel";
import { DebateView } from "./DebatePanel";
import { MapView } from "./MapPanel";

const noop = () => {};

describe("API 全挂时的降级态", () => {
  it("mock fetch reject：面板实际调用的加载路径映射为 unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("fetch failed"))));
    // 这些正是三个容器 useEffect 里跑的调用
    await expect(api.listCards("active")).rejects.toBeInstanceOf(ApiUnavailableError);
    await expect(api.annals()).rejects.toBeInstanceOf(ApiUnavailableError);
    await expect(api.listTensions()).rejects.toBeInstanceOf(ApiUnavailableError);
    await expect(api.ask("q")).rejects.toBeInstanceOf(ApiUnavailableError);
    // 容器 catch 后套用的映射
    expect(mapApiError(new ApiUnavailableError())).toEqual({ status: "unavailable" });
    vi.unstubAllGlobals();
  });

  it("问：ask 结果 unavailable → 渲染「接线中」而非白屏", () => {
    const html = renderToString(
      <AskView
        text=""
        onText={noop}
        onSubmit={noop}
        busy={false}
        result={{ status: "unavailable" }}
        modal={null}
      />,
    );
    expect(html).toContain("接线中");
    // 提问入口仍在，白屏恢复无死角
    expect(html).toContain("提问");
  });

  it("辩：active 卡列表 unavailable → 渲染「接线中」", () => {
    const html = renderToString(
      <DebateView
        cards={{ status: "unavailable" }}
        selected={null}
        onSelect={noop}
        onReload={noop}
        attack={{ status: "idle" }}
        onAttack={noop}
        responseText=""
        onResponseText={noop}
        stability="stable"
        onStability={noop}
        onRespond={noop}
        respondNote={null}
        changePositionText=""
        onChangePositionText={noop}
        changeReasons=""
        onChangeReasons={noop}
        onChange={noop}
        changeNote={null}
        busy={false}
      />,
    );
    expect(html).toContain("接线中");
  });

  it("谱：投影/张力簿/年轮 unavailable → 渲染「接线中」", () => {
    const html = renderToString(
      <MapView
        count={{ status: "unavailable" }}
        projection={{ status: "unavailable" }}
        onProject={noop}
        tensions={{ status: "unavailable" }}
        annals={{ status: "unavailable" }}
        history={{ status: "unavailable" }}
      />,
    );
    expect(html).toContain("接线中");
  });

  it("谱：少于 5 张卡时按钮禁用并提示；就绪投影渲染 SVG 雷达与邻居", () => {
    const disabled = renderToString(
      <MapView
        count={{ status: "ready", data: 3 }}
        projection={{ status: "idle" }}
        onProject={noop}
        tensions={{ status: "idle" }}
        annals={{ status: "idle" }}
        history={{ status: "idle" }}
      />,
    );
    expect(disabled).toContain("disabled"); // 合成按钮禁用
    expect(disabled).toContain("3 张");

    const ready = renderToString(
      <MapView
        count={{ status: "ready", data: 6 }}
        projection={{
          status: "ready",
          data: {
            axes: { 自由意志: -0.7, 决定论: 0.8, 道德实在: 0.2, 相对主义: -0.4, 本质主义: 0.6, 建构主义: 0.1 },
            neighbors: [
              { name_en: "Existentialism", name_zh: "存在主义", distance: 0.42 },
              { name_en: "Stoicism", name_zh: "斯多葛主义", distance: 0.71 },
            ],
            based_on_cards: ["a", "b", "c", "d", "e", "f"],
            skipped: ["g"],
          },
        }}
        onProject={noop}
        tensions={{ status: "idle" }}
        annals={{ status: "idle" }}
        history={{ status: "idle" }}
      />,
    );
    expect(ready).toContain("<svg"); // 原生 SVG 雷达
    expect(ready).toContain("polygon");
    expect(ready).toContain("存在主义"); // 邻居 zh 名
    expect(ready).toContain("斯多葛主义");
    expect(ready).toContain("6 张"); // based_on 计数
    expect(ready).toContain("g"); // skipped 提示
  });
});
