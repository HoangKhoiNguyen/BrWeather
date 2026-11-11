import React, { useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';

import { USE_MOCK } from '../api/client';
import type { Reliability, SeriesPoint } from '../api/types';
import { PM_SCALE_MAX, glass, pm25Level, pmColors, pmRamp, text } from '../theme';
import { useGrow } from './anim';

const VN_OFFSET = 7 * 3600 * 1000;
const pad = (n: number) => String(n).padStart(2, '0');

// Data is stored in UTC and always shown in Vietnam time, whatever the device clock says
export function vnTime(iso: string): string {
  const d = new Date(new Date(iso).getTime() + VN_OFFSET);
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

export function vnDay(iso: string, short = false): string {
  const d = new Date(new Date(iso).getTime() + VN_OFFSET);
  const today = new Date(Date.now() + VN_OFFSET);
  if (d.getUTCDate() === today.getUTCDate() && d.getUTCMonth() === today.getUTCMonth()) {
    return 'Hôm nay';
  }
  const names = ['CN', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7'];
  return short ? names[d.getUTCDay()] : `${names[d.getUTCDay()]}, ${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}`;
}

export function weatherInfo(code: number | null, night = false): { icon: string; label: string } {
  if (code === null) {
    return { icon: '–', label: 'Không rõ' };
  }
  if (code <= 1) {
    return night ? { icon: '🌙', label: 'Trời quang' } : { icon: '☀️', label: 'Nắng' };
  }
  if (code === 2) {
    return { icon: night ? '☁️' : '⛅', label: 'Có mây' };
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

/** Frosted card. */
export function Glass({ children, style }: { children: React.ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.glass, style]}>{children}</View>;
}

export function SectionTitle({ icon, children }: { icon?: string; children: string }) {
  return (
    <Text style={styles.section}>
      {icon ? `${icon}  ` : ''}
      {children.toUpperCase()}
    </Text>
  );
}

export function SampleBanner() {
  if (!USE_MOCK) {
    return null;
  }
  return (
    <View style={styles.banner}>
      <Text style={styles.bannerText}>● Bản khung · dữ liệu mẫu</Text>
    </View>
  );
}

export function Pill({ label, color, dark = true }: { label: string; color: string; dark?: boolean }) {
  return (
    <View style={[styles.pill, { backgroundColor: color }]}>
      <Text style={[styles.pillText, { color: dark ? text.dark : text.primary }]}>{label}</Text>
    </View>
  );
}

const RELIABILITY: Record<Reliability, { label: string; color: string }> = {
  high: { label: 'Tin cậy cao', color: pmColors.good },
  medium: { label: 'Tin cậy TB', color: pmColors.moderate },
  low: { label: 'Tin cậy thấp', color: pmColors.veryHigh },
};

export function ReliabilityPill({ level }: { level: Reliability | null }) {
  if (!level) {
    return null;
  }
  return (
    <View style={styles.outlinePill}>
      <View style={[styles.dot, { backgroundColor: RELIABILITY[level].color }]} />
      <Text style={styles.outlineText}>{RELIABILITY[level].label}</Text>
    </View>
  );
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

/** PM2.5 gauge: colour ramp with a marker that slides to the value. */
export function PmGauge({ value }: { value: number | null }) {
  const [width, setWidth] = useState(0);
  const grow = useGrow(250, 1200);
  const ratio = value === null ? 0 : Math.min(1, value / PM_SCALE_MAX);
  const translateX = grow.interpolate({ inputRange: [0, 1], outputRange: [0, Math.max(0, ratio * width - 9)] });
  return (
    <View>
      <View style={styles.gaugeTrack} onLayout={e => setWidth(e.nativeEvent.layout.width)}>
        {value !== null ? (
          <Animated.View
            style={[styles.gaugeMarker, { borderColor: pm25Level(value).color, transform: [{ translateX }] }]}
          />
        ) : null}
      </View>
      <View style={styles.gaugeLabels}>
        {[0, 25, 50, 80, 150].map(l => (
          <Text
            key={l}
            style={[
              styles.gaugeLabel,
              l === PM_SCALE_MAX ? styles.gaugeLabelEnd : { left: Math.max(0, (l / PM_SCALE_MAX) * width - 6) },
            ]}>
            {l === PM_SCALE_MAX ? `${l}+` : l}
          </Text>
        ))}
      </View>
    </View>
  );
}

function Bar({ value, max, height, index }: { value: number; max: number; height: number; index: number }) {
  const grow = useGrow(80 + index * 22, 700);
  return (
    <Animated.View
      style={[
        styles.bar,
        {
          height: Math.max(3, (value / max) * height),
          backgroundImage: `linear-gradient(180deg, ${pm25Level(value).color} 0%, rgba(255,255,255,0.25) 100%)`,
          transform: [{ scaleY: grow }],
        },
      ]}
    />
  );
}

// A missing hour leaves an empty slot: the chart must never imply data that does not exist
export function BarChart({ data, height = 120 }: { data: SeriesPoint[]; height?: number }) {
  const max = Math.max(1, ...data.map(p => p.value ?? 0));
  const ticks = [0, Math.floor(data.length / 3), Math.floor((2 * data.length) / 3), data.length - 1];
  return (
    <View>
      <View style={[styles.chart, { height }]}>
        {data.map((p, i) => (
          <View key={p.time} style={styles.barSlot}>
            {p.value !== null ? <Bar value={p.value} max={max} height={height} index={i} /> : null}
          </View>
        ))}
      </View>
      <View style={styles.axis}>
        {ticks.map(i => (
          <Text key={i} style={styles.axisText}>
            {vnTime(data[i].time)}
          </Text>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  glass: {
    backgroundColor: glass.bg,
    borderColor: glass.border,
    borderWidth: StyleSheet.hairlineWidth * 2,
    borderRadius: 24,
    padding: 18,
    marginHorizontal: 16,
    marginBottom: 14,
    boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
  },
  section: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    color: text.faint,
    marginBottom: 10,
  },
  banner: {
    alignSelf: 'center',
    backgroundColor: 'rgba(255,255,255,0.16)',
    borderRadius: 999,
    paddingVertical: 5,
    paddingHorizontal: 12,
    marginBottom: 14,
  },
  bannerText: { fontSize: 11, fontWeight: '600', color: text.secondary, letterSpacing: 0.3 },
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, alignSelf: 'flex-start' },
  pillText: { fontSize: 12, fontWeight: '800' },
  outlinePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: glass.border,
    backgroundColor: glass.highlight,
  },
  outlineText: { fontSize: 12, fontWeight: '600', color: text.primary },
  dot: { width: 7, height: 7, borderRadius: 4 },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: glass.border,
    backgroundColor: glass.bg,
    marginRight: 8,
    marginBottom: 8,
  },
  chipOn: { backgroundColor: '#FFFFFF', borderColor: '#FFFFFF' },
  chipText: { fontSize: 14, color: text.primary, fontWeight: '500' },
  chipTextOn: { color: text.dark, fontWeight: '700' },
  gaugeTrack: { height: 8, borderRadius: 4, backgroundImage: pmRamp, justifyContent: 'center' },
  gaugeMarker: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#FFFFFF',
    borderWidth: 4,
    boxShadow: '0 2px 8px rgba(0,0,0,0.35)',
  },
  gaugeLabels: { height: 16, marginTop: 6 },
  gaugeLabel: { position: 'absolute', fontSize: 10, color: text.faint },
  gaugeLabelEnd: { right: 0 },
  chart: { flexDirection: 'row', alignItems: 'flex-end' },
  barSlot: { flex: 1, marginHorizontal: 1.5, justifyContent: 'flex-end', height: '100%' },
  bar: { borderRadius: 4, transformOrigin: 'bottom' },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  axisText: { fontSize: 11, color: text.faint },
});
