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

function ProbBar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden", marginTop: 6 }}>
      <div style={{
        height: "100%",
        width: `${value * 100}%`,
        background: color,
        borderRadius: 2,
        transition: "width 0.5s ease",
        opacity: 0.85,
      }} />
    </div>
  );
}

function TrendBadge({ trend }: { trend: CountryRisk["risk_trend"] }) {
  const map = {
    up:     { label: "↑ Rising",  color: "#ff4466" },
    down:   { label: "↓ Declining",  color: "#00d2aa" },
    stable: { label: "→ Stable",  color: "rgba(228,237,245,0.35)" },
  };
  const t = map[trend];
  return (
    <span style={{ fontSize: 10, color: t.color, fontFamily: "'JetBrains Mono', monospace" }}>
      {t.label}
    </span>
  );
}

export function CountryPanel({ country, dataYear, predictionFrom, predictionTo, conflictDefinition, regimeChangeDefinition, onClose }: Props) {
  if (!country) return null;

  const color = riskColor(country.risk_score);
  const label = riskLabel(country.risk_score);
  const predLabel = predictionFrom && predictionTo
    ? `${predictionFrom} – ${predictionTo}`
    : "1-Year Forecast";

  return (
    <div style={panelStyle}>
      <div style={{ height: 2, background: `linear-gradient(90deg, ${color}, transparent)` }} />

      {/* Header */}
      <div style={{ padding: "16px 18px 14px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 10, color: "rgba(228,237,245,0.3)", letterSpacing: "0.1em", fontFamily: "monospace" }}>
              {country.country_code}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#e4edf5", marginTop: 2, lineHeight: 1.2 }}>
              {country.country_name}
            </div>
          </div>
          <button onClick={onClose} style={closeBtnStyle}>✕</button>
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 14 }}>
          <span style={{ fontSize: 42, fontWeight: 800, color, lineHeight: 1, fontFamily: "'JetBrains Mono', monospace" }}>
            {country.risk_score < 0.001 ? "< 0.1" : country.risk_score < 0.01 ? (country.risk_score * 100).toFixed(2) : (country.risk_score * 100).toFixed(1)}
          </span>
          <span style={{ fontSize: 18, color: "rgba(228,237,245,0.3)", fontFamily: "monospace" }}>%</span>
          <div style={{ marginLeft: 2 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color, letterSpacing: "0.08em" }}>{label}</div>
            <TrendBadge trend={country.risk_trend} />
          </div>
        </div>
        <ProbBar value={country.risk_score} color={color} />
        <div style={{ fontSize: 9, color: "rgba(228,237,245,0.25)", marginTop: 4 }}>
          Overall Risk — {predLabel}
        </div>
      </div>

      <hr style={hrStyle} />

      {/* Risk indicators */}
      <div style={{ padding: "0 18px" }}>
        <SectionLabel>RISK INDICATORS — {predLabel}</SectionLabel>
        <MetricRow
          label="Conflict Risk"
          value={country.conflict_probability_1y}
          color="#ff4466"
          definition={conflictDefinition}
        />
        <MetricRow
          label="Coup Risk"
          value={country.regime_change_probability_1y}
          color="#a855f7"
          definition={regimeChangeDefinition}
        />
      </div>


      <hr style={hrStyle} />
      <div style={{ padding: "0 18px 18px" }}>
        <SectionLabel>KEY RISK FACTORS</SectionLabel>
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 1 }}>
          {country.top_features.map((f, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid rgba(228,237,245,0.04)" }}>
              <span style={{ fontSize: 9, color: "#00d2aa", fontFamily: "monospace", flexShrink: 0 }}>{i + 1}</span>
              <span style={{ fontSize: 11, color: "rgba(228,237,245,0.6)", fontFamily: "monospace" }}>{f}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: "8px 18px 14px", borderTop: "1px solid rgba(228,237,245,0.04)" }}>
        <div style={{ fontSize: 9, color: "rgba(228,237,245,0.15)", fontFamily: "monospace" }}>
          Earth Twin v0.1 · XGBoost · {predLabel}
        </div>
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, color: "rgba(228,237,245,0.3)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
      {children}
    </div>
  );
}

function formatProb(value: number): { display: string; suffix: string } {
  if (value < 0.001) return { display: "< 0.1", suffix: "%" };
  if (value < 0.01) return { display: (value * 100).toFixed(2), suffix: "%" };
  return { display: (value * 100).toFixed(1), suffix: "%" };
}

function MetricRow({ label, value, color, definition }: { label: string; value: number; color: string; definition?: string }) {
  const { display, suffix } = formatProb(value);
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <span style={{ fontSize: 11, color: "rgba(228,237,245,0.55)" }}>{label}</span>
          {definition && (
            <div style={{ fontSize: 9, color: "rgba(228,237,245,0.28)", marginTop: 2, lineHeight: 1.4, maxWidth: 160 }}>
              {definition}
            </div>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 2, flexShrink: 0, marginLeft: 8 }}>
          <span style={{ fontSize: 20, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
            {display}
          </span>
          <span style={{ fontSize: 11, color: "rgba(228,237,245,0.3)", fontFamily: "monospace" }}>{suffix}</span>
        </div>
      </div>
      <ProbBar value={value} color={color} />
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "rgba(228,237,245,0.03)", border: "1px solid rgba(228,237,245,0.06)", borderRadius: 4, padding: "8px 10px" }}>
      <div style={{ fontSize: 9, color: "rgba(228,237,245,0.3)", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  width: 296,
  maxWidth: "100%",
  maxHeight: "100%",
  background: "rgba(8, 16, 26, 0.97)",
  backdropFilter: "blur(20px)",
  borderLeft: "1px solid rgba(0, 210, 170, 0.12)",
  overflowY: "auto",
  flexShrink: 0,
  pointerEvents: "auto",
  boxShadow: "-4px 0 24px rgba(0,0,0,0.5)",
  animation: "panel-in 0.18s ease-out",
};

const hrStyle: React.CSSProperties = {
  border: "none",
  borderTop: "1px solid rgba(228,237,245,0.06)",
  margin: "14px 0",
};

const closeBtnStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "rgba(228,237,245,0.3)",
  cursor: "pointer",
  fontSize: 14,
  padding: 4,
  lineHeight: 1,
};
