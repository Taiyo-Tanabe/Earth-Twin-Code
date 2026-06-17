import { CountryRisk } from "../types";

interface Props {
  country: CountryRisk | null;
  dataYear?: number | null;
  predictionFrom?: string | null;
  predictionTo?: string | null;
  conflictDefinition?: string;
  regimeChangeDefinition?: string;
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
function fmt(v: number) {
  if (v < 0.001) return "< 0.1";
  if (v < 0.01)  return (v * 100).toFixed(2);
  return (v * 100).toFixed(1);
}

function Arc({ value, color, size = 44 }: { value: number; color: string; size?: number }) {
  const sw = 3;
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

export function BottomSheet({
  country, predictionFrom, predictionTo,
  conflictDefinition, regimeChangeDefinition, onClose,
}: Props) {
  const isOpen = country !== null;

  return (
    <>
      {isOpen && (
        <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 900, background: "rgba(0,0,0,0.45)" }} />
      )}

      <div style={{
        position: "fixed", left: 0, right: 0, bottom: 0,
        zIndex: 950,
        background: "rgba(8, 14, 22, 0.98)",
        backdropFilter: "blur(24px)",
        borderTop: "1px solid rgba(255,255,255,0.07)",
        borderRadius: "14px 14px 0 0",
        boxShadow: "0 -12px 48px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.03)",
        transform: isOpen ? "translateY(0)" : "translateY(100%)",
        transition: "transform 0.32s cubic-bezier(0.32, 0.72, 0, 1)",
        maxHeight: "75vh",
        overflowY: "auto",
        paddingBottom: "env(safe-area-inset-bottom, 20px)",
      }}>

        {/* color accent */}
        {isOpen && country && (
          <div style={{ height: 1, background: `linear-gradient(90deg, ${riskColor(country.risk_score)}bb, transparent 60%)` }} />
        )}

        {/* drag handle */}
        <div style={{ display: "flex", justifyContent: "center", padding: "12px 0 6px" }}>
          <div style={{ width: 36, height: 3, borderRadius: 2, background: "rgba(228,237,245,0.1)" }} />
        </div>

        {country && (
          <div style={{ padding: "4px 18px 24px" }}>
            {/* Country header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 10, color: "rgba(228,237,245,0.25)", letterSpacing: "0.12em", fontFamily: "monospace" }}>
                  {country.country_code}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "#e4edf5", marginTop: 2, letterSpacing: "-0.01em" }}>
                  {country.country_name}
                </div>
              </div>
              {/* Overall risk pill */}
              <div style={{ textAlign: "right", paddingTop: 2 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 3, justifyContent: "flex-end" }}>
                  <span style={{ fontSize: 30, fontWeight: 800, color: riskColor(country.risk_score), fontFamily: "'JetBrains Mono', monospace", lineHeight: 1, letterSpacing: "-0.02em" }}>
                    {fmt(country.risk_score)}
                  </span>
                  <span style={{ fontSize: 14, color: "rgba(228,237,245,0.25)", fontFamily: "monospace" }}>%</span>
                </div>
                <div style={{ fontSize: 9, fontWeight: 700, color: riskColor(country.risk_score), letterSpacing: "0.1em", marginTop: 3 }}>
                  {riskLabel(country.risk_score)}
                </div>
                <div style={{ fontSize: 8, color: "rgba(228,237,245,0.2)", marginTop: 2 }}>
                  {predictionFrom && predictionTo ? `${predictionFrom} – ${predictionTo}` : "1-Year Forecast"}
                </div>
              </div>
            </div>

            {/* Stat cards */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 20 }}>
              <MiniStatCard label="Conflict Risk" value={country.conflict_probability_1y}
                color="#ff4466" definition={conflictDefinition} />
              <MiniStatCard label="Coup Risk" value={country.regime_change_probability_1y}
                color="#a855f7" definition={regimeChangeDefinition} />
            </div>

            {/* Risk factors */}
            <div style={{ fontSize: 9, color: "rgba(228,237,245,0.22)", letterSpacing: "0.1em", marginBottom: 10 }}>
              KEY RISK FACTORS
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {country.top_features.map((f, i) => (
                <span key={i} style={{
                  fontSize: 10, color: "rgba(228,237,245,0.55)",
                  background: i === 0 ? "rgba(228,237,245,0.07)" : "rgba(228,237,245,0.03)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: 6, padding: "5px 10px",
                  fontFamily: "monospace",
                }}>
                  {f}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function MiniStatCard({ label, value, color, definition }: {
  label: string; value: number; color: string; definition?: string;
}) {
  return (
    <div style={{
      padding: "12px",
      background: "rgba(255,255,255,0.03)",
      border: "1px solid rgba(255,255,255,0.06)",
      borderRadius: 10,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 9, color: "rgba(228,237,245,0.28)", letterSpacing: "0.06em", marginBottom: 6 }}>
            {label.toUpperCase()}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
            <span style={{ fontSize: 20, fontWeight: 800, color, fontFamily: "'JetBrains Mono', monospace", letterSpacing: "-0.02em", lineHeight: 1 }}>
              {value < 0.001 ? "< 0.1" : value < 0.01 ? (value * 100).toFixed(2) : (value * 100).toFixed(1)}
            </span>
            <span style={{ fontSize: 10, color: "rgba(228,237,245,0.25)", fontFamily: "monospace" }}>%</span>
          </div>
        </div>
        <Arc value={value} color={color} size={36} />
      </div>
      {definition && (
        <div style={{ fontSize: 8, color: "rgba(228,237,245,0.2)", marginTop: 8, lineHeight: 1.5 }}>
          {definition}
        </div>
      )}
    </div>
  );
}
