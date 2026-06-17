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

function getLayerValue(c: CountryRisk, layer: RiskLayer): number {
  if (layer === "regime_change") return c.regime_change_probability_1y;
  return c.conflict_probability_1y;
}

function formatValue(value: number): string {
  if (value < 0.001) return "< 0.1%";
  if (value < 0.01)  return `${(value * 100).toFixed(2)}%`;
  if (value < 0.1)   return `${(value * 100).toFixed(1)}%`;
  return `${(value * 100).toFixed(0)}%`;
}

export function TopRiskList({ countries, riskLayer, selectedCode, onSelect }: Props) {
  const sorted = [...countries]
    .sort((a, b) => getLayerValue(b, riskLayer) - getLayerValue(a, riskLayer))
    .slice(0, 5);

  const titles: Record<RiskLayer, string> = {
    conflict: "Conflict Risk TOP 5",
    regime_change: "Coup Risk TOP 5",
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <span style={{ fontSize: 10, fontWeight: 600, color: "rgba(228,237,245,0.45)", letterSpacing: "0.06em" }}>
          {titles[riskLayer]}
        </span>
        <span style={{ fontSize: 8, color: "rgba(228,237,245,0.2)", fontFamily: "monospace" }}>1-Year Forecast</span>
      </div>

      {sorted.map((c, i) => {
        const value = getLayerValue(c, riskLayer);
        const color = riskColor(value);
        const isSelected = c.country_code === selectedCode;

        return (
          <button
            key={c.country_code}
            onClick={() => onSelect(c.country_code)}
            style={rowStyle(isSelected, color)}
            onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "rgba(228,237,245,0.03)"; }}
            onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = "none"; }}
          >
            <span style={{ fontSize: 10, color: "rgba(228,237,245,0.2)", fontFamily: "monospace", width: 14, flexShrink: 0 }}>
              {i + 1}
            </span>

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: isSelected ? "#e4edf5" : "rgba(228,237,245,0.75)", fontWeight: isSelected ? 600 : 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {c.country_name}
              </div>
              <div style={{ height: 2, background: "rgba(255,255,255,0.05)", borderRadius: 1, marginTop: 4, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${Math.min(value * 100, 100)}%`, background: color, borderRadius: 1, opacity: 0.8 }} />
              </div>
            </div>

            <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace", flexShrink: 0 }}>
              {formatValue(value)}
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
  width: 220,
  background: "rgba(8, 16, 26, 0.94)",
  backdropFilter: "blur(16px)",
  border: "1px solid rgba(0, 210, 170, 0.1)",
  borderRadius: 6,
  overflow: "hidden",
  boxShadow: "0 4px 20px rgba(0, 0, 0, 0.45)",
};

const headerStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: "1px solid rgba(228,237,245,0.05)",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
};

function rowStyle(isSelected: boolean, color: string): React.CSSProperties {
  return {
    display: "flex",
    alignItems: "center",
    gap: 8,
    width: "100%",
    background: isSelected ? `${color}12` : "none",
    border: "none",
    borderBottom: "1px solid rgba(228,237,245,0.04)",
    borderLeft: isSelected ? `2px solid ${color}` : "2px solid transparent",
    cursor: "pointer",
    padding: "8px 12px 8px 10px",
    textAlign: "left",
    transition: "background 0.1s",
  };
}
