import { useEffect } from "react";

interface Props {
  onClose: () => void;
}

export function ConceptOverlay({ onClose }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(e) => e.stopPropagation()}>
        <div style={accentBar} />

        <button onClick={onClose} style={closeBtnStyle}>✕</button>

        <div style={{ padding: "48px 52px 52px" }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 40 }}>
            <svg width="36" height="36" viewBox="0 0 32 32" fill="none">
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
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "0.12em" }}>
                <span style={{ color: "#00d2aa" }}>EARTH</span>
                <span style={{ color: "#e4edf5", marginLeft: 7 }}>TWIN</span>
              </div>
              <div style={{ fontSize: 10, color: "rgba(0,210,170,0.5)", letterSpacing: "0.14em", marginTop: 2 }}>
                PROBABILISTIC WORLD MODEL
              </div>
            </div>
          </div>

          {/* Core statement */}
          <p style={leadStyle}>
            Earth Twin is not a geopolitical prediction tool.
          </p>
          <p style={leadStyle}>
            It is a <span style={{ color: "#00d2aa" }}>copy of the world.</span>
          </p>

          <div style={dividerStyle} />

          {/* Philosophy */}
          <Section title="The Premise">
            Economic collapse, governance failure, destabilization of neighboring
            states, climate stress, food crises, refugee flows — countless factors
            intertwine, and when they cross a threshold, events move.
            <br /><br />
            Earth Twin observes all of these simultaneously and attempts to
            reproduce the current state of the world as faithfully as possible.
          </Section>

          <Section title="The Method">
            Data is continuously collected from 13+ real-time sources: seismic
            activity, weather, disease surveillance, food prices, democratic
            erosion, armed conflict events, wildfires, refugee movements, and more.
            <br /><br />
            Every six hours, an AI agent autonomously discovers and integrates new
            open data sources — expanding the model's coverage without human
            intervention.
          </Section>

          <Section title="The Model">
            Machine learning models trained on decades of historical data translate
            each country's observable state into a risk score: the estimated
            probability of conflict or coup within the next 12 months.
            <br /><br />
            The output is always a probability. Reproduction of the world is never
            complete — unobservable factors are countless. The number between 0
            and 1 is an estimate derived from known factors,{" "}
            <span style={{ color: "#00d2aa", fontStyle: "italic" }}>
              not an absolute prediction.
            </span>
          </Section>

          <Section title="The Goal">
            To capture as much of the world's complexity as possible — so that
            the risk embedded in the present can be read before it becomes the past.
          </Section>

          <div style={dividerStyle} />

          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 8 }}>
            <Stat value="150+" label="Countries tracked" />
            <Stat value="∞" label="Data streams active" />
            <Stat value="1 yr" label="Forecast horizon" />
          </div>

          <div style={{ marginTop: 36, fontSize: 10, color: "rgba(228,237,245,0.18)", letterSpacing: "0.06em", lineHeight: 1.8 }}>
            POWERED BY XGBOOST · CLAUDE · TIMESCALEDB · GDELT · UCDP · WORLD BANK · V-DEM · POWELL-THYNE · NASA · NOAA · WHO · FAO · OPEN-METEO
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ fontSize: 9, color: "#00d2aa", letterSpacing: "0.14em", marginBottom: 8, fontFamily: "monospace" }}>
        {title.toUpperCase()}
      </div>
      <p style={{ fontSize: 13, color: "rgba(228,237,245,0.65)", lineHeight: 1.85, margin: 0 }}>
        {children}
      </p>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div style={{ textAlign: "center", padding: "16px 8px", background: "rgba(0,210,170,0.04)", border: "1px solid rgba(0,210,170,0.1)", borderRadius: 6 }}>
      <div style={{ fontSize: 24, fontWeight: 800, color: "#00d2aa", fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 9, color: "rgba(228,237,245,0.35)", marginTop: 6, letterSpacing: "0.06em" }}>
        {label.toUpperCase()}
      </div>
    </div>
  );
}

const backdropStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 2000,
  background: "rgba(0, 0, 0, 0.75)",
  backdropFilter: "blur(8px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 24,
};

const panelStyle: React.CSSProperties = {
  position: "relative",
  maxWidth: 680,
  width: "100%",
  maxHeight: "90vh",
  overflowY: "auto",
  background: "rgba(8, 14, 22, 0.98)",
  border: "1px solid rgba(0, 210, 170, 0.18)",
  borderRadius: 8,
  boxShadow: "0 32px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(0,210,170,0.05)",
  animation: "panel-in 0.2s ease-out",
};

const accentBar: React.CSSProperties = {
  height: 2,
  background: "linear-gradient(90deg, #00d2aa, transparent 70%)",
  borderRadius: "8px 8px 0 0",
};

const closeBtnStyle: React.CSSProperties = {
  position: "absolute",
  top: 16,
  right: 18,
  background: "none",
  border: "none",
  color: "rgba(228,237,245,0.3)",
  cursor: "pointer",
  fontSize: 16,
  lineHeight: 1,
  padding: 4,
  zIndex: 1,
};

const leadStyle: React.CSSProperties = {
  fontSize: 26,
  fontWeight: 700,
  color: "#e4edf5",
  lineHeight: 1.4,
  margin: "0 0 6px",
  letterSpacing: "-0.01em",
};

const dividerStyle: React.CSSProperties = {
  height: 1,
  background: "rgba(228,237,245,0.06)",
  margin: "32px 0",
};
