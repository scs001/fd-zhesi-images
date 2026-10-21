/** 工作台：问 / 辩 / 谱 三闭环（task 6.2）。 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import AskPanel from "./workbench/AskPanel";
import DebatePanel from "./workbench/DebatePanel";
import MapPanel from "./workbench/MapPanel";

type Tab = "ask" | "debate" | "map";
const TABS: readonly Tab[] = ["ask", "debate", "map"];

export default function Workbench() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("ask");

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-serif">{t("workbench.title")}</h1>
      <p className="mt-1 text-sm text-neutral-500">{t("workbench.subtitle")}</p>

      <div className="mt-6 flex gap-1 border-b border-neutral-200" role="tablist">
        {TABS.map((k) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm transition-colors ${
              tab === k
                ? "border-neutral-900 font-medium text-neutral-900"
                : "border-transparent text-neutral-500 hover:text-neutral-900"
            }`}
          >
            {t(`workbench.tabs.${k}`)}
          </button>
        ))}
      </div>

      <div className="mt-8">
        {tab === "ask" ? <AskPanel /> : null}
        {tab === "debate" ? <DebatePanel /> : null}
        {tab === "map" ? <MapPanel /> : null}
      </div>
    </main>
  );
}
