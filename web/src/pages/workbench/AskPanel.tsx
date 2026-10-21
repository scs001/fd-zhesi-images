/** 问 · 概念澄清：生活语言提问 → 概念卡 + 命中立场问题 → 表态立卡。 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type AskResult, type StanceQuestion, type SurveyOption } from "../../api/client";
import { Loadable, mapApiError } from "../../api/state";
import { DegradeBox, EmptyLine, ErrorBox, Loading, Note, SectionTitle } from "../../components/ui";

// ---- 视图（显式状态，可独立渲染降级态） ----

export function AskView({
  text,
  onText,
  onSubmit,
  busy,
  result,
  onTakePosition,
  modal,
}: {
  text: string;
  onText: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  result: Loadable<AskResult>;
  onTakePosition?: (sq: StanceQuestion) => void;
  modal: TakePositionModalProps | null;
}) {
  const { t } = useTranslation();
  return (
    <section className="space-y-8">
      <div>
        <SectionTitle>{t("workbench.ask.heading")}</SectionTitle>
        <p className="mt-1 text-sm text-neutral-500">{t("workbench.ask.hint")}</p>
        <textarea
          value={text}
          onChange={(e) => onText(e.target.value)}
          placeholder={t("workbench.ask.placeholder")}
          rows={3}
          className="mt-3 w-full rounded-lg border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
        />
        <button
          type="button"
          disabled={busy || !text.trim()}
          onClick={onSubmit}
          className="mt-3 rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? t("workbench.ask.thinking") : t("workbench.ask.submit")}
        </button>
      </div>

      {result.status === "loading" ? <Loading /> : null}
      {result.status === "unavailable" ? <DegradeBox /> : null}
      {result.status === "error" ? <ErrorBox message={result.message} code={result.code} /> : null}
      {result.status === "ready" ? <AskResultView data={result.data} onTakePosition={onTakePosition} /> : null}

      {modal ? <TakePositionModal {...modal} /> : null}
    </section>
  );
}

function AskResultView({
  data,
  onTakePosition,
}: {
  data: AskResult;
  onTakePosition?: (sq: StanceQuestion) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      {data.engine ? (
        <p className="text-xs text-neutral-400">{t("workbench.ask.engine", { engine: data.engine })}</p>
      ) : null}

      <div>
        <SectionTitle>{t("workbench.ask.concepts")}</SectionTitle>
        {data.concept_cards.length === 0 ? (
          <EmptyLine>{t("workbench.ask.conceptsEmpty")}</EmptyLine>
        ) : (
          <ul className="mt-3 space-y-3">
            {data.concept_cards.map((c) => (
              <li key={c.url || c.title} className="rounded-lg border border-neutral-200 bg-white p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="font-serif text-neutral-900">{c.title}</h3>
                  {c.url ? (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="shrink-0 text-xs text-neutral-500 underline hover:text-neutral-900"
                    >
                      {t("workbench.ask.sep")}
                    </a>
                  ) : null}
                </div>
                {c.snippet ? <p className="mt-1 text-sm text-neutral-600">{c.snippet}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <SectionTitle>{t("workbench.ask.questions")}</SectionTitle>
        {data.stance_questions.length === 0 ? (
          <EmptyLine>{t("workbench.ask.questionsEmpty")}</EmptyLine>
        ) : (
          <ul className="mt-3 space-y-4">
            {data.stance_questions.map((sq) => (
              <li
                key={`${sq.survey_round}:${sq.question}`}
                className="rounded-lg border border-neutral-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-serif text-neutral-900">{sq.question}</h3>
                    <p className="mt-0.5 text-xs text-neutral-400">
                      {t("workbench.ask.round", { round: sq.survey_round })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onTakePosition?.(sq)}
                    className="shrink-0 rounded border border-neutral-900 px-3 py-1 text-xs text-neutral-900 hover:bg-neutral-900 hover:text-white"
                  >
                    {t("workbench.ask.takePosition")}
                  </button>
                </div>
                <ul className="mt-3 space-y-2">
                  {sq.options.map((o) => (
                    <li key={o.label} className="text-sm">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-neutral-800">
                          {o.label_zh ? `${o.label_zh} · ${o.label}` : o.label}
                        </span>
                        <span className="text-xs tabular-nums text-neutral-500">{pctText(o.pct)}</span>
                      </div>
                      <div className="mt-1 h-1.5 w-full rounded bg-neutral-100">
                        <div
                          className="h-1.5 rounded bg-neutral-700"
                          style={{ width: `${pctWidth(o.pct)}%` }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function pctText(pct: number): string {
  return Number.isFinite(pct) ? `${Math.round(pct)}%` : "—";
}
function pctWidth(pct: number): number {
  return Number.isFinite(pct) ? Math.max(0, Math.min(100, pct)) : 0;
}

// ---- 表态弹层 ----

interface TakePositionModalProps {
  question: StanceQuestion;
  selected: string | null;
  onSelect: (label: string) => void;
  reasons: string;
  onReasons: (v: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
  note: { kind: "created"; position: string } | { kind: "error"; message: string } | null;
}

function TakePositionModal(p: TakePositionModalProps) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-900/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
        <h3 className="font-serif text-lg">{t("workbench.ask.modalTitle")}</h3>
        <p className="mt-2 text-sm text-neutral-600">{p.question.question}</p>
        <p className="mt-4 text-xs font-medium text-neutral-500">{t("workbench.ask.pick")}</p>
        <ul className="mt-2 space-y-2">
          {p.question.options.map((o: SurveyOption) => (
            <li key={o.label}>
              <label className="flex cursor-pointer items-start gap-2 rounded border border-neutral-200 px-3 py-2 text-sm hover:border-neutral-400">
                <input
                  type="radio"
                  name="stance-option"
                  checked={p.selected === o.label}
                  onChange={() => p.onSelect(o.label)}
                  className="mt-0.5"
                />
                <span>
                  <span className="text-neutral-900">
                    {o.label_zh ? `${o.label_zh} · ${o.label}` : o.label}
                  </span>
                  {Number.isFinite(o.pct) ? (
                    <span className="ml-2 text-xs text-neutral-400">{pctText(o.pct)}</span>
                  ) : null}
                </span>
              </label>
            </li>
          ))}
        </ul>
        <textarea
          value={p.reasons}
          onChange={(e) => p.onReasons(e.target.value)}
          placeholder={t("workbench.ask.reason")}
          rows={3}
          className="mt-4 w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-900 focus:outline-none"
        />
        {p.note?.kind === "created" ? (
          <Note>{t("workbench.ask.created", { position: p.note.position })}</Note>
        ) : null}
        {p.note?.kind === "error" ? <ErrorBox message={p.note.message} /> : null}
        <div className="mt-4 flex justify-end gap-3">
          <button
            type="button"
            onClick={p.onCancel}
            className="rounded px-4 py-2 text-sm text-neutral-500 hover:text-neutral-900"
          >
            {t("workbench.ask.cancel")}
          </button>
          <button
            type="button"
            disabled={p.busy || !p.selected}
            onClick={p.onConfirm}
            className="rounded bg-neutral-900 px-4 py-2 text-sm text-white hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("workbench.ask.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- 容器：接 API ----

export default function AskPanel() {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Loadable<AskResult>>({ status: "idle" });

  // 表态弹层状态
  const [modalQuestion, setModalQuestion] = useState<StanceQuestion | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [reasons, setReasons] = useState("");
  const [modalBusy, setModalBusy] = useState(false);
  const [modalNote, setModalNote] = useState<TakePositionModalProps["note"]>(null);

  const submit = async () => {
    setBusy(true);
    setResult({ status: "loading" });
    try {
      setResult({ status: "ready", data: await api.ask(text.trim()) });
    } catch (e) {
      setResult(mapApiError(e));
    } finally {
      setBusy(false);
    }
  };

  const openModal = (sq: StanceQuestion) => {
    setModalQuestion(sq);
    setSelected(null);
    setReasons("");
    setModalNote(null);
  };

  const confirm = async () => {
    if (!modalQuestion || !selected) return;
    setModalBusy(true);
    setModalNote(null);
    try {
      await api.createCard({
        question: modalQuestion.question,
        position: selected,
        reasons: reasons.trim() || undefined,
        question_ref: `${modalQuestion.survey_round}:${modalQuestion.question}`,
      });
      setModalNote({ kind: "created", position: selected });
    } catch (e) {
      const mapped = mapApiError(e);
      setModalNote(
        mapped.status === "error"
          ? { kind: "error", message: mapped.message }
          : { kind: "error", message: t("workbench.unavailable") },
      );
    } finally {
      setModalBusy(false);
    }
  };

  return (
    <AskView
      text={text}
      onText={setText}
      onSubmit={() => void submit()}
      busy={busy}
      result={result}
      onTakePosition={openModal}
      modal={
        modalQuestion
          ? {
              question: modalQuestion,
              selected,
              onSelect: setSelected,
              reasons,
              onReasons: setReasons,
              onCancel: () => setModalQuestion(null),
              onConfirm: () => void confirm(),
              busy: modalBusy,
              note: modalNote,
            }
          : null
      }
    />
  );
}
