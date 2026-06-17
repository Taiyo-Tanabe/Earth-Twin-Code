import { useState, useEffect } from "react";
import { CountryRisk, RiskLayer } from "../types";
import { MOCK_COUNTRIES, MOCK_UPDATED_AT } from "../data/mockData";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export function useRiskData(selectedYear: number | null = null) {
  const [countries, setCountries] = useState<CountryRisk[]>([]);
  const [updatedAt, setUpdatedAt] = useState("");
  const [dataYear, setDataYear] = useState<number | null>(null);
  const [predictionFrom, setPredictionFrom] = useState<string | null>(null);
  const [predictionTo, setPredictionTo] = useState<string | null>(null);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [conflictDefinition, setConflictDefinition] = useState<string>("");
  const [regimeChangeDefinition, setRegimeChangeDefinition] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const url = selectedYear
      ? `${API_BASE}/global_map?year=${selectedYear}`
      : `${API_BASE}/global_map`;
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        setCountries(data.countries as CountryRisk[]);
        setUpdatedAt(data.updated_at ?? "");
        setDataYear(data.data_year ?? null);
        setPredictionFrom(data.prediction_from ?? null);
        setPredictionTo(data.prediction_to ?? null);
        setAvailableYears(data.available_years ?? []);
        setConflictDefinition(data.conflict_definition ?? "");
        setRegimeChangeDefinition(data.regime_change_definition ?? "");
      })
      .catch(() => {
        setCountries(MOCK_COUNTRIES);
        setUpdatedAt(MOCK_UPDATED_AT);
        setDataYear(null);
        setPredictionFrom(null);
        setPredictionTo(null);
        setAvailableYears([]);
      })
      .finally(() => setLoading(false));
  }, [selectedYear]);

  const getCountry = (code: string) =>
    countries.find((c) => c.country_code === code) ?? null;

  return {
    countries, updatedAt, dataYear, predictionFrom, predictionTo,
    availableYears, conflictDefinition, regimeChangeDefinition, loading, getCountry,
  };
}

export function sortByLayer(countries: CountryRisk[], layer: RiskLayer) {
  return [...countries].sort((a, b) => {
    const av = layer === "regime_change" ? a.regime_change_probability_1y : a.conflict_probability_1y;
    const bv = layer === "regime_change" ? b.regime_change_probability_1y : b.conflict_probability_1y;
    return bv - av;
  });
}
