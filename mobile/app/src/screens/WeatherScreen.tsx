import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Animated, ScrollView, StyleSheet, Text, View } from 'react-native';

import { getWeather } from '../api/client';
import type { Weather } from '../api/types';
import { FadeIn, useCountUp, useGrow } from '../components/anim';
import { WeatherHeroIcon } from '../components/sky';
import { Glass, SampleBanner, SectionTitle, fmt, vnDay, vnTime, weatherInfo } from '../components/ui';
import { glass, skyFor, tempRamp, text, uvRamp } from '../theme';

export default function WeatherScreen() {
  const [w, setW] = useState<Weather | null>(null);

  useEffect(() => {
    getWeather().then(setW);
  }, []);

  if (!w) {
    return <ActivityIndicator style={styles.loading} color="#fff" />;
  }

  const night = skyFor(w.current.weatherCode, w.fetchedAt) === 'night';
  const today = w.daily[0];

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <FadeIn style={styles.hero}>
        <Text style={styles.place}>Hà Nội</Text>
        <WeatherHeroIcon code={w.current.weatherCode} night={night} />
        <BigTemp value={w.current.temperatureC} />
        <Text style={styles.condition}>{weatherInfo(w.current.weatherCode, night).label}</Text>
        <Text style={styles.hiLo}>
          C: {fmt(today?.maxC ?? null, '°')}   T: {fmt(today?.minC ?? null, '°')}   ·   Cảm giác {w.current.apparentC === null ? '–' : `${Math.round(w.current.apparentC)}°`}
        </Text>
        <Text style={styles.source}>
          {w.source} · cập nhật {vnTime(w.fetchedAt)}
        </Text>
        <SampleBanner />
      </FadeIn>

      <FadeIn delay={150}>
        <Glass style={styles.noSidePad}>
          <View style={styles.padded}>
            <SectionTitle icon="🕒">Dự báo theo giờ</SectionTitle>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hours}>
            {w.hourly.map((h, i) => (
              <View key={h.time} style={[styles.hour, i === 0 && styles.hourNow]}>
                <Text style={styles.hourTime}>{i === 0 ? 'Bây giờ' : vnTime(h.time)}</Text>
                <Text style={styles.hourIcon}>{weatherInfo(h.weatherCode, skyFor(h.weatherCode, h.time) === 'night').icon}</Text>
                <Text style={styles.hourRain}>{(h.precipitationProbPct ?? 0) >= 20 ? `${h.precipitationProbPct}%` : ' '}</Text>
                <Text style={styles.hourTemp}>{h.temperatureC === null ? '–' : `${Math.round(h.temperatureC)}°`}</Text>
              </View>
            ))}
          </ScrollView>
        </Glass>
      </FadeIn>

      <FadeIn delay={280}>
        <Glass>
          <SectionTitle icon="📅">Dự báo 7 ngày</SectionTitle>
          <DailyList weather={w} />
        </Glass>
      </FadeIn>

      <FadeIn delay={400}>
        <View style={styles.tiles}>
          <Tile icon="💧" title="Độ ẩm" value={fmt(w.current.humidityPct, '%')}>
            <Meter ratio={(w.current.humidityPct ?? 0) / 100} ramp="linear-gradient(90deg, #8FD3FF, #3B82F6)" />
            <Text style={styles.tileNote}>Điểm sương khoảng 19°</Text>
          </Tile>
          <Tile icon="🌬️" title="Gió" value={fmt(w.current.windKmh, ' km/h')}>
            <Compass deg={w.current.windDirectionDeg ?? 0} />
          </Tile>
          <Tile icon="🔆" title="Chỉ số UV" value={fmt(w.current.uvIndex)}>
            <Meter ratio={(w.current.uvIndex ?? 0) / 11} ramp={uvRamp} marker />
            <Text style={styles.tileNote}>{uvLabel(w.current.uvIndex)}</Text>
          </Tile>
          <Tile icon="🌧️" title="Lượng mưa" value={fmt(w.current.precipitationMm, ' mm')}>
            <Text style={styles.tileNote}>
              Hôm nay dự kiến {fmt(today?.precipitationMm ?? null, ' mm')}
            </Text>
          </Tile>
        </View>
      </FadeIn>
    </ScrollView>
  );
}

function BigTemp({ value }: { value: number | null }) {
  const shown = useCountUp(value === null ? null : Math.round(value), 900);
  return <Text style={styles.temp}>{shown}°</Text>;
}

function DailyList({ weather }: { weather: Weather }) {
  const mins = weather.daily.map(d => d.minC ?? 0);
  const maxs = weather.daily.map(d => d.maxC ?? 0);
  const lo = Math.min(...mins);
  const hi = Math.max(...maxs);
  const span = Math.max(1, hi - lo);
  return (
    <View>
      {weather.daily.map((d, i) => (
        <View key={d.date} style={[styles.day, i > 0 && styles.dayLine]}>
          <Text style={styles.dayName}>{vnDay(d.date, true)}</Text>
          <View style={styles.dayIconBox}>
            <Text style={styles.dayIcon}>{weatherInfo(d.weatherCode).icon}</Text>
            {(d.precipitationMm ?? 0) > 0 ? <Text style={styles.dayRain}>{d.precipitationMm} mm</Text> : null}
          </View>
          <Text style={styles.dayMin}>{fmt(d.minC, '°')}</Text>
          <RangeBar left={((d.minC ?? lo) - lo) / span} right={((d.maxC ?? hi) - lo) / span} index={i} />
          <Text style={styles.dayMax}>{fmt(d.maxC, '°')}</Text>
        </View>
      ))}
    </View>
  );
}

function RangeBar({ left, right, index }: { left: number; right: number; index: number }) {
  const grow = useGrow(300 + index * 60, 700);
  return (
    <View style={styles.rangeTrack}>
      <Animated.View
        style={[
          styles.rangeFill,
          {
            left: `${left * 100}%`,
            width: `${Math.max(0.08, right - left) * 100}%`,
            transform: [{ scaleX: grow }],
          },
        ]}
      />
    </View>
  );
}

function Tile({ icon, title, value, children }: { icon: string; title: string; value: string; children?: React.ReactNode }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileTitle}>
        {icon}  {title.toUpperCase()}
      </Text>
      <Text style={styles.tileValue}>{value}</Text>
      {children}
    </View>
  );
}

function Meter({ ratio, ramp, marker = false }: { ratio: number; ramp: string; marker?: boolean }) {
  const grow = useGrow(500, 900);
  const r = Math.max(0, Math.min(1, ratio));
  if (marker) {
    return (
      <View style={[styles.meter, { backgroundImage: ramp }]}>
        <Animated.View style={[styles.meterDot, { left: `${r * 92}%`, opacity: grow }]} />
      </View>
    );
  }
  return (
    <View style={styles.meter}>
      <Animated.View style={[styles.meterFill, { width: `${r * 100}%`, backgroundImage: ramp, transform: [{ scaleX: grow }] }]} />
    </View>
  );
}

function Compass({ deg }: { deg: number }) {
  const grow = useGrow(500, 1400);
  const rotate = grow.interpolate({ inputRange: [0, 1], outputRange: ['0deg', `${deg + 180}deg`] });
  return (
    <View style={styles.compass}>
      <Text style={[styles.cardinal, styles.north]}>B</Text>
      <Animated.Text style={[styles.arrow, { transform: [{ rotate }] }]}>➤</Animated.Text>
    </View>
  );
}

function uvLabel(uv: number | null): string {
  if (uv === null) {
    return '';
  }
  if (uv <= 2) {
    return 'Thấp';
  }
  if (uv <= 5) {
    return 'Trung bình';
  }
  if (uv <= 7) {
    return 'Cao';
  }
  return 'Rất cao, nên che chắn';
}

const styles = StyleSheet.create({
  content: { paddingBottom: 140 },
  loading: { marginTop: 120 },
  hero: { alignItems: 'center', paddingTop: 16, paddingBottom: 18 },
  place: { fontSize: 30, fontWeight: '500', color: text.primary, marginBottom: 4 },
  temp: {
    fontSize: 104,
    fontWeight: '200',
    color: text.primary,
    lineHeight: 112,
    marginLeft: 24,
    textShadowColor: 'rgba(0,0,0,0.18)',
    textShadowRadius: 14,
  },
  condition: { fontSize: 20, fontWeight: '600', color: text.primary },
  hiLo: { fontSize: 15, color: text.secondary, marginTop: 4 },
  source: { fontSize: 11, color: text.faint, marginTop: 8, marginBottom: 10 },
  noSidePad: { paddingHorizontal: 0 },
  padded: { paddingHorizontal: 18 },
  hours: { paddingHorizontal: 12 },
  hour: { alignItems: 'center', width: 62, paddingVertical: 10, borderRadius: 18, marginHorizontal: 2 },
  hourNow: { backgroundColor: glass.highlight, borderWidth: 1, borderColor: glass.border },
  hourTime: { fontSize: 13, fontWeight: '600', color: text.primary },
  hourIcon: { fontSize: 24, marginTop: 8 },
  hourRain: { fontSize: 11, fontWeight: '700', color: '#8FD3FF', height: 16 },
  hourTemp: { fontSize: 19, fontWeight: '500', color: text.primary },
  day: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, gap: 8 },
  dayLine: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: glass.border },
  dayName: { width: 72, fontSize: 16, fontWeight: '600', color: text.primary },
  dayIconBox: { width: 46, alignItems: 'center' },
  dayIcon: { fontSize: 22 },
  dayRain: { fontSize: 10, fontWeight: '700', color: '#8FD3FF' },
  dayMin: { width: 34, textAlign: 'right', fontSize: 16, color: text.faint },
  dayMax: { width: 34, fontSize: 16, fontWeight: '600', color: text.primary },
  rangeTrack: { flex: 1, height: 6, borderRadius: 3, backgroundColor: 'rgba(0,0,0,0.22)' },
  rangeFill: { position: 'absolute', top: 0, bottom: 0, borderRadius: 3, backgroundImage: tempRamp, transformOrigin: 'left' },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 10 },
  tile: {
    width: '46%',
    flexGrow: 1,
    margin: 6,
    padding: 16,
    minHeight: 150,
    borderRadius: 24,
    backgroundColor: glass.bg,
    borderWidth: StyleSheet.hairlineWidth * 2,
    borderColor: glass.border,
    boxShadow: '0 8px 22px rgba(0,0,0,0.16)',
  },
  tileTitle: { fontSize: 11, fontWeight: '700', letterSpacing: 1, color: text.faint },
  tileValue: { fontSize: 30, fontWeight: '400', color: text.primary, marginTop: 8, marginBottom: 10 },
  tileNote: { fontSize: 12, color: text.secondary, marginTop: 8 },
  meter: { height: 6, borderRadius: 3, backgroundColor: 'rgba(0,0,0,0.22)', justifyContent: 'center' },
  meterFill: { height: 6, borderRadius: 3, transformOrigin: 'left' },
  meterDot: {
    position: 'absolute',
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#fff',
    boxShadow: '0 1px 6px rgba(0,0,0,0.4)',
  },
  compass: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 2,
    borderColor: glass.border,
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardinal: { position: 'absolute', fontSize: 10, fontWeight: '800', color: text.faint },
  north: { top: 3 },
  arrow: { fontSize: 22, color: text.primary },
});
