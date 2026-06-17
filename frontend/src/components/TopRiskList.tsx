import { CountryRisk, RiskLayer } from "../types";

interface Props {
  countries: CountryRisk[];
  riskLayer: RiskLayer;
  selectedCode: string | null;
  onSelect: (code: string) => void;
}

function riskColor(v: number) {
  if (v >= 0.8) return "#ff4466";
  if (v >= 0.6) return "#ff9430";
  if (v >= 0.4) return "#ffd440";
  return "#aaff44";
}
function getVal(c: CountryRisk, layer: RiskLayer) {
  if (layer === "regime_change") return c.regime_change_probability_1y;
  if (layer === "overall") return c.risk_score;
  return c.conflict_probability_1y;
}
function fmt(v: number) {
  if (v < 0.001) return "< 0.1%";
  if (v < 0.01)  return `${(v * 100).toFixed(2)}%`;
  if (v < 0.1)   return `${(v * 100).toFixed(1)}%`;
  return `${(v * 100).toFixed(0)}%`;
}

const RANK_COLORS = ["#ffd440", "rgba(228,237,245,0.35)", "rgba(228,237,245,0.2)", "rgba(228,237,245,0.12)", "rgba(228,237,245,0.08)"];

export function TopRiskList({ countries, riskLayer, selectedCode, onSelect }: Props) {
  const sorted = [...countries]
    .sort((a, b) => getVal(b, riskLayer) - getVal(a, riskLayer))
    .slice(0, 5);

  const layerLabel = riskLayer === "regime_change" ? "Coup Risk" : riskLayer === "overall" ? "Overall Risk" : "Conflict Risk";

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{ padding: "11px 14px 9px", borderBottom: "1px solid rgba(255,255,255,0.04)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 9, color: "rgba(228,237,245,0.25)", letterSpacing: "0.1em" }}>
          {layerLabel.toUpperCase()} · TOP 5
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: "#00d2aa", animation: "pulse-dot 2.5s infinite" }} />
          <span style={{ fontSize: 8, color: "#00d2aa", letterSpacing: "0.1em", fontFamily: "monospace" }}>AI</span>
        </div>
      </div>

      {/* Rows */}
      {sorted.map((c, i) => {
        const value = getVal(c, riskLayer);
        const color = riskColor(value);
        const isSelected = c.country_code === selectedCode;
        const pct = Math.min(value * 100, 100);

        return (
          <button
            key={c.country_code}
            onClick={() => onSelect(c.country_code)}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              width: "100%", background: isSelected ? `${color}10` : "transparent",
              border: "none", cursor: "pointer", padding: "9px 14px",
              textAlign: "left", transition: "background 0.12s",
              borderBottom: i < 4 ? "1px solid rgba(255,255,255,0.03)" : "none",
            }}
            onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
            onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
          >
            {/* Rank */}
            <span style={{
              fontSize: 10, fontWeight: 700,
              color: isSelected ? color : RANK_COLORS[i],
              fontFamily: "monospace", width: 14, flexShrink: 0, textAlign: "right",
            }}>
              {i + 1}
            </span>

            {/* Name + bar */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 12, fontWeight: isSelected ? 600 : 400,
                color: isSelected ? "#e4edf5" : "rgba(228,237,245,0.7)",
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                marginBottom: 4,
              }}>
                {c.country_name}
              </div>
              {/* Track */}
              <div style={{ height: 2, background: "rgba(255,255,255,0.05)", borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  height: "100%", width: `${pct}%`,
                  background: `linear-gradient(90deg, ${color}cc, ${color})`,
                  borderRadius: 2, transition: "width 0.5s ease",
                }} />
              </div>
            </div>

            {/* Value */}
            <span style={{
              fontSize: 12, fontWeight: 700, color: isSelected ? color : "rgba(228,237,245,0.6)",
              fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
              minWidth: 42, textAlign: "right",
            }}>
              {fmt(value)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

const containerStyle: React.CSSProperties = {
  position: "absolute",
  bottom: 24,
  left: 12,
  zIndex: 800,
  width: 240,
  background: "rgba(6, 10, 18, 0.96)",
  backdropFilter: "blur(20px)",
  border: "1px solid rgba(0,210,170,0.12)",
  borderRadius: 6,
  overflow: "hidden",
  boxShadow: "0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,210,170,0.04), 0 0 24px rgba(0,210,170,0.04)",
};
