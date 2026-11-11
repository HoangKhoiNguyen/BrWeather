// Visual language: a full-screen sky that follows the current weather and time of day,
// with frosted "glass" cards on top. All text is light so it reads on every sky.

export type SkyKind = 'clear-day' | 'cloudy' | 'rain' | 'sunset' | 'night';

export const skies: Record<SkyKind, string> = {
  'clear-day': 'linear-gradient(180deg, #1F6FD1 0%, #3B9BE8 45%, #7CC4F2 100%)',
  cloudy: 'linear-gradient(180deg, #4A6280 0%, #6F87A3 50%, #9DB0C4 100%)',
  rain: 'linear-gradient(180deg, #1E2B40 0%, #34475F 50%, #5B7189 100%)',
  sunset: 'linear-gradient(180deg, #2B2F66 0%, #8A4E86 50%, #E8875F 100%)',
  night: 'linear-gradient(180deg, #070F24 0%, #15254A 55%, #2E4377 100%)',
};

export const text = {
  primary: '#FFFFFF',
  secondary: 'rgba(255,255,255,0.80)',
  faint: 'rgba(255,255,255,0.58)',
  dark: '#0B1530',
};

export const glass = {
  bg: 'rgba(10,24,52,0.28)',
  strong: 'rgba(8,18,40,0.46)',
  border: 'rgba(255,255,255,0.18)',
  highlight: 'rgba(255,255,255,0.10)',
};

export const accent = '#8FD3FF';

export const pmColors = {
  good: '#4ADE80',
  moderate: '#FACC15',
  high: '#FB923C',
  veryHigh: '#F87171',
  none: '#CBD5E1',
};

// PM2.5 colour ramp for gauges (0 → 150 µg/m³). UI bands, not an official AQI.
// Stops sit at the band edges on a linear 0–150 scale: 25 → 17%, 50 → 33%, 80 → 53%
export const pmRamp =
  'linear-gradient(90deg, #4ADE80 0%, #4ADE80 10%, #FACC15 22%, #FB923C 38%, #F87171 58%, #C084FC 100%)';
export const uvRamp = 'linear-gradient(90deg, #4ADE80 0%, #FACC15 30%, #FB923C 55%, #F87171 78%, #C084FC 100%)';
export const tempRamp = 'linear-gradient(90deg, #7DD3FC 0%, #FDE68A 55%, #FB923C 100%)';

export const PM_SCALE_MAX = 150;

export function pm25Level(v: number | null): { label: string; color: string; advice: string } {
  if (v === null) {
    return { label: 'Không có dữ liệu', color: pmColors.none, advice: 'Chưa có số đo mới tại trạm này.' };
  }
  if (v <= 25) {
    return { label: 'Tốt', color: pmColors.good, advice: 'Phù hợp cho mọi hoạt động ngoài trời.' };
  }
  if (v <= 50) {
    return {
      label: 'Trung bình',
      color: pmColors.moderate,
      advice: 'Người nhạy cảm nên giảm vận động mạnh ngoài trời kéo dài.',
    };
  }
  if (v <= 80) {
    return { label: 'Kém', color: pmColors.high, advice: 'Nên hạn chế ra ngoài lâu, đeo khẩu trang khi di chuyển.' };
  }
  return { label: 'Xấu', color: pmColors.veryHigh, advice: 'Hạn chế ra ngoài, ưu tiên hoạt động trong nhà.' };
}

const VN_OFFSET = 7 * 3600 * 1000;

export function vnHourOf(iso: string): number {
  return new Date(new Date(iso).getTime() + VN_OFFSET).getUTCHours();
}

export function skyFor(code: number | null, iso: string): SkyKind {
  const h = vnHourOf(iso);
  if (h < 5 || h >= 19) {
    return 'night';
  }
  if (code !== null && code >= 51) {
    return 'rain';
  }
  if (h >= 17) {
    return 'sunset';
  }
  if (code === 3 || (code !== null && code >= 45 && code <= 48)) {
    return 'cloudy';
  }
  return 'clear-day';
}
