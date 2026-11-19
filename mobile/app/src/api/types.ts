// Mirrors docs/api-contract.md. Keep both in sync when the API changes.

export type DataKind = 'observed' | 'modelled' | 'forecast';
export type Reliability = 'high' | 'medium' | 'low';
export type DataStatus = 'ok' | 'stale' | 'missing';

export interface StationSummary {
  id: number;
  name: string;
  lat: number;
  lon: number;
  distanceKm: number;
  latest: {
    pm25: number | null;
    unit: string;
    measuredAt: string | null; // ISO 8601 UTC
    source: string;
    kind: DataKind;
    reliability: Reliability | null;
    status: DataStatus;
  };
}

export interface SeriesPoint {
  time: string;
  value: number | null;
}

export interface Anomaly {
  id: number;
  time: string;
  category: 'data' | 'environment' | 'needs_review';
  description: string;
}

export interface StationDetail {
  history: SeriesPoint[];
  // null when the station does not have enough history for a forecast (T3.1-5)
  forecast: SeriesPoint[] | null;
  forecastIssuedAt: string | null;
  modelVersion: string | null;
  anomalies: Anomaly[];
}

export interface WeatherHour {
  time: string;
  temperatureC: number | null;
  precipitationProbPct: number | null;
  weatherCode: number | null;
}

export interface WeatherDay {
  date: string;
  maxC: number | null;
  minC: number | null;
  precipitationMm: number | null;
  weatherCode: number | null;
}

export interface Weather {
  fetchedAt: string;
  source: string;
  // Open-Meteo values come from a weather model, never from a station measurement
  kind: DataKind;
  current: {
    temperatureC: number | null;
    apparentC: number | null;
    humidityPct: number | null;
    precipitationMm: number | null;
    windKmh: number | null;
    windDirectionDeg: number | null;
    uvIndex: number | null;
    weatherCode: number | null;
  };
  hourly: WeatherHour[];
  daily: WeatherDay[];
}

export interface RecommendationRequest {
  durationMinutes: number;
  windowStartHour: number;
  windowEndHour: number;
}

export interface Recommendation {
  start: string;
  end: string;
  pm25: number;
  rainPct: number;
  temperatureC: number;
  reason: string;
}

export interface RecommendationResult {
  options: Recommendation[];
  explanation: string;
  usedFallback: boolean;
}

export interface Subscription {
  id: number;
  label: string;
  pm25Threshold: number;
  useForecast: boolean;
  enabled: boolean;
}

export interface AlertEvent {
  id: number;
  time: string;
  label: string;
  value: number;
  reason: string;
}
