// Mirrors docs/api-contract.md. Keep both in sync when the API changes.

export type DataKind = 'observed' | 'modelled' | 'forecast';
export type Reliability = 'high' | 'medium' | 'low';
export type DataStatus = 'ok' | 'stale' | 'missing';

export interface StationSummary {
  id: number;
  name: string;
  lat: number;
  lon: number;
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

export interface WeatherHour {
  validTime: string;
  temperatureC: number | null;
  precipitationProbPct: number | null;
  weatherCode: number | null;
}

export interface Recommendation {
  start: string;
  end: string;
  score: number;
  reasons: string[];
}
