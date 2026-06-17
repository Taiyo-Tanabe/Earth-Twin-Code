import { useState } from "react";
import { RiskMap } from "./components/RiskMap";
import { CountryPanel } from "./components/CountryPanel";
import { BottomSheet } from "./components/BottomSheet";
import { Toolbar } from "./components/Toolbar";
import { MobileToolbar } from "./components/MobileToolbar";
import { SearchBar } from "./components/SearchBar";
import { TopRiskList } from "./components/TopRiskList";
import { useRiskData } from "./hooks/useRiskData";
import { useIsMobile } from "./hooks/useIsMobile";
import { RiskLayer } from "./types";
import "./app.css";

export default function App() {
  const [riskLayer, setRiskLayer] = useState<RiskLayer>("conflict");
  const [selectedCode, setSelectedCode] = useState<string | null>(null);

  const isMobile = useIsMobile();
  const { countries, updatedAt, dataYear, predictionFrom, predictionTo, conflictDefinition, regimeChangeDefinition, loading, getCountry } = useRiskData();
  const selectedCountry = selectedCode ? getCountry(selectedCode) : null;

  const toolbarHeight = isMobile ? 66 : 56;

  const handleSelect = (code: string) =>
    setSelectedCode((prev) => (prev === code ? null : code));

  const handleClose = () => setSelectedCode(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {isMobile ? (
        <MobileToolbar
          riskLayer={riskLayer}
          onLayerChange={setRiskLayer}
        />
      ) : (
        <Toolbar
          riskLayer={riskLayer}
          updatedAt={updatedAt}
          predictionFrom={predictionFrom}
          predictionTo={predictionTo}
          onLayerChange={setRiskLayer}
        />
      )}

      <div style={{ position: "relative", flex: 1, overflow: "hidden", marginTop: toolbarHeight }}>
        {loading && (
          <div style={loadingStyle}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
              <div style={{ width: 32, height: 32, border: "2px solid rgba(0,210,170,0.15)", borderTopColor: "#00d2aa", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
              <div style={{ color: "#00d2aa", fontSize: 12, letterSpacing: "0.08em", fontFamily: "monospace" }}>
                LOADING RISK DATA...
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
            国をクリックしてリスク詳細を表示
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
  background: "rgba(8, 16, 26, 0.88)",
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(0, 210, 170, 0.12)",
  borderRadius: 99,
  padding: "7px 18px",
  fontSize: 12,
  color: "rgba(228,237,245,0.35)",
  pointerEvents: "none",
  whiteSpace: "nowrap",
};
