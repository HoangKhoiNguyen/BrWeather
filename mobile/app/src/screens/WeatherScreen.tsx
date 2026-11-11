import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { getWeather } from '../api/client';
import type { Weather } from '../api/types';
import { Card, SampleBanner, ScreenTitle, SectionTitle, colors, fmt, vnDay, vnTime, weatherInfo } from '../components/ui';

export default function WeatherScreen() {
  const [w, setW] = useState<Weather | null>(null);

  useEffect(() => {
    getWeather().then(setW);
  }, []);

  if (!w) {
    return <ActivityIndicator style={styles.loading} color={colors.accent} />;
  }

  const now = weatherInfo(w.current.weatherCode);

  return (
    <ScrollView>
      <ScreenTitle title="Thời tiết" subtitle={`Hà Nội · ${w.source} · Cập nhật ${vnTime(w.fetchedAt)}`} />
      <SampleBanner />
      <Card>
        <View style={styles.nowRow}>
          <Text style={styles.nowIcon}>{now.icon}</Text>
          <View>
            <Text style={styles.nowTemp}>{fmt(w.current.temperatureC, '°C')}</Text>
            <Text style={styles.meta}>
              {now.label} · Cảm giác như {fmt(w.current.apparentC, '°C')}
            </Text>
          </View>
        </View>
        <View style={styles.stats}>
          <Stat label="Độ ẩm" value={fmt(w.current.humidityPct, '%')} />
          <Stat label="Gió" value={fmt(w.current.windKmh, ' km/h')} />
          <Stat label="Mưa" value={fmt(w.current.precipitationMm, ' mm')} />
          <Stat label="UV" value={fmt(w.current.uvIndex)} />
        </View>
      </Card>

      <SectionTitle>24 giờ tới</SectionTitle>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hours}>
        {w.hourly.map(h => (
          <View key={h.time} style={styles.hour}>
            <Text style={styles.meta}>{vnTime(h.time)}</Text>
            <Text style={styles.hourIcon}>{weatherInfo(h.weatherCode).icon}</Text>
            <Text style={styles.hourTemp}>{fmt(h.temperatureC, '°')}</Text>
            <Text style={styles.rain}>{fmt(h.precipitationProbPct, '%')}</Text>
          </View>
        ))}
      </ScrollView>

      <SectionTitle>7 ngày tới</SectionTitle>
      <Card>
        {w.daily.map(d => (
          <View key={d.date} style={styles.day}>
            <Text style={styles.dayName}>{vnDay(d.date)}</Text>
            <Text style={styles.dayIcon}>{weatherInfo(d.weatherCode).icon}</Text>
            <Text style={styles.rainDay}>{fmt(d.precipitationMm, ' mm')}</Text>
            <Text style={styles.dayTemp}>
              {fmt(d.minC, '°')} / {fmt(d.maxC, '°')}
            </Text>
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.meta}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  loading: { marginTop: 64 },
  nowRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  nowIcon: { fontSize: 46 },
  nowTemp: { fontSize: 36, fontWeight: '700', color: colors.text },
  meta: { fontSize: 12, color: colors.muted },
  stats: { flexDirection: 'row', marginTop: 14 },
  stat: { flex: 1 },
  statValue: { fontSize: 15, fontWeight: '600', color: colors.text, marginTop: 2 },
  hours: { paddingHorizontal: 16, paddingBottom: 12 },
  hour: {
    backgroundColor: colors.card,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginRight: 8,
    alignItems: 'center',
  },
  hourIcon: { fontSize: 22, marginVertical: 4 },
  hourTemp: { fontSize: 15, fontWeight: '600', color: colors.text },
  rain: { fontSize: 12, color: colors.accent, marginTop: 2 },
  day: { flexDirection: 'row', alignItems: 'center', paddingVertical: 7 },
  dayName: { flex: 1.3, fontSize: 14, color: colors.text },
  dayIcon: { flex: 0.6, fontSize: 18 },
  rainDay: { flex: 1, fontSize: 13, color: colors.accent },
  dayTemp: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text, textAlign: 'right' },
});
