import { useState } from "react";
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
  { value: "overall",       label: "Overall Risk",  color: "#00d2aa" },
  { value: "conflict",      label: "Conflict Risk", color: "#ff4466" },
  { value: "regime_change", label: "Coup Risk",     color: "#a855f7" },
];

export function MobileToolbar({
  riskLayer, predictionFrom, predictionTo,
  availableYears = [], selectedYear,
  onLayerChange, onYearChange, onConceptOpen,
}: Props) {
  const [open, setOpen] = useState(false);
  const predRange = predictionFrom && predictionTo
    ? `${predictionFrom} – ${predictionTo}`
    : "Forecast";
  const activeLayer = LAYERS.find((l) => l.value === riskLayer)!;

  const handleLayer = (v: RiskLayer) => {
    onLayerChange(v);
    setOpen(false);
  };
  const handleYear = (y: number) => {
    onYearChange?.(y);
    setOpen(false);
  };

  return (
    <>
      {/* Header bar — always visible */}
      <div style={barStyle}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
          <div style={logoMark}>
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
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
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 800, letterSpacing: "0.1em", whiteSpace: "nowrap" }}>
              <span style={{ color: "#00d2aa" }}>EARTH</span>
              <span style={{ color: "rgba(228,237,245,0.9)", marginLeft: 6 }}>TWIN</span>
            </div>
            <div style={{ fontSize: 9, color: "rgba(0,210,170,0.5)", letterSpacing: "0.08em", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              <span style={{ color: activeLayer.color }}>■</span>
              {" "}{activeLayer.label} · {predRange}
            </div>
          </div>
        </div>

        {/* Right: ? + hamburger */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0, marginLeft: "auto" }}>
          {onConceptOpen && (
            <button onClick={onConceptOpen} style={iconBtn} title="About">
              ?
            </button>
          )}
          <button onClick={() => setOpen((o) => !o)} style={iconBtn} title="Menu">
            {open ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <line x1="2" y1="2" x2="12" y2="12" stroke="#00d2aa" strokeWidth="1.5" strokeLinecap="round" />
                <line x1="12" y1="2" x2="2" y2="12" stroke="#00d2aa" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <line x1="2" y1="3.5" x2="12" y2="3.5" stroke="#00d2aa" strokeWidth="1.5" strokeLinecap="round" />
                <line x1="2" y1="7" x2="12" y2="7" stroke="#00d2aa" strokeWidth="1.5" strokeLinecap="round" />
                <line x1="2" y1="10.5" x2="12" y2="10.5" stroke="#00d2aa" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Dropdown panel */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setOpen(false)}
            style={{ position: "fixed", inset: 0, zIndex: 998, background: "rgba(0,0,0,0.4)" }}
          />
          {/* Panel */}
          <div style={panelStyle}>
            <div style={sectionLabel}>LAYER</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {LAYERS.map((l) => (
                <button key={l.value} onClick={() => handleLayer(l.value)} style={menuItem(riskLayer === l.value, l.color)}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: l.color, display: "inline-block", marginRight: 10, opacity: riskLayer === l.value ? 1 : 0.4 }} />
                  {l.label}
                </button>
              ))}
            </div>

            {availableYears.length > 1 && onYearChange && (
              <>
                <div style={{ ...sectionLabel, marginTop: 16 }}>FORECAST YEAR</div>
                <div style={{ display: "flex", gap: 6 }}>
                  {availableYears.map((y) => (
                    <button key={y} onClick={() => handleYear(y)} style={yearChip(selectedYear === y)}>
                      {y}
                    </button>
                  ))}
                </div>
              </>
            )}

            <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 4 }}>
              {(["#00d2aa", "#aaff44", "#ffd440", "#ff9430", "#ff4466"] as const).map((c, i) => (
                <div key={i} style={{ flex: 1, height: 4, background: c, borderRadius: 2, opacity: 0.7 }} />
              ))}
              <span style={{ fontSize: 8, color: "rgba(228,237,245,0.2)", marginLeft: 6, whiteSpace: "nowrap" }}>LOW→HIGH</span>
            </div>
          </div>
        </>
      )}
    </>
  );
}

const barStyle: React.CSSProperties = {
  position: "absolute",
  top: 0, left: 0, right: 0,
  zIndex: 1000,
  height: 64,
  background: "rgba(6, 10, 18, 0.98)",
  backdropFilter: "blur(24px)",
  borderBottom: "1px solid rgba(0, 210, 170, 0.15)",
  boxShadow: "0 1px 0 rgba(0,210,170,0.06), 0 4px 24px rgba(0,0,0,0.5)",
  display: "flex",
  alignItems: "center",
  gap: 12,
  padding: "0 14px",
  overflow: "hidden",
};

const logoMark: React.CSSProperties = {
  width: 42, height: 42,
  borderRadius: "50%",
  border: "1px solid rgba(0, 210, 170, 0.35)",
  display: "flex", alignItems: "center", justifyContent: "center",
  background: "radial-gradient(circle at 40% 40%, rgba(0,210,170,0.1) 0%, rgba(0,210,170,0.02) 70%)",
  boxShadow: "0 0 12px rgba(0, 210, 170, 0.12), inset 0 0 8px rgba(0,210,170,0.05)",
  flexShrink: 0,
};

const panelStyle: React.CSSProperties = {
  position: "absolute",
  top: 64, left: 0, right: 0,
  zIndex: 999,
  background: "rgba(8, 16, 26, 0.98)",
  backdropFilter: "blur(20px)",
  borderBottom: "1px solid rgba(0, 210, 170, 0.15)",
  padding: "16px 14px 18px",
  boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
};

const sectionLabel: React.CSSProperties = {
  fontSize: 9,
  color: "rgba(0,210,170,0.45)",
  letterSpacing: "0.1em",
  marginBottom: 8,
  fontFamily: "monospace",
};

const iconBtn: React.CSSProperties = {
  background: "none",
  border: "1px solid rgba(0,210,170,0.25)",
  borderRadius: "50%",
  width: 36, height: 36,
  display: "flex", alignItems: "center", justifyContent: "center",
  cursor: "pointer",
  color: "rgba(0,210,170,0.75)",
  fontSize: 14,
  fontWeight: 700,
  WebkitTapHighlightColor: "transparent",
};

function menuItem(active: boolean, color: string): React.CSSProperties {
  return {
    background: active ? `${color}18` : "transparent",
    color: active ? color : "rgba(228,237,245,0.5)",
    border: `1px solid ${active ? `${color}50` : "rgba(228,237,245,0.06)"}`,
    borderRadius: 4,
    padding: "9px 14px",
    fontSize: 12,
    fontWeight: active ? 700 : 400,
    cursor: "pointer",
    textAlign: "left",
    WebkitTapHighlightColor: "transparent",
    display: "flex",
    alignItems: "center",
  };
}

function yearChip(active: boolean): React.CSSProperties {
  return {
    background: active ? "rgba(96,165,250,0.15)" : "transparent",
    color: active ? "#60a5fa" : "rgba(228,237,245,0.4)",
    border: `1px solid ${active ? "rgba(96,165,250,0.5)" : "rgba(228,237,245,0.08)"}`,
    borderRadius: 4,
    padding: "6px 18px",
    fontSize: 12,
    fontWeight: active ? 700 : 400,
    cursor: "pointer",
    WebkitTapHighlightColor: "transparent",
  };
}
