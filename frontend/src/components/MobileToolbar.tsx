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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={logoMark}>
            <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="13" stroke="#00d2aa" strokeWidth="1.2" opacity="0.9" />
              <circle cx="16" cy="16" r="10" stroke="#00d2aa" strokeWidth="0.5" opacity="0.3" />
              <ellipse cx="16" cy="16" rx="5" ry="13" stroke="#00d2aa" strokeWidth="0.8" opacity="0.55" />
              <line x1="3" y1="16" x2="29" y2="16" stroke="#00d2aa" strokeWidth="0.8" opacity="0.55" />
              <ellipse cx="16" cy="11" rx="9.5" ry="2" stroke="#00d2aa" strokeWidth="0.5" opacity="0.3" />
              <ellipse cx="16" cy="21" rx="9.5" ry="2" stroke="#00d2aa" strokeWidth="0.5" opacity="0.3" />
              <circle cx="16" cy="16" r="1.5" fill="#00d2aa" opacity="0.9" />
              <line x1="16" y1="13" x2="16" y2="14.2" stroke="#00d2aa" strokeWidth="0.8" opacity="0.8" />
              <line x1="16" y1="17.8" x2="16" y2="19" stroke="#00d2aa" strokeWidth="0.8" opacity="0.8" />
              <line x1="13" y1="16" x2="14.2" y2="16" stroke="#00d2aa" strokeWidth="0.8" opacity="0.8" />
              <line x1="17.8" y1="16" x2="19" y2="16" stroke="#00d2aa" strokeWidth="0.8" opacity="0.8" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 800, color: "#e4edf5", letterSpacing: "0.1em" }}>
              <span style={{ color: "#00d2aa" }}>EARTH</span>
              <span style={{ color: "rgba(228,237,245,0.9)", marginLeft: 5 }}>TWIN</span>
            </div>
            <div style={{ fontSize: 8, color: "rgba(0,210,170,0.45)", letterSpacing: "0.12em", marginTop: 1 }}>PROBABILISTIC WORLD MODEL · {predRange}</div>
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
  width: 34, height: 34,
  borderRadius: "50%",
  border: "1px solid rgba(0, 210, 170, 0.35)",
  display: "flex", alignItems: "center", justifyContent: "center",
  background: "radial-gradient(circle at 40% 40%, rgba(0,210,170,0.1) 0%, rgba(0,210,170,0.02) 70%)",
  boxShadow: "0 0 10px rgba(0, 210, 170, 0.1), inset 0 0 6px rgba(0, 210, 170, 0.04)",
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
