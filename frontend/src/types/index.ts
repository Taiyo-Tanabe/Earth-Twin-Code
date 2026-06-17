export interface CountryRisk {
  country_code: string;
  country_name: string;
  conflict_probability_1y: number;
  regime_change_probability_1y: number;
  risk_score: number;
  risk_trend: "up" | "down" | "stable";
  top_features: string[];
  gdp_growth: number | null;
  inflation: number | null;
  polity_score: number | null;
  structural_risk?: number | null;
}

export interface GlobalMapData {
  countries: CountryRisk[];
  updated_at: string;
  data_year?: number | null;
  prediction_from?: string | null;
  prediction_to?: string | null;
  conflict_definition?: string;
  regime_change_definition?: string;
}

export type RiskLayer = "conflict" | "regime_change";
