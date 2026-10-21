import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

/** 六轴细线玫珂——页面唯一的动效时刻：轴与环加载时一次画成。 */
function AxisRose() {
  const axes = ["个体", "物质", "理性", "决定", "超越", "普遍"];
  const cx = 150;
  const cy = 150;
  const r = 118;
  const pts = (radius: number) =>
    axes
      .map((_, i) => {
        const a = (Math.PI / 3) * i - Math.PI / 2;
        return `${cx + radius * Math.cos(a)},${cy + radius * Math.sin(a)}`;
      })
      .join(" ");
  return (
    <svg viewBox="0 0 300 300" className="w-full max-w-sm" role="img" aria-label="六轴哲学坐标">
      <polygon points={pts(r)} fill="none" stroke="currentColor" strokeOpacity={0.28} strokeWidth={1} className="axis-draw axis-draw-3" style={{ ["--dash" as string]: 760 }} />
      <polygon points={pts(r * 0.55)} fill="none" stroke="currentColor" strokeOpacity={0.18} strokeWidth={1} className="axis-draw axis-draw-2" style={{ ["--dash" as string]: 420 }} />
      {axes.map((label, i) => {
        const a = (Math.PI / 3) * i - Math.PI / 2;
        const x = cx + r * Math.cos(a);
        const y = cy + r * Math.sin(a);
        const lx = cx + (r + 22) * Math.cos(a);
        const ly = cy + (r + 22) * Math.sin(a);
        return (
          <g key={label}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="currentColor" strokeOpacity={0.22} strokeWidth={1} className="axis-draw axis-draw-1" style={{ ["--dash" as string]: 130 }} />
            <circle cx={x} cy={y} r={2.5} fill="currentColor" fillOpacity={0.55} />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize={13} fill="currentColor" fillOpacity={0.75} className="font-display">
              {label}
            </text>
          </g>
        );
      })}
      <polygon
        points={`${cx + r * 0.72 * Math.cos(-Math.PI / 2)},${cy + r * 0.72 * Math.sin(-Math.PI / 2)}
                 ${cx + r * 0.4 * Math.cos(-Math.PI / 6)},${cy + r * 0.4 * Math.sin(-Math.PI / 6)}
                 ${cx + r * 0.62 * Math.cos(Math.PI / 2)},${cy + r * 0.62 * Math.sin(Math.PI / 2)}
                 ${cx + r * 0.45 * Math.cos(Math.PI * 0.8)},${cy + r * 0.45 * Math.sin(Math.PI * 0.8)}`}
        fill="currentColor"
        fillOpacity={0.1}
        stroke="currentColor"
        strokeOpacity={0.5}
        strokeWidth={1.5}
        className="axis-draw axis-draw-3"
        style={{ ["--dash" as string]: 620 }}
      />
    </svg>
  );
}

function LoopBand({ index, name, title, body, detail }: { index: number; name: string; title: string; body: string; detail: string }) {
  return (
    <section className={`border-t border-line ${index % 2 === 1 ? "bg-mist" : "bg-paper"}`}>
      <div className="mx-auto grid max-w-5xl gap-6 px-6 py-14 md:grid-cols-[10rem_1fr] md:gap-12 md:py-16">
        <div className="font-display text-2xl text-axis md:text-right">{name}</div>
        <div className="max-w-2xl">
          <h2 className="font-display text-2xl leading-snug text-ink md:text-[1.7rem]">{title}</h2>
          <p className="mt-4 leading-loose text-ink-soft">{body}</p>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft/90">{detail}</p>
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  const { t } = useTranslation();
  const loops = (["ask", "debate", "map"] as const).map((k) => ({
    name: t(`landing.loops.${k}.name`),
    title: t(`landing.loops.${k}.title`),
    body: t(`landing.loops.${k}.body`),
    detail: t(`landing.loops.${k}.detail`),
  }));
  return (
    <main className="bg-paper">
      {/* Hero——深夜的思考场 */}
      <section className="bg-night text-moon">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 lg:grid-cols-12 lg:py-28">
          <div className="lg:col-span-7">
            <h1 className="hero-rise font-display text-5xl leading-tight tracking-wide text-white md:text-6xl">
              {t("landing.hero.statement1")}
            </h1>
            <p className="hero-rise hero-rise-1 mt-5 font-display text-2xl leading-snug text-moon/85 md:text-3xl">
              {t("landing.hero.statement2")}
            </p>
            <p className="hero-rise hero-rise-2 mt-7 max-w-xl leading-loose text-moon/70">
              {t("landing.hero.lede")}
            </p>
            <div className="hero-rise hero-rise-3 mt-10 flex flex-wrap items-center gap-4">
              <Link
                to="/workbench"
                className="rounded-md bg-moon px-6 py-3 text-sm font-medium text-night-deep transition-colors hover:bg-white"
              >
                {t("landing.hero.cta")}
              </Link>
              <a href="#loops" className="rounded-md border border-moon/30 px-6 py-3 text-sm text-moon transition-colors hover:border-moon/70">
                {t("landing.hero.ctaSecondary")}
              </a>
            </div>
            <p className="hero-rise hero-rise-3 mt-8 text-xs leading-relaxed text-moon/45">
              {t("landing.hero.sources")}
            </p>
          </div>
          <div className="hero-rise hero-rise-2 text-moon lg:col-span-5">
            <div className="mx-auto max-w-sm">
              <AxisRose />
            </div>
          </div>
        </div>
      </section>

      {/* 三个闭环——编辑部式横带，非卡片阵 */}
      <div id="loops" className="scroll-mt-16">
        {loops.map((l, i) => (
          <LoopBand key={l.name} index={i} {...l} />
        ))}
      </div>

      {/* 个人层私有——产品真话 */}
      <section className="border-t border-line bg-night-deep text-moon">
        <div className="mx-auto max-w-3xl px-6 py-16 text-center">
          <h2 className="font-display text-2xl leading-snug text-white md:text-3xl">{t("landing.privacy.title")}</h2>
          <p className="mx-auto mt-5 max-w-xl leading-loose text-moon/70">{t("landing.privacy.body")}</p>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-line bg-paper">
        <div className="mx-auto max-w-3xl px-6 py-20 text-center">
          <h2 className="font-display text-3xl leading-snug text-ink">{t("landing.cta.title")}</h2>
          <p className="mt-4 leading-loose text-ink-soft">{t("landing.cta.body")}</p>
          <Link
            to="/workbench"
            className="mt-8 inline-block rounded-md bg-night px-8 py-3.5 text-sm font-medium text-moon transition-colors hover:bg-night-deep"
          >
            {t("landing.hero.cta")}
          </Link>
          <p className="mt-6 text-xs text-ink-soft/70">{t("landing.cta.family")}</p>
        </div>
      </section>
    </main>
  );
}
