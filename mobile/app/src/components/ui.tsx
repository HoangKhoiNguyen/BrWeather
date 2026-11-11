import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { ViewStyle } from 'react-native';

import { USE_MOCK } from '../api/client';
import type { Reliability, SeriesPoint } from '../api/types';

export const colors = {
  bg: '#EEF2F3',
  card: '#FFFFFF',
  text: '#16232A',
  muted: '#56666E',
  line: '#D3DCDF',
  accent: '#1D6A86',
  accentSoft: '#D6E8EF',
  good: '#2FA34F',
  moderate: '#C99F0A',
  high: '#E07A12',
  veryHigh: '#D43A2C',
  none: '#9AA6AB',
};

// Display bands for PM2.5 (µg/m³). These are UI colours, not an official AQI.
export function pm25Level(v: number | null): { label: string; color: string } {
  if (v === null) {
    return { label: 'Không có dữ liệu', color: colors.none };
  }
  if (v <= 25) {
    return { label: 'Thấp', color: colors.good };
  }
  if (v <= 50) {
    return { label: 'Trung bình', color: colors.moderate };
  }
  if (v <= 80) {
    return { label: 'Cao', color: colors.high };
  }
  return { label: 'Rất cao', color: colors.veryHigh };
}

const VN_OFFSET = 7 * 3600 * 1000;
const pad = (n: number) => String(n).padStart(2, '0');

// Data is stored in UTC and always shown in Vietnam time, whatever the device clock says
export function vnTime(iso: string): string {
  const d = new Date(new Date(iso).getTime() + VN_OFFSET);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

export function vnDay(iso: string): string {
  const d = new Date(new Date(iso).getTime() + VN_OFFSET);
  const names = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];
  return `${names[d.getUTCDay()]} ${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}`;
}

export function weatherInfo(code: number | null): { icon: string; label: string } {
  if (code === null) {
    return { icon: '–', label: 'Không rõ' };
  }
  if (code <= 1) {
    return { icon: '☀️', label: 'Quang mây' };
  }
  if (code === 2) {
    return { icon: '⛅', label: 'Mây rải rác' };
  }
  if (code === 3) {
    return { icon: '☁️', label: 'Nhiều mây' };
  }
  if (code >= 45 && code <= 48) {
    return { icon: '🌫️', label: 'Sương mù' };
  }
  if (code >= 95) {
    return { icon: '⛈️', label: 'Giông' };
  }
  return { icon: '🌧️', label: 'Mưa' };
}

export function fmt(v: number | null, unit = ''): string {
  return v === null ? '–' : `${v}${unit}`;
}

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function ScreenTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.titleBox}>
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

export function SampleBanner() {
  if (!USE_MOCK) {
    return null;
  }
  return (
    <View style={styles.banner}>
      <Text style={styles.bannerText}>Bản khung: đang hiển thị dữ liệu mẫu</Text>
    </View>
  );
}

export function SectionTitle({ children }: { children: string }) {
  return <Text style={styles.section}>{children}</Text>;
}

export function Pill({ label, color }: { label: string; color: string }) {
  return (
    <View style={[styles.pill, { backgroundColor: color }]}>
      <Text style={styles.pillText}>{label}</Text>
    </View>
  );
}

const RELIABILITY: Record<Reliability, { label: string; color: string }> = {
  high: { label: 'Tin cậy cao', color: colors.good },
  medium: { label: 'Tin cậy TB', color: colors.moderate },
  low: { label: 'Tin cậy thấp', color: colors.veryHigh },
};

export function ReliabilityPill({ level }: { level: Reliability | null }) {
  if (!level) {
    return null;
  }
  return <Pill label={RELIABILITY[level].label} color={RELIABILITY[level].color} />;
}

export function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.chip, selected && styles.chipOn]}>
      <Text style={[styles.chipText, selected && styles.chipTextOn]}>{label}</Text>
    </Pressable>
  );
}

// A missing hour leaves an empty slot: the chart must never imply data that does not exist
export function BarChart({ data, height = 110 }: { data: SeriesPoint[]; height?: number }) {
  const max = Math.max(1, ...data.map(p => p.value ?? 0));
  return (
    <View>
      <View style={[styles.chart, { height }]}>
        {data.map(p => (
          <View key={p.time} style={styles.barSlot}>
            {p.value !== null ? (
              <View
                style={[
                  styles.bar,
                  { height: Math.max(2, (p.value / max) * height), backgroundColor: pm25Level(p.value).color },
                ]}
              />
            ) : null}
          </View>
        ))}
      </View>
      <View style={styles.axis}>
        <Text style={styles.axisText}>{vnTime(data[0].time)}</Text>
        <Text style={styles.axisText}>{vnTime(data[data.length - 1].time)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 16,
    marginBottom: 12,
  },
  titleBox: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: colors.text },
  subtitle: { fontSize: 13, color: colors.muted, marginTop: 2 },
  banner: {
    backgroundColor: colors.accentSoft,
    marginHorizontal: 16,
    marginBottom: 12,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  bannerText: { fontSize: 12, color: colors.accent, fontWeight: '600' },
  section: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.text,
    marginHorizontal: 16,
    marginTop: 4,
    marginBottom: 8,
  },
  pill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, alignSelf: 'flex-start' },
  pillText: { fontSize: 11, fontWeight: '700', color: '#FFFFFF' },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.card,
    marginRight: 8,
    marginBottom: 8,
  },
  chipOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { fontSize: 14, color: colors.text },
  chipTextOn: { color: '#FFFFFF', fontWeight: '600' },
  chart: { flexDirection: 'row', alignItems: 'flex-end' },
  barSlot: { flex: 1, marginHorizontal: 1, justifyContent: 'flex-end' },
  bar: { borderTopLeftRadius: 2, borderTopRightRadius: 2 },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  axisText: { fontSize: 11, color: colors.muted },
});
