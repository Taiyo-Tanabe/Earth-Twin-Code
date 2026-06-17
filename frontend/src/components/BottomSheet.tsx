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

function formatProb(value: number): string {
  if (value < 0.001) return "< 0.1%";
  if (value < 0.01) return `${(value * 100).toFixed(2)}%`;
  return `${(value * 100).toFixed(1)}%`;
}

function ProbRow({ label, value, color, definition }: { label: string; value: number; color: string; definition?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5, alignItems: "flex-start" }}>
        <div>
          <span style={{ fontSize: 12, color: "rgba(228,237,245,0.45)" }}>{label}</span>
          {definition && (
            <div style={{ fontSize: 9, color: "rgba(228,237,245,0.28)", marginTop: 2, lineHeight: 1.4, maxWidth: 200 }}>
              {definition}
            </div>
          )}
        </div>
        <span style={{ fontSize: 14, fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace", flexShrink: 0, marginLeft: 8 }}>
          {formatProb(value)}
        </span>
      </div>
      <div style={{ height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${value * 100}%`, background: color, borderRadius: 2, transition: "width 0.4s ease", opacity: 0.85 }} />
      </div>
    </div>
  );
}

export function BottomSheet({ country, dataYear, predictionFrom, predictionTo, conflictDefinition, regimeChangeDefinition, onClose }: Props) {
  const isOpen = country !== null;

  return (
    <>
      {isOpen && (
        <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 900, background: "rgba(0,0,0,0.4)" }} />
      )}

      <div style={{
        position: "fixed",
        left: 0, right: 0, bottom: 0,
        zIndex: 950,
        background: "rgba(8, 16, 26, 0.98)",
        backdropFilter: "blur(20px)",
        borderTop: "1px solid rgba(0, 210, 170, 0.15)",
        borderRadius: "12px 12px 0 0",
        boxShadow: "0 -8px 40px rgba(0,0,0,0.6)",
        transform: isOpen ? "translateY(0)" : "translateY(100%)",
        transition: "transform 0.3s cubic-bezier(0.32, 0.72, 0, 1)",
        maxHeight: "72vh",
        overflowY: "auto",
        paddingBottom: "env(safe-area-inset-bottom, 16px)",
      }}>
        {isOpen && country && (
          <div style={{ height: 2, background: `linear-gradient(90deg, ${riskColor(country.risk_score)}, transparent)` }} />
        )}

        <div style={{ display: "flex", justifyContent: "center", padding: "10px 0 4px" }}>
          <div style={{ width: 32, height: 3, borderRadius: 2, background: "rgba(228,237,245,0.12)" }} />
        </div>

        {country && (
          <div style={{ padding: "8px 20px 20px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 10, color: "rgba(228,237,245,0.3)", letterSpacing: "0.1em", fontFamily: "monospace" }}>{country.country_code}</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "#e4edf5", marginTop: 2 }}>{country.country_name}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: riskColor(country.risk_score), fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>
                  {country.risk_score < 0.001 ? "< 0.1" : country.risk_score < 0.01 ? (country.risk_score * 100).toFixed(2) : (country.risk_score * 100).toFixed(1)}<span style={{ fontSize: 14, fontWeight: 400, color: "rgba(228,237,245,0.3)" }}>%</span>
                </div>
                <div style={{ fontSize: 9, color: "rgba(228,237,245,0.3)", marginTop: 3 }}>
                  {predictionFrom && predictionTo ? `${predictionFrom} – ${predictionTo}` : "1-Year Forecast"}
                </div>
              </div>
            </div>

            <ProbRow label="Conflict Risk" value={country.conflict_probability_1y} color="#ff4466" definition={conflictDefinition} />
            <ProbRow label="Coup Risk" value={country.regime_change_probability_1y} color="#a855f7" definition={regimeChangeDefinition} />


            <div style={{ fontSize: 9, color: "rgba(228,237,245,0.3)", textTransform: "uppercase", marginBottom: 8 }}>KEY RISK FACTORS</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
              {country.top_features.map((f, i) => (
                <span key={i} style={{ fontSize: 10, color: "rgba(228,237,245,0.5)", background: "rgba(228,237,245,0.04)", border: "1px solid rgba(228,237,245,0.06)", borderRadius: 3, padding: "4px 9px", fontFamily: "monospace" }}>
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
