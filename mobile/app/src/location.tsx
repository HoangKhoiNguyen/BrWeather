import React, { createContext, useContext, useMemo, useState } from 'react';

// The place the user is looking at: from GPS, picked by hand, or the default city centre (F11, T1.1-4)
export interface Place {
  label: string;
  lat: number;
  lon: number;
  source: 'gps' | 'manual' | 'default';
}

export const DEFAULT_PLACE: Place = { label: 'Trung tâm Hà Nội', lat: 21.0285, lon: 105.8542, source: 'default' };

// Approximate district centres for picking a place by hand when location permission is refused
export const DISTRICTS: Place[] = [
  { label: 'Hoàn Kiếm', lat: 21.0285, lon: 105.8542 },
  { label: 'Ba Đình', lat: 21.0359, lon: 105.8142 },
  { label: 'Đống Đa', lat: 21.0128, lon: 105.8272 },
  { label: 'Hai Bà Trưng', lat: 21.006, lon: 105.8573 },
  { label: 'Cầu Giấy', lat: 21.0362, lon: 105.7906 },
  { label: 'Thanh Xuân', lat: 20.9938, lon: 105.8148 },
  { label: 'Tây Hồ', lat: 21.068, lon: 105.8188 },
  { label: 'Hoàng Mai', lat: 20.9746, lon: 105.8633 },
  { label: 'Long Biên', lat: 21.0393, lon: 105.8851 },
  { label: 'Nam Từ Liêm', lat: 21.0123, lon: 105.7653 },
  { label: 'Bắc Từ Liêm', lat: 21.0707, lon: 105.7617 },
  { label: 'Hà Đông', lat: 20.9714, lon: 105.7788 },
  { label: 'Đông Anh', lat: 21.1361, lon: 105.8495 },
  { label: 'Gia Lâm', lat: 21.0285, lon: 105.9453 },
  { label: 'Sóc Sơn', lat: 21.2563, lon: 105.8487 },
].map(d => ({ ...d, source: 'manual' as const }));

/** Great-circle distance in km. */
export function distanceKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(bLat - aLat);
  const dLon = rad(bLon - aLon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(aLat)) * Math.cos(rad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

const LocationContext = createContext<{ place: Place; setPlace: (p: Place) => void }>({
  place: DEFAULT_PLACE,
  setPlace: () => {},
});

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const [place, setPlace] = useState<Place>(DEFAULT_PLACE);
  const value = useMemo(() => ({ place, setPlace }), [place]);
  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

export function useLocation() {
  return useContext(LocationContext);
}
