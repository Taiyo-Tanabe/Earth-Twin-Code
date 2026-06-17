import { CountryRisk, RiskLayer } from "../types";

interface Props {
  country: CountryRisk | null;
  dataYear?: number | null;
  predictionFrom?: string | null;
  predictionTo?: string | null;
  conflictDefinition?: string;
  regimeChangeDefinition?: string;
  riskLayer?: RiskLayer;
  onClose: () => void;
}

function riskColor(v: number) {
  if (v >= 0.8) return "#ff4466";
  if (v >= 0.6) return "#ff9430";
  if (v >= 0.4) return "#ffd440";
  if (v >= 0.2) return "#aaff44";
  return "#00d2aa";
}
function riskLabel(v: number) {
  if (v >= 0.8) return "CRITICAL";
  if (v >= 0.6) return "HIGH";
  if (v >= 0.4) return "ELEVATED";
  if (v >= 0.2) return "GUARDED";
  return "LOW";
}
function riskTrend(t: CountryRisk["risk_trend"]) {
  if (t === "up")   return { sym: "↑", label: "Rising",    color: "#ff4466" };
  if (t === "down") return { sym: "↓", label: "Declining", color: "#00d2aa" };
  return              { sym: "→", label: "Stable",     color: "rgba(228,237,245,0.3)" };
}
function fmt(v: number) {
  if (v < 0.001) return "< 0.1";
  if (v < 0.01)  return (v * 100).toFixed(2);
  return (v * 100).toFixed(1);
}

function Arc({ value, color, size = 52 }: { value: number; color: string; size?: number }) {
  const sw = 3.5;
  const r  = (size - sw) / 2;
  const c  = size / 2;
  const circ = 2 * Math.PI * r;
  const arc  = circ * 0.75;
  const fill = Math.min(value, 1) * arc;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}
         style={{ transform: "rotate(-225deg)", flexShrink: 0 }}>
      <circle cx={c} cy={c} r={r} fill="none"
        stroke="rgba(255,255,255,0.06)" strokeWidth={sw}
        strokeDasharray={`${arc} ${circ - arc}`} strokeLinecap="round" />
      <circle cx={c} cy={c} r={r} fill="none"
        stroke={color} strokeWidth={sw} strokeOpacity={0.9}
        strokeDasharray={`${fill} ${circ - fill}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.65s cubic-bezier(0.4,0,0.2,1)" }} />
    </svg>
  );
}

export function CountryPanel({
  country, predictionFrom, predictionTo,
  conflictDefinition, regimeChangeDefinition, onClose,
}: Props) {
  if (!country) return null;

  const color    = riskColor(country.risk_score);
  const label    = riskLabel(country.risk_score);
  const trend    = riskTrend(country.risk_trend);
  const predLabel = predictionFrom && predictionTo
    ? `${predictionFrom} – ${predictionTo}`
    : "1-Year Forecast";

  return (
    <div style={panelStyle}>
      {/* top accent */}
      <div style={{ height: 1, background: `linear-gradient(90deg, ${color}cc, transparent 60%)` }} />

      {/* ── Header ─────────────────────────────── */}
      <div style={{ padding: "18px 18px 0" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 10, color: "rgba(228,237,245,0.25)", letterSpacing: "0.12em", fontFamily: "monospace" }}>
              {country.country_code}
            </div>
            <div style={{ fontSize: 19, fontWeight: 700, color: "#e4edf5", marginTop: 3, lineHeight: 1.25, letterSpacing: "-0.01em" }}>
              {country.country_name}
            </div>
          </div>
          <button onClick={onClose} style={closeBtnStyle}>✕</button>
        </div>
      </div>

      {/* ── Hero stat ─────────────────────────── */}
      <div style={{ margin: "14px 14px 0", padding: "16px", background: "rgba(255,255,255,0.03)", borderRadius: 10, border: "1px solid rgba(255,255,255,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
              <span style={{ fontSize: 44, fontWeight: 800, color, lineHeight: 1, fontFamily: "'JetBrains Mono', monospace", letterSpacing: "-0.02em" }}>
                {fmt(country.risk_score)}
              </span>
              <span style={{ fontSize: 18, color: "rgba(228,237,245,0.25)", fontFamily: "monospace", fontWeight: 400 }}>%</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color, letterSpacing: "0.1em", background: `${color}18`, border: `1px solid ${color}40`, borderRadius: 4, padding: "2px 7px" }}>
                {label}
              </span>
              <span style={{ fontSize: 10, color: trend.color, letterSpacing: "0.04em" }}>
                {trend.sym} {trend.label}
              </span>
            </div>
            <div style={{ fontSize: 9, color: "rgba(228,237,245,0.2)", marginTop: 6, letterSpacing: "0.04em" }}>
              Overall Risk · {predLabel}
            </div>
          </div>
          <Arc value={country.risk_score} color={color} size={56} />
        </div>
      </div>

      {/* ── Two stat cards ────────────────────── */}
      <div style={{ margin: "10px 14px 0", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <StatCard
          label="Conflict Risk"
          value={country.conflict_probability_1y}
          color="#ff4466"
          definition={conflictDefinition}
        />
        <StatCard
          label="Coup Risk"
          value={country.regime_change_probability_1y}
          color="#a855f7"
          definition={regimeChangeDefinition}
        />
      </div>

      {/* ── Risk factors ──────────────────────── */}
      <div style={{ margin: "16px 14px 0" }}>
        <div style={{ fontSize: 9, color: "rgba(228,237,245,0.22)", letterSpacing: "0.1em", marginBottom: 10 }}>
          KEY RISK FACTORS
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {country.top_features.map((f, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "7px 10px",
              borderRadius: 6,
              background: i === 0 ? "rgba(255,255,255,0.04)" : "transparent",
              transition: "background 0.1s",
            }}>
              <span style={{
                fontSize: 9, fontWeight: 700,
                color: i === 0 ? color : "rgba(228,237,245,0.2)",
                fontFamily: "monospace", width: 14, flexShrink: 0,
              }}>{i + 1}</span>
              <span style={{ fontSize: 11, color: i === 0 ? "rgba(228,237,245,0.8)" : "rgba(228,237,245,0.45)", fontFamily: "monospace" }}>
                {f}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Footer ────────────────────────────── */}
      <div style={{ margin: "16px 14px 16px" }}>
        <div style={{ fontSize: 9, color: "rgba(228,237,245,0.12)", fontFamily: "monospace", letterSpacing: "0.06em" }}>
          EARTH TWIN v0.1 · XGBOOST · {predLabel}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, definition }: {
  label: string; value: number; color: string; definition?: string;
}) {
  return (
    <div style={{
      padding: "12px 12px 10px",
      background: "rgba(255,255,255,0.025)",
      border: "1px solid rgba(255,255,255,0.05)",
      borderRadius: 10,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 9, color: "rgba(228,237,245,0.3)", letterSpacing: "0.06em", marginBottom: 6 }}>
            {label.toUpperCase()}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
            <span style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "'JetBrains Mono', monospace", letterSpacing: "-0.02em", lineHeight: 1 }}>
              {fmt(value)}
            </span>
            <span style={{ fontSize: 11, color: "rgba(228,237,245,0.25)", fontFamily: "monospace" }}>%</span>
          </div>
        </div>
        <Arc value={value} color={color} size={36} />
      </div>
      {definition && (
        <div style={{ fontSize: 8, color: "rgba(228,237,245,0.22)", marginTop: 8, lineHeight: 1.5 }}>
          {definition}
        </div>
      )}
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  width: 302,
  maxWidth: "100%",
  maxHeight: "100%",
  background: "rgba(8, 14, 22, 0.97)",
  backdropFilter: "blur(24px)",
  borderLeft: "1px solid rgba(255,255,255,0.06)",
  overflowY: "auto",
  flexShrink: 0,
  pointerEvents: "auto",
  boxShadow: "-8px 0 40px rgba(0,0,0,0.6)",
  animation: "panel-in 0.18s ease-out",
};

const closeBtnStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "rgba(228,237,245,0.2)",
  cursor: "pointer",
  fontSize: 13,
  padding: 4,
  lineHeight: 1,
  flexShrink: 0,
  transition: "color 0.1s",
};
