// Sample data so the UI can be built before the backend is ready. Everything here is invented.
import type {
  AlertEvent,
  RecommendationRequest,
  RecommendationResult,
  SeriesPoint,
  StationDetail,
  StationSummary,
  Subscription,
  Weather,
  WeatherDay,
  WeatherHour,
} from './types';

const HOUR = 3600 * 1000;
const VN_OFFSET = 7 * HOUR;

function currentHour(): number {
  return Math.floor(Date.now() / HOUR) * HOUR;
}

function iso(t: number): string {
  return new Date(t).toISOString();
}

function vnHour(t: number): number {
  return new Date(t + VN_OFFSET).getUTCHours();
}

// PM2.5 peaks in the morning and late evening rush hours
function pm25At(t: number, base: number): number {
  const h = vnHour(t);
  const shape =
    1 +
    0.35 * Math.exp(-((h - 8) ** 2) / 6) +
    0.5 * Math.exp(-((h - 21) ** 2) / 8) -
    0.25 * Math.exp(-((h - 14) ** 2) / 10);
  const wobble = 1 + 0.08 * Math.sin(t / (5 * HOUR));
  return Math.round(base * shape * wobble * 10) / 10;
}

function rainAt(t: number): number {
  const h = vnHour(t);
  return Math.max(5, Math.round(55 * Math.exp(-((h - 17) ** 2) / 9)));
}

function temperatureAt(t: number): number {
  const h = vnHour(t);
  return Math.round((22 + 5 * Math.cos(((h - 14) * Math.PI) / 12)) * 10) / 10;
}

function codeAt(t: number): number {
  const rain = rainAt(t);
  if (rain > 45) {
    return 61;
  }
  if (rain > 25) {
    return 3;
  }
  return vnHour(t) >= 6 && vnHour(t) <= 17 ? 1 : 2;
}

const STATIONS: Array<{ id: number; name: string; lat: number; lon: number; km: number; base: number; rel: 'high' | 'medium' | 'low' }> = [
  { id: 2161292, name: 'Số 46 Lưu Quang Vũ', lat: 21.015, lon: 105.8, km: 1.2, base: 46, rel: 'high' },
  { id: 4946812, name: 'Công viên Nhân Chính', lat: 21.007, lon: 105.8, km: 2.1, base: 58, rel: 'high' },
  { id: 4946813, name: 'Số 1 Giải Phóng - Bạch Mai', lat: 21.0, lon: 105.84, km: 4.6, base: 63, rel: 'high' },
  { id: 2161306, name: 'Minh Khai - Bắc Từ Liêm', lat: 21.07, lon: 105.76, km: 7.3, base: 41, rel: 'medium' },
  { id: 6123215, name: 'Dragon', lat: 21.03, lon: 105.85, km: 5.5, base: 52, rel: 'medium' },
];

export function mockStations(): StationSummary[] {
  const now = currentHour();
  return STATIONS.map((s, i) => {
    // One stale and one missing station so those UI states are always visible
    const stale = i === 3;
    const missing = i === 4;
    const measured = stale ? now - 6 * HOUR : now;
    return {
      id: s.id,
      name: s.name,
      lat: s.lat,
      lon: s.lon,
      distanceKm: s.km,
      latest: {
        pm25: missing ? null : pm25At(measured, s.base),
        unit: 'µg/m³',
        measuredAt: missing ? null : iso(measured),
        source: 'OpenAQ',
        kind: 'observed',
        reliability: missing ? null : stale ? 'low' : s.rel,
        status: missing ? 'missing' : stale ? 'stale' : 'ok',
      },
    };
  });
}

export function mockStationDetail(id: number): StationDetail {
  const base = STATIONS.find(s => s.id === id)?.base ?? 50;
  const now = currentHour();
  const history: SeriesPoint[] = [];
  for (let k = 23; k >= 0; k--) {
    const t = now - k * HOUR;
    history.push({ time: iso(t), value: k === 9 || k === 10 ? null : pm25At(t, base) });
  }
  const forecast: SeriesPoint[] = [];
  for (let k = 1; k <= 24; k++) {
    const t = now + k * HOUR;
    forecast.push({ time: iso(t), value: pm25At(t, base * 1.05) });
  }
  return {
    history,
    forecast,
    forecastIssuedAt: iso(now),
    modelVersion: 'baseline-persistence (mẫu)',
    anomalies: [
      {
        id: 1,
        time: iso(now - 14 * HOUR),
        category: 'environment',
        description: 'PM2.5 tăng nhanh trong 3 giờ, trạm lân cận cũng tăng.',
      },
      {
        id: 2,
        time: iso(now - 9 * HOUR),
        category: 'data',
        description: 'Mất tín hiệu 2 giờ, không tính vào phân tích.',
      },
    ],
  };
}

export function mockWeather(): Weather {
  const now = currentHour();
  const hourly: WeatherHour[] = [];
  for (let k = 0; k < 24; k++) {
    const t = now + k * HOUR;
    hourly.push({
      time: iso(t),
      temperatureC: temperatureAt(t),
      precipitationProbPct: rainAt(t),
      weatherCode: codeAt(t),
    });
  }
  const codes = [1, 3, 61, 80, 2, 1, 3];
  const daily: WeatherDay[] = codes.map((code, i) => ({
    date: iso(now + i * 24 * HOUR),
    maxC: 27 - (i % 3),
    minC: 20 - (i % 2),
    precipitationMm: code >= 61 ? 4.5 + i : 0,
    weatherCode: code,
  }));
  return {
    fetchedAt: iso(now),
    source: 'Open-Meteo',
    current: {
      temperatureC: temperatureAt(now),
      apparentC: temperatureAt(now) + 1,
      humidityPct: 76,
      precipitationMm: 0,
      windKmh: 7.2,
      windDirectionDeg: 45,
      uvIndex: 4,
      weatherCode: codeAt(now),
    },
    hourly,
    daily,
  };
}

export function mockRecommendations(req: RecommendationRequest): RecommendationResult {
  // Candidates start on the hour tomorrow, inside the chosen window (Vietnam time)
  const tomorrow = Math.floor((Date.now() + VN_OFFSET) / (24 * HOUR) + 1) * 24 * HOUR - VN_OFFSET;
  const hours = Math.ceil(req.durationMinutes / 60);
  const candidates = [];
  for (let h = req.windowStartHour; h + hours <= req.windowEndHour; h++) {
    const start = tomorrow + h * HOUR;
    const span = Array.from({ length: hours }, (_, i) => start + i * HOUR);
    const pm25 = span.reduce((a, t) => a + pm25At(t, 50), 0) / hours;
    const rainPct = Math.max(...span.map(rainAt));
    const temperatureC = span.reduce((a, t) => a + temperatureAt(t), 0) / hours;
    const score = pm25 + 0.4 * rainPct + 2 * Math.abs(temperatureC - 24);
    candidates.push({ start, pm25, rainPct, temperatureC, score });
  }
  const options = candidates
    .sort((a, b) => a.score - b.score)
    .slice(0, 3)
    .map(c => ({
      start: iso(c.start),
      end: iso(c.start + req.durationMinutes * 60 * 1000),
      pm25: Math.round(c.pm25),
      rainPct: c.rainPct,
      temperatureC: Math.round(c.temperatureC),
      reason: `PM2.5 dự báo khoảng ${Math.round(c.pm25)} µg/m³, khả năng mưa ${c.rainPct}%, ${Math.round(c.temperatureC)}°C.`,
    }));
  return {
    options,
    explanation: options.length
      ? 'Khung giờ đầu tiên có PM2.5 dự báo thấp nhất trong khoảng bạn chọn và ít khả năng mưa. Đây là lựa chọn tương đối, không phải bảo đảm an toàn sức khỏe.'
      : 'Khoảng giờ đã chọn ngắn hơn thời lượng hoạt động.',
    usedFallback: true,
  };
}

export function mockSubscriptions(): Subscription[] {
  return [
    { id: 1, label: 'Nhà - Cầu Giấy', pm25Threshold: 50, useForecast: true, enabled: true },
    { id: 2, label: 'Công ty - Thanh Xuân', pm25Threshold: 80, useForecast: false, enabled: false },
  ];
}

export function mockAlerts(): AlertEvent[] {
  const now = currentHour();
  return [
    {
      id: 1,
      time: iso(now - 3 * HOUR),
      label: 'Nhà - Cầu Giấy',
      value: 64,
      reason: 'PM2.5 vượt ngưỡng 50 µg/m³ tại trạm Số 46 Lưu Quang Vũ.',
    },
    {
      id: 2,
      time: iso(now - 20 * HOUR),
      label: 'Nhà - Cầu Giấy',
      value: 57,
      reason: 'Dự báo PM2.5 vượt ngưỡng 50 µg/m³ lúc 21:00.',
    },
  ];
}
