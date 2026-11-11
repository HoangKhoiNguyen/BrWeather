import * as mock from './mock';
import type {
  AlertEvent,
  RecommendationRequest,
  RecommendationResult,
  StationDetail,
  StationSummary,
  Subscription,
  Weather,
} from './types';

// Android emulator reaches the host machine at 10.0.2.2
const BASE_URL = 'http://10.0.2.2:8080/api/v1';

// true: use sample data. Set to false once the backend serves the endpoints in docs/api-contract.md.
export const USE_MOCK = true;

// Placeholder until the app generates and stores its own anonymous id (F07a, F11)
const DEVICE_ID = '00000000-0000-0000-0000-000000000000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export const getStations = (): Promise<StationSummary[]> =>
  USE_MOCK ? Promise.resolve(mock.mockStations()) : get('/stations');

export const getStationDetail = (id: number): Promise<StationDetail> =>
  USE_MOCK ? Promise.resolve(mock.mockStationDetail(id)) : get(`/stations/${id}/detail`);

export const getWeather = (): Promise<Weather> =>
  USE_MOCK ? Promise.resolve(mock.mockWeather()) : get('/weather?lat=21.0285&lon=105.8542');

export const getRecommendations = (req: RecommendationRequest): Promise<RecommendationResult> =>
  USE_MOCK ? Promise.resolve(mock.mockRecommendations(req)) : post('/recommendations', req);

export const getSubscriptions = (): Promise<Subscription[]> =>
  USE_MOCK ? Promise.resolve(mock.mockSubscriptions()) : get(`/devices/${DEVICE_ID}/subscriptions`);

export const getAlerts = (): Promise<AlertEvent[]> =>
  USE_MOCK ? Promise.resolve(mock.mockAlerts()) : get(`/devices/${DEVICE_ID}/alerts`);
