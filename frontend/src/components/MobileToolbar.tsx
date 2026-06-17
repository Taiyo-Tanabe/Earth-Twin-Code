import { RiskLayer } from "../types";

interface Props {
  riskLayer: RiskLayer;
  predictionFrom?: string | null;
  predictionTo?: string | null;
  availableYears?: number[];
  selectedYear?: number | null;
  onLayerChange: (l: RiskLayer) => void;
  onYearChange?: (y: number) => void;
  onConceptOpen?: () => void;
}

const LAYERS: { value: RiskLayer; label: string; color: string }[] = [
  { value: "overall",       label: "Overall",  color: "#00d2aa" },
  { value: "conflict",      label: "Conflict", color: "#ff4466" },
  { value: "regime_change", label: "Coup",     color: "#a855f7" },
];

export function MobileToolbar({ riskLayer, predictionFrom, predictionTo, availableYears = [], selectedYear, onLayerChange, onYearChange, onConceptOpen }: Props) {
  const predRange = predictionFrom && predictionTo ? `${predictionFrom} – ${predictionTo}` : "1-Year Forecast";

  return (
    <div style={toolbarStyle}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
        {/* Logo + site name */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={logoMark}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9.5" stroke="#00d2aa" strokeWidth="1.5" />
              <ellipse cx="12" cy="12" rx="4.5" ry="9.5" stroke="#00d2aa" strokeWidth="1" opacity="0.6" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#e4edf5", letterSpacing: "0.06em" }}>EARTH TWIN</div>
            <div style={{ fontSize: 8, color: "rgba(0,210,170,0.4)" }}>PROBABILISTIC WORLD MODEL · {predRange}</div>
          </div>
        </div>

        {/* Right side: scale + concept button */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 1 }}>
            {(["#00d2aa", "#ffd440", "#ff4466"] as const).map((c, i) => (
              <div key={i} style={{ width: 14, height: 4, background: c, borderRadius: 1, opacity: 0.8 }} />
            ))}
          </div>
          {onConceptOpen && (
            <button
              onClick={onConceptOpen}
              title="About Earth Twin"
              style={{
                background: "none",
                border: "1px solid rgba(0,210,170,0.2)",
                borderRadius: "50%",
                width: 26, height: 26,
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer",
                color: "rgba(0,210,170,0.6)",
                fontSize: 12,
                fontWeight: 700,
                flexShrink: 0,
                WebkitTapHighlightColor: "transparent",
              }}
            >
              ?
            </button>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: 4, width: "100%" }}>
        {LAYERS.map((l) => (
          <button key={l.value} onClick={() => onLayerChange(l.value)} style={chip(riskLayer === l.value, l.color)}>
            {l.label}
          </button>
        ))}
      </div>

      {availableYears.length > 1 && onYearChange && (
        <div style={{ display: "flex", gap: 4, width: "100%" }}>
          {availableYears.map((y) => (
            <button key={y} onClick={() => onYearChange(y)} style={chip(selectedYear === y, "#60a5fa")}>
              {y}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const toolbarStyle: React.CSSProperties = {
  position: "absolute",
  top: 0, left: 0, right: 0,
  zIndex: 1000,
  background: "rgba(8, 16, 26, 0.96)",
  backdropFilter: "blur(20px)",
  borderBottom: "1px solid rgba(0, 210, 170, 0.12)",
  padding: "10px 14px 9px",
  display: "flex",
  flexDirection: "column",
  gap: 8,
};

const logoMark: React.CSSProperties = {
  width: 24, height: 24,
  border: "1px solid rgba(0, 210, 170, 0.28)",
  display: "flex", alignItems: "center", justifyContent: "center",
  background: "rgba(0, 210, 170, 0.04)",
  flexShrink: 0,
};

function chip(active: boolean, color: string): React.CSSProperties {
  return {
    flex: 1,
    background: active ? `${color}20` : "transparent",
    color: active ? color : "rgba(228,237,245,0.35)",
    border: `1px solid ${active ? `${color}60` : "rgba(228,237,245,0.08)"}`,
    borderRadius: 3,
    padding: "5px 10px",
    fontSize: 11,
    fontWeight: active ? 700 : 400,
    cursor: "pointer",
    WebkitTapHighlightColor: "transparent",
    whiteSpace: "nowrap",
    textAlign: "center",
  };
}
