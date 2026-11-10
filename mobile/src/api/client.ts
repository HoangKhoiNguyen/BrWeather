import type { StationSummary } from './types';

// Android emulator reaches the host machine at 10.0.2.2
const BASE_URL = 'http://10.0.2.2:8080/api/v1';

// true: build UI against sample data before the backend is ready. Must be false before every demo.
export const USE_MOCK = true;

const MOCK_STATIONS: StationSummary[] = [
  {
    id: 2161306,
    name: 'Minh Khai - Bắc Từ Liêm',
    lat: 21.07,
    lon: 105.76,
    latest: {
      pm25: 48.2,
      unit: 'µg/m³',
      measuredAt: '2026-11-10T03:00:00Z',
      source: 'OpenAQ',
      kind: 'observed',
      reliability: 'high',
      status: 'ok',
    },
  },
  {
    id: 6123215,
    name: 'Dragon',
    lat: 21.0,
    lon: 105.8,
    latest: {
      pm25: null,
      unit: 'µg/m³',
      measuredAt: '2026-11-09T20:00:00Z',
      source: 'OpenAQ',
      kind: 'observed',
      reliability: 'medium',
      status: 'stale',
    },
  },
];

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function getStations(): Promise<StationSummary[]> {
  if (USE_MOCK) {
    return MOCK_STATIONS;
  }
  return get<StationSummary[]>('/stations');
}
