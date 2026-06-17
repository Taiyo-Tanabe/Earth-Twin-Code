import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap, ZoomControl } from "react-leaflet";
import L from "leaflet";
import { CountryRisk, RiskLayer } from "../types";

interface Props {
  countries: CountryRisk[];
  selectedCode: string | null;
  riskLayer: RiskLayer;
  onCountryClick: (code: string) => void;
}

function getRiskValue(country: CountryRisk, layer: RiskLayer): number {
  if (layer === "regime_change") return country.regime_change_probability_1y;
  if (layer === "overall") return country.risk_score;
  return country.conflict_probability_1y;
}

function riskToColor(value: number): string {
  if (value >= 0.8) return "#ff4466";
  if (value >= 0.6) return "#ff9430";
  if (value >= 0.4) return "#ffd440";
  if (value >= 0.2) return "#aaff44";
  return "#00d2aa";
}

function formatPct(value: number): string {
  if (value < 0.0001) return "< 0.01%";
  if (value < 0.001)  return `${(value * 100).toFixed(3)}%`;
  if (value < 0.01)   return `${(value * 100).toFixed(2)}%`;
  if (value < 0.1)    return `${(value * 100).toFixed(1)}%`;
  return `${(value * 100).toFixed(0)}%`;
}

function layerLabel(layer: RiskLayer): string {
  if (layer === "regime_change") return "Coup Risk";
  if (layer === "overall") return "Overall Risk";
  return "Conflict Risk";
}

function GeoJSONLayer({ countries, selectedCode, riskLayer, onCountryClick }: Props) {
  const map = useMap();
  const layerRef = useRef<L.GeoJSON | null>(null);

  useEffect(() => {
    if (countries.length === 0) return;

    const riskMap = new Map(countries.map((c) => [c.country_code, c]));

    fetch("/countries.geojson")
      .then((r) => r.json())
      .then((geoData) => {
        if (layerRef.current) {
          map.removeLayer(layerRef.current);
        }

        const layer = L.geoJSON(geoData, {
          style: (feature) => {
            const raw = feature?.properties?.ISO_A3;
            const code = (raw === "-99" || !raw) ? feature?.properties?.ISO_A3_EH : raw;
            const country = riskMap.get(code);
            const value = country ? getRiskValue(country, riskLayer) : -1;
            const isSelected = code === selectedCode;

            return {
              fillColor: value >= 0 ? riskToColor(value) : "#1a2035",
              fillOpacity: value >= 0 ? 0.75 : 0.3,
              color: isSelected ? "#ffffff" : "#2d3a4a",
              weight: isSelected ? 2.5 : 0.8,
            };
          },
          onEachFeature: (feature, featureLayer) => {
            const raw = feature?.properties?.ISO_A3;
            const code = (raw === "-99" || !raw)
              ? feature?.properties?.ISO_A3_EH
              : raw;
            if (!code || code === "-99") return;

            const country = riskMap.get(code);

            featureLayer.on("click", () => onCountryClick(code));
            featureLayer.on("mouseover", (e) => {
              (e.target as L.Path).setStyle({ fillOpacity: 1, weight: 2 });
            });
            featureLayer.on("mouseout", (e) => {
              const isSelected = code === selectedCode;
              (e.target as L.Path).setStyle({
                fillOpacity: country ? 0.75 : 0.3,
                weight: isSelected ? 2.5 : 0.8,
              });
            });

            const name = feature?.properties?.NAME ?? code;
            if (country) {
              const value = getRiskValue(country, riskLayer);
              const label = layerLabel(riskLayer);
              const pct = formatPct(value);
              featureLayer.bindTooltip(
                `<div style="font-size:12px;font-weight:600">${country.country_name}</div>
                 <div style="color:${riskToColor(value)};font-size:13px">${label}: ${pct}</div>`,
                { sticky: true, className: "earth-twin-tooltip" }
              );
            } else {
              featureLayer.bindTooltip(
                `<div style="font-size:12px;font-weight:600">${name}</div>
                 <div style="color:#546e7a;font-size:12px">No data</div>`,
                { sticky: true, className: "earth-twin-tooltip" }
              );
            }
          },
        });

        layer.addTo(map);
        layerRef.current = layer;
      });

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }
    };
  }, [countries, selectedCode, riskLayer, map, onCountryClick]);

  return null;
}

export function RiskMap({ countries, selectedCode, riskLayer, onCountryClick }: Props) {
  const isMobile = window.innerWidth < 768;

  return (
    <MapContainer
      center={[20, 0]}
      zoom={isMobile ? 1 : 2}
      minZoom={1}
      maxZoom={6}
      style={{ height: "100%", width: "100%", background: "#06101a" }}
      zoomControl={false}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
      />
      <ZoomControl position={isMobile ? "bottomleft" : "topleft"} />
      <GeoJSONLayer
        countries={countries}
        selectedCode={selectedCode}
        riskLayer={riskLayer}
        onCountryClick={onCountryClick}
      />
    </MapContainer>
  );
}
