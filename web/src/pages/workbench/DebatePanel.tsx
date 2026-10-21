/** 辩 · 最强反驳：active 卡列表 → 请传统攻击我 → 回应 + 立场现状；附立场变更（旧卡入年轮）。 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  api,
  citationText,
  type ObjectionResult,
  type StanceCard,
  type Stability,
} from "../../api/client";
import { Loadable, mapApiError } from "../../api/state";
import { DegradeBox, EmptyLine, ErrorBox, Loading, Note, SectionTitle, StabilityBadge } from "../../components/ui";

// ---- 视图（显式状态，可独立渲染降级态） ----

export function DebateView({
  cards,
  selected,
  onSelect,
  onReload,
  attack,
  onAttack,
  responseText,
  onResponseText,
  stability,
  onStability,
  onRespond,
  respondNote,
  changePositionText,
  onChangePositionText,
  changeReasons,
  onChangeReasons,
  onChange,
  changeNote,
  busy,
}: {
  cards: Loadable<StanceCard[]>;
  selected: StanceCard | null;
  onSelect: (id: string) => void;
  onReload: () => void;
  attack: Loadable<ObjectionResult>;
  onAttack: () => void;
  responseText: string;
  onResponseText: (v: string) => void;
  stability: Stability;
  onStability: (s: Stability) => void;
  onRespond: () => void;
  respondNote: string | null;
  changePositionText: string;
  onChangePositionText: (v: string) => void;
  changeReasons: string;
  onChangeReasons: (v: string) => void;
  onChange: () => void;
  changeNote: string | null;
  busy: boolean;
}) {
  const { t } = useTranslation();
  return (
    <section className="space-y-6">
      <div>
        <div className="flex items-baseline justify-between">
          <SectionTitle>{t("workbench.debate.cards")}</SectionTitle>
          <button
            type="button"
            onClick={onReload}
            className="text-xs text-neutral-500 underline hover:text-neutral-900"
          >
            {t("workbench.retry")}
          </button>
        </div>
        {cards.status === "loading" ? <Loading /> : null}
        {cards.status === "unavailable" ? <DegradeBox /> : null}
        {cards.status === "error" ? <ErrorBox message={cards.message} code={cards.code} /> : null}
        {cards.status === "ready" && cards.data.length === 0 ? (
          <EmptyLine>{t("workbench.debate.cardsEmpty")}</EmptyLine>
        ) : null}
        {cards.status === "ready" && cards.data.length > 0 ? (
          <ul className="mt-3 space-y-2">
            {cards.data.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className={`w-full rounded-lg border bg-white p-4 text-left transition-colors ${
                    selected?.id === c.id
                      ? "border-neutral-900"
                      : "border-neutral-200 hover:border-neutral-400"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-serif text-neutral-900">{c.question}</p>
                      <p className="mt-1 truncate text-sm text-neutral-600">{c.position}</p>
                    </div>
                    <StabilityBadge s={c.stability} />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {selected ? (
        <div className="space-y-5 rounded-lg border border-neutral-200 bg-white p-5">
          <div>
            <p className="text-xs text-neutral-400">{t("workbench.card.question")}</p>
            <p className="font-serif">{selected.question}</p>
          </div>
          <div>
            <p className="text-xs text-neutral-400">{t("workbench.card.position")}</p>
            <p>{selected.position}</p>
          </div>
          {selected.reasons ? (
            <div>
              <p className="text-xs text-neutral-400">{t("workbench.card.reasons")}</p>
              <p className="text-sm text-neutral-600">{selected.reasons}</p>
            </div>
          ) : null}

          {/* 最强反驳 */}
          <div className="border-t border-neutral-100 pt-4">
            <div className="flex items-center justify-between gap-3">
              <SectionTitle>{t("workbench.debate.objection")}</SectionTitle>
              <button
                type="button"
                disabled={busy}
                onClick={onAttack}
                className="rounded border border-neutral-900 px-3 py-1 text-xs text-neutral-900 hover:bg-neutral-900 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {attack.status === "loading" ? t("workbench.debate.attacking") : t("workbench.debate.attack")}
              </button>
            </div>
            {attack.status === "unavailable" ? (
              <div className="mt-3">
                <DegradeBox />
              </div>
            ) : null}
            {attack.status === "error" ? (
              <div className="mt-3">
                <ErrorBox message={attack.message} code={attack.code} />
              </div>
            ) : null}
            {attack.status === "ready" ? <ObjectionView data={attack.data} /> : null}
            {!selected.strongest_objection && attack.status !== "ready" ? (
              <p className="mt-2 text-xs text-neutral-400">{t("workbench.debate.objectionHint")}</p>
            ) : null}
            {selected.strongest_objection && attack.status !== "ready" ? (
              <blockquote className="mt-3 border-l-2 border-neutral-300 pl-3 text-sm text-neutral-700">
                {selected.strongest_objection}
              </blockquote>
            ) : null}
          </div>

          {/* 回应 */}
          <div className="border-t border-neutral-100 pt-4">
            <SectionTitle>{t("workbench.debate.responseHeading")}</SectionTitle>
            {selected.my_response ? (
              <p className="mt-2 text-sm text-neutral-600">{selected.my_response}</p>
            ) : null}
            <textarea
              value={responseText}
              onChange={(e) => onResponseText(e.target.value)}
              placeholder={t("workbench.debate.responsePlaceholder")}
              rows={3}
              className="mt-3 w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="text-xs text-neutral-500">{t("workbench.debate.stabilityLabel")}</label>
              <select
                value={stability}
                onChange={(e) => onStability(e.target.value as Stability)}
                className="rounded border border-neutral-300 bg-white px-2 py-1 text-sm"
              >
                {(["stable", "wavering", "shelved"] as const).map((s) => (
                  <option key={s} value={s}>
                    {t(`workbench.stability.${s}`)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={busy || !responseText.trim()}
                onClick={onRespond}
                className="rounded bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t("workbench.debate.respond")}
              </button>
            </div>
            {respondNote ? <Note>{respondNote}</Note> : null}
          </div>

          {/* 立场变更（旧卡封存入年轮） */}
          <details className="border-t border-neutral-100 pt-4">
            <summary className="cursor-pointer text-sm text-neutral-500 hover:text-neutral-900">
              {t("workbench.debate.changeHeading")}
            </summary>
            <div className="mt-3 space-y-3">
              <input
                value={changePositionText}
                onChange={(e) => onChangePositionText(e.target.value)}
                placeholder={t("workbench.debate.newPosition")}
                className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
              />
              <input
                value={changeReasons}
                onChange={(e) => onChangeReasons(e.target.value)}
                placeholder={t("workbench.debate.newReasons")}
                className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
              />
              <button
                type="button"
                disabled={busy || !changePositionText.trim()}
                onClick={onChange}
                className="rounded border border-neutral-900 px-4 py-2 text-sm text-neutral-900 hover:bg-neutral-900 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t("workbench.debate.change")}
              </button>
              {changeNote ? <Note>{changeNote}</Note> : null}
            </div>
          </details>
        </div>
      ) : null}
    </section>
  );
}

function ObjectionView({ data }: { data: ObjectionResult }) {
  const { t } = useTranslation();
  return (
    <div className="mt-3">
      <blockquote className="border-l-2 border-neutral-900 pl-3 font-serif text-neutral-800">
        {data.objection}
      </blockquote>
      <p className="mt-2 text-xs text-neutral-400">{t("workbench.debate.citations")}</p>
      {data.citations?.length ? (
        <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-neutral-500">
          {data.citations.map((c, i) => (
            <li key={i}>{citationText(c)}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs text-neutral-400">{t("workbench.debate.noCitations")}</p>
      )}
      {data.engine ? (
        <p className="mt-2 text-xs text-neutral-400">{t("workbench.ask.engine", { engine: data.engine })}</p>
      ) : null}
    </div>
  );
}

// ---- 容器：接 API ----

export default function DebatePanel() {
  const { t } = useTranslation();
  const [cards, setCards] = useState<Loadable<StanceCard[]>>({ status: "loading" });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [attack, setAttack] = useState<Loadable<ObjectionResult>>({ status: "idle" });
  const [responseText, setResponseText] = useState("");
  const [stability, setStability] = useState<Stability>("stable");
  const [respondNote, setRespondNote] = useState<string | null>(null);
  const [changePositionText, setChangePositionText] = useState("");
  const [changeReasons, setChangeReasons] = useState("");
  const [changeNote, setChangeNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setCards({ status: "loading" });
    try {
      setCards({ status: "ready", data: (await api.listCards("active")).results });
    } catch (e) {
      setCards(mapApiError(e));
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const selected =
    cards.status === "ready" ? cards.data.find((c) => c.id === selectedId) ?? null : null;

  const select = (id: string) => {
    setSelectedId(id);
    setAttack({ status: "idle" });
    setResponseText("");
    setRespondNote(null);
    setChangePositionText("");
    setChangeReasons("");
    setChangeNote(null);
    const card = cards.status === "ready" ? cards.data.find((c) => c.id === id) : null;
    if (card) setStability(card.stability);
  };

  const doAttack = async () => {
    if (!selected) return;
    setAttack({ status: "loading" });
    try {
      const data = await api.strongestObjection(selected.id);
      setAttack({ status: "ready", data });
      // 反驳入卡持久化（fire-and-forget，失败不影响呈现）
      try {
        await api.recordObjection(selected.id, data.objection);
        await load();
      } catch {
        /* 持久化失败可容忍 */
      }
    } catch (e) {
      setAttack(mapApiError(e));
    }
  };

  const doRespond = async () => {
    if (!selected) return;
    setBusy(true);
    setRespondNote(null);
    try {
      await api.respond(selected.id, {
        my_response: responseText.trim(),
        stability,
      });
      setRespondNote(t("workbench.debate.responded"));
      setResponseText("");
      await load();
    } catch (e) {
      const m = mapApiError(e);
      setRespondNote(m.status === "error" ? m.message : t("workbench.unavailable"));
    } finally {
      setBusy(false);
    }
  };

  const doChange = async () => {
    if (!selected) return;
    setBusy(true);
    setChangeNote(null);
    try {
      const fresh = await api.changePosition(selected.id, {
        position: changePositionText.trim(),
        reasons: changeReasons.trim() || undefined,
      });
      setChangeNote(t("workbench.debate.changed", { position: fresh.position }));
      setChangePositionText("");
      setChangeReasons("");
      await load();
      setSelectedId(fresh.id);
    } catch (e) {
      const m = mapApiError(e);
      setChangeNote(m.status === "error" ? m.message : t("workbench.unavailable"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <DebateView
      cards={cards}
      selected={selected}
      onSelect={select}
      onReload={() => void load()}
      attack={attack}
      onAttack={() => void doAttack()}
      responseText={responseText}
      onResponseText={setResponseText}
      stability={stability}
      onStability={setStability}
      onRespond={() => void doRespond()}
      respondNote={respondNote}
      changePositionText={changePositionText}
      onChangePositionText={setChangePositionText}
      changeReasons={changeReasons}
      onChangeReasons={setChangeReasons}
      onChange={() => void doChange()}
      changeNote={changeNote}
      busy={busy}
    />
  );
}
