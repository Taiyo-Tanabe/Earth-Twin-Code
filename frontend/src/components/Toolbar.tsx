import { useEffect, useState } from "react";
import { RiskLayer } from "../types";
import { useViewportWidth } from "../hooks/useViewportWidth";

interface Props {
  riskLayer: RiskLayer;
  updatedAt: string;
  predictionFrom?: string | null;
  predictionTo?: string | null;
  onLayerChange: (l: RiskLayer) => void;
  onConceptOpen?: () => void;
}

const LAYERS: { value: RiskLayer; label: string; color: string }[] = [
  { value: "conflict",      label: "Conflict Risk", color: "#ff4466" },
  { value: "regime_change", label: "Coup Risk", color: "#a855f7" },
];

export function Toolbar({ riskLayer, predictionFrom, predictionTo, onLayerChange, onConceptOpen }: Props) {
  const predRange = predictionFrom && predictionTo ? `${predictionFrom} – ${predictionTo}` : "1-Year Forecast";
  const activeLayer = LAYERS.find((l) => l.value === riskLayer)!;
  const [, setTick] = useState(0);
  const vw = useViewportWidth();
  const showScale = vw >= 960;
  const showSubtitle = vw >= 880;
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const timeStr = new Date().toISOString().slice(11, 19) + " UTC";

  return (
    <div style={barStyle}>
      <div style={leftAccent} />

      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <div style={logoMark}>
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
            {/* Outer ring */}
            <circle cx="16" cy="16" r="13" stroke="#00d2aa" strokeWidth="1.2" opacity="0.9" />
            {/* Inner glow ring */}
            <circle cx="16" cy="16" r="10" stroke="#00d2aa" strokeWidth="0.5" opacity="0.3" />
            {/* Meridian */}
            <ellipse cx="16" cy="16" rx="5" ry="13" stroke="#00d2aa" strokeWidth="0.8" opacity="0.55" />
            {/* Equator */}
            <line x1="3" y1="16" x2="29" y2="16" stroke="#00d2aa" strokeWidth="0.8" opacity="0.55" />
            {/* Latitude lines */}
            <ellipse cx="16" cy="11" rx="9.5" ry="2" stroke="#00d2aa" strokeWidth="0.5" opacity="0.3" />
            <ellipse cx="16" cy="21" rx="9.5" ry="2" stroke="#00d2aa" strokeWidth="0.5" opacity="0.3" />
            {/* Scan dot */}
            <circle cx="16" cy="16" r="1.5" fill="#00d2aa" opacity="0.9" />
            {/* Crosshair */}
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
          {showSubtitle && <div style={{ fontSize: 9, color: "rgba(0,210,170,0.45)", letterSpacing: "0.12em", marginTop: 1 }}>GLOBAL RISK INTELLIGENCE · {predRange}</div>}
        </div>
      </div>

      <div style={sep} />

      {/* Layer */}
      <div style={group}>
        <div style={groupLabel}>LAYER</div>
        <div style={{ display: "flex", gap: 2 }}>
          {LAYERS.map((l) => (
            <button key={l.value} onClick={() => onLayerChange(l.value)} style={chip(riskLayer === l.value, l.color)}>
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {showScale && <div style={sep} />}

      {/* Scale — hidden when viewport is narrow */}
      {showScale && (
        <div style={group}>
          <div style={groupLabel}>RISK SCALE</div>
          <div style={{ display: "flex", alignItems: "center", gap: 1 }}>
            {(["#00d2aa", "#aaff44", "#ffd440", "#ff9430", "#ff4466"] as const).map((c, i) => (
              <div key={i} style={{ width: 22, height: 5, background: c, borderRadius: 1, opacity: 0.85 }} />
            ))}
            <span style={{ fontSize: 9, color: "rgba(228,237,245,0.25)", marginLeft: 6 }}>LOW→HIGH</span>
          </div>
        </div>
      )}

      <div style={{ flex: 1 }} />

      {/* Status */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5, justifyContent: "flex-end" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: activeLayer.color }} />
            <span style={{ fontSize: 10, fontWeight: 600, color: activeLayer.color }}>{activeLayer.label}</span>
          </div>
          <div style={{ fontSize: 9, color: "rgba(228,237,245,0.25)", marginTop: 2 }}>{predRange}</div>
        </div>
        <div style={sep} />
        <div style={{ textAlign: "right" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#00d2aa", animation: "pulse-dot 2.5s infinite" }} />
            <span style={{ fontSize: 10, color: "#00d2aa", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.04em" }}>LIVE</span>
          </div>
          <div style={{ fontSize: 8, color: "rgba(228,237,245,0.2)", marginTop: 1, fontFamily: "monospace" }}>{timeStr}</div>
        </div>

        {onConceptOpen && (
          <>
            <div style={sep} />
            <button
              onClick={onConceptOpen}
              title="About Earth Twin"
              style={{
                background: "none",
                border: "1px solid rgba(0,210,170,0.2)",
                borderRadius: "50%",
                width: 28, height: 28,
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer",
                color: "rgba(0,210,170,0.6)",
                fontSize: 13,
                fontWeight: 700,
                flexShrink: 0,
                transition: "all 0.12s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(0,210,170,0.08)"; e.currentTarget.style.color = "#00d2aa"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "rgba(0,210,170,0.6)"; }}
            >
              ?
            </button>
          </>
        )}
      </div>

      <div style={bottomAccent} />
    </div>
  );
}

const barStyle: React.CSSProperties = {
  position: "absolute",
  top: 0, left: 0, right: 0,
  zIndex: 1000,
  background: "rgba(8, 16, 26, 0.96)",
  backdropFilter: "blur(20px)",
  borderBottom: "1px solid rgba(0, 210, 170, 0.12)",
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "0 16px",
  height: 56,
  overflow: "hidden",
  minWidth: 0,
};

const leftAccent: React.CSSProperties = {
  position: "absolute",
  left: 0, top: 8, bottom: 8,
  width: 2,
  background: "linear-gradient(180deg, transparent, #00d2aa, transparent)",
  borderRadius: 1,
};

const bottomAccent: React.CSSProperties = {
  position: "absolute",
  bottom: 0, left: 0, right: 0, height: 1,
  background: "linear-gradient(90deg, transparent, rgba(0,210,170,0.3) 30%, rgba(0,210,170,0.3) 70%, transparent)",
  pointerEvents: "none",
};

const sep: React.CSSProperties = {
  width: 1, height: 24,
  background: "rgba(228, 237, 245, 0.08)",
  flexShrink: 0,
};

const group: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 5,
};

const groupLabel: React.CSSProperties = {
  fontSize: 9,
  color: "rgba(228, 237, 245, 0.3)",
  letterSpacing: "0.06em",
};

const logoMark: React.CSSProperties = {
  width: 38, height: 38,
  borderRadius: "50%",
  border: "1px solid rgba(0, 210, 170, 0.35)",
  display: "flex", alignItems: "center", justifyContent: "center",
  background: "radial-gradient(circle at 40% 40%, rgba(0,210,170,0.1) 0%, rgba(0,210,170,0.02) 70%)",
  boxShadow: "0 0 12px rgba(0, 210, 170, 0.12), inset 0 0 8px rgba(0, 210, 170, 0.05)",
  flexShrink: 0,
};

function chip(active: boolean, color: string): React.CSSProperties {
  return {
    background: active ? `${color}20` : "transparent",
    color: active ? color : "rgba(228,237,245,0.35)",
    border: `1px solid ${active ? `${color}60` : "rgba(228,237,245,0.08)"}`,
    borderRadius: 3,
    padding: "3px 10px",
    fontSize: 11,
    fontWeight: active ? 700 : 400,
    cursor: "pointer",
    transition: "all 0.12s",
    whiteSpace: "nowrap",
  };
}
