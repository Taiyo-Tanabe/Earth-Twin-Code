import { useState } from "react";
import { RiskMap } from "./components/RiskMap";
import { CountryPanel } from "./components/CountryPanel";
import { BottomSheet } from "./components/BottomSheet";
import { Toolbar } from "./components/Toolbar";
import { MobileToolbar } from "./components/MobileToolbar";
import { SearchBar } from "./components/SearchBar";
import { TopRiskList } from "./components/TopRiskList";
import { ConceptOverlay } from "./components/ConceptOverlay";
import { useRiskData } from "./hooks/useRiskData";
import { useIsMobile } from "./hooks/useIsMobile";
import { RiskLayer } from "./types";
import "./app.css";

export default function App() {
  const [riskLayer, setRiskLayer] = useState<RiskLayer>("conflict");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [showConcept, setShowConcept] = useState(false);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  const isMobile = useIsMobile();
  const { countries, updatedAt, dataYear, predictionFrom, predictionTo, availableYears, conflictDefinition, regimeChangeDefinition, loading, getCountry } = useRiskData(selectedYear);

  const handleYearChange = (y: number) => {
    setSelectedYear(y);
    setSelectedCode(null);
  };
  const selectedCountry = selectedCode ? getCountry(selectedCode) : null;

  const toolbarHeight = isMobile ? 52 : 56;

  const handleSelect = (code: string) =>
    setSelectedCode((prev) => (prev === code ? null : code));

  const handleClose = () => setSelectedCode(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {isMobile ? (
        <MobileToolbar
          riskLayer={riskLayer}
          predictionFrom={predictionFrom}
          predictionTo={predictionTo}
          availableYears={availableYears}
          selectedYear={selectedYear ?? availableYears[availableYears.length - 1]}
          onLayerChange={setRiskLayer}
          onYearChange={handleYearChange}
          onConceptOpen={() => setShowConcept(true)}
        />
      ) : (
        <Toolbar
          riskLayer={riskLayer}
          updatedAt={updatedAt}
          predictionFrom={predictionFrom}
          predictionTo={predictionTo}
          availableYears={availableYears}
          selectedYear={selectedYear ?? availableYears[availableYears.length - 1]}
          onLayerChange={setRiskLayer}
          onYearChange={handleYearChange}
          onConceptOpen={() => setShowConcept(true)}
        />
      )}

      <div style={{ position: "relative", flex: 1, overflow: "hidden", marginTop: toolbarHeight }}>

        {/* Vignette overlay */}
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 5,
          background: "radial-gradient(ellipse at center, transparent 45%, rgba(6,10,18,0.65) 100%)",
        }} />

        {/* Scan line */}
        <div style={{
          position: "absolute", left: 0, right: 0, height: 1, zIndex: 6, pointerEvents: "none",
          background: "linear-gradient(90deg, transparent, rgba(0,210,170,0.18) 30%, rgba(0,210,170,0.18) 70%, transparent)",
          animation: "scan-line 10s linear infinite",
        }} />

        {loading && (
          <div style={loadingStyle}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
              <div style={{ position: "relative", width: 48, height: 48 }}>
                <div style={{ position: "absolute", inset: 0, border: "1px solid rgba(0,210,170,0.15)", borderRadius: "50%" }} />
                <div style={{ position: "absolute", inset: 0, border: "2px solid transparent", borderTopColor: "#00d2aa", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
                <div style={{ position: "absolute", inset: 8, border: "1px solid rgba(0,210,170,0.08)", borderRadius: "50%" }} />
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ color: "#00d2aa", fontSize: 11, letterSpacing: "0.14em", fontFamily: "monospace" }}>
                  EARTH TWIN · INITIALIZING
                </div>
                <div style={{ color: "rgba(0,210,170,0.35)", fontSize: 9, letterSpacing: "0.1em", fontFamily: "monospace", marginTop: 6 }}>
                  LOADING 150+ COUNTRIES · RISK MODEL ACTIVE
                </div>
              </div>
            </div>
          </div>
        )}

        <RiskMap
          countries={countries}
          selectedCode={selectedCode}
          riskLayer={riskLayer}
          onCountryClick={handleSelect}
        />

        {!loading && (
          <SearchBar
            countries={countries}
            onSelect={handleSelect}
            isMobile={isMobile}
          />
        )}

        {!isMobile && !loading && countries.length > 0 && (
          <TopRiskList
            countries={countries}
            riskLayer={riskLayer}
            selectedCode={selectedCode}
            onSelect={handleSelect}
          />
        )}

        {!isMobile && (
          <div style={panelOverlayStyle}>
            <CountryPanel
              country={selectedCountry}
              dataYear={dataYear}
              predictionFrom={predictionFrom}
              predictionTo={predictionTo}
              conflictDefinition={conflictDefinition}
              regimeChangeDefinition={regimeChangeDefinition}
              riskLayer={riskLayer}
              onClose={handleClose}
            />
          </div>
        )}

        {!isMobile && !selectedCode && !loading && (
          <div style={hintStyle}>
            <span style={{ color: "rgba(0,210,170,0.5)", marginRight: 6 }}>◈</span>
            SELECT A COUNTRY · AI RISK ANALYSIS
          </div>
        )}
      </div>

      {isMobile && (
        <BottomSheet
          country={selectedCountry}
          dataYear={dataYear}
          predictionFrom={predictionFrom}
          predictionTo={predictionTo}
          conflictDefinition={conflictDefinition}
          regimeChangeDefinition={regimeChangeDefinition}
          onClose={handleClose}
        />
      )}

      {showConcept && <ConceptOverlay onClose={() => setShowConcept(false)} />}
    </div>
  );
}

const panelOverlayStyle: React.CSSProperties = {
  position: "absolute",
  top: 0, right: 0, bottom: 0,
  zIndex: 800,
  pointerEvents: "none",
  display: "flex",
  alignItems: "stretch",
  maxWidth: "calc(100vw - 240px)",  // always leaves at least 240px for the map
};

const loadingStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "rgba(8, 16, 26, 0.85)",
  zIndex: 999,
};

const hintStyle: React.CSSProperties = {
  position: "absolute",
  bottom: 24,
  left: "50%",
  transform: "translateX(-50%)",
  zIndex: 700,
  background: "rgba(6, 10, 18, 0.92)",
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(0, 210, 170, 0.15)",
  borderRadius: 4,
  padding: "6px 16px",
  fontSize: 10,
  fontFamily: "monospace",
  letterSpacing: "0.1em",
  color: "rgba(228,237,245,0.3)",
  pointerEvents: "none",
  whiteSpace: "nowrap",
};
