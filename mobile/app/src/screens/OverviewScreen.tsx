import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { getStations } from '../api/client';
import type { StationSummary } from '../api/types';
import { FadeIn, PressScale, Pulse, useCountUp } from '../components/anim';
import { Glass, PmGauge, ReliabilityPill, SampleBanner, SectionTitle, vnTime } from '../components/ui';
import { glass, pm25Level, pmColors, text } from '../theme';

export default function OverviewScreen({ onOpen }: { onOpen: (s: StationSummary) => void }) {
  const [stations, setStations] = useState<StationSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(false);
      setStations(await getStations());
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  // Hero shows the nearest station that has a current reading
  const nearest = stations
    ?.filter(s => s.latest.status === 'ok')
    .sort((a, b) => a.distanceKm - b.distanceKm)[0];

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor="#fff" colors={['#1F6FD1']} />}>
      <FadeIn>
        <View style={styles.header}>
          <Text style={styles.place}>📍 Hà Nội</Text>
          <Text style={styles.headerSub}>Chất lượng không khí</Text>
        </View>
        <SampleBanner />
      </FadeIn>

      {error ? (
        <Glass>
          <Text style={styles.body}>Không tải được dữ liệu. Kéo xuống để thử lại.</Text>
        </Glass>
      ) : null}
      {!stations && !error ? <ActivityIndicator style={styles.loading} color="#fff" /> : null}

      {nearest ? (
        <FadeIn delay={120}>
          <Hero station={nearest} onPress={() => onOpen(nearest)} />
        </FadeIn>
      ) : null}

      {nearest ? (
        <FadeIn delay={240}>
          <Glass>
            <SectionTitle icon="✨">Tóm tắt</SectionTitle>
            <Text style={styles.body}>
              Không khí quanh bạn ở mức <Text style={styles.bold}>{pm25Level(nearest.latest.pm25).label.toLowerCase()}</Text>.{' '}
              {pm25Level(nearest.latest.pm25).advice}
            </Text>
            <Text style={styles.note}>Văn bản mẫu · sau này do AI tạo từ số liệu đã kiểm tra</Text>
          </Glass>
        </FadeIn>
      ) : null}

      {stations ? (
        <FadeIn delay={360}>
          <Glass style={styles.listCard}>
            <View style={styles.listHead}>
              <SectionTitle icon="📡">Trạm quan trắc</SectionTitle>
            </View>
            {stations.map((s, i) => (
              <StationRow key={s.id} station={s} last={i === stations.length - 1} onPress={() => onOpen(s)} />
            ))}
          </Glass>
        </FadeIn>
      ) : null}
    </ScrollView>
  );
}

function Hero({ station, onPress }: { station: StationSummary; onPress: () => void }) {
  const { latest } = station;
  const level = pm25Level(latest.pm25);
  const shown = useCountUp(latest.pm25);
  return (
    <PressScale onPress={onPress} accessibilityLabel={`Xem chi tiết trạm ${station.name}`} style={styles.hero}>
      <View style={styles.liveRow}>
        <Pulse color={pmColors.good} />
        <Text style={styles.live}>Trạm gần nhất · {station.distanceKm} km</Text>
      </View>
      <Text style={styles.heroName}>{station.name}</Text>
      <View style={styles.valueRow}>
        <Text style={styles.value}>{shown}</Text>
        <View>
          <Text style={styles.unit}>µg/m³</Text>
          <Text style={styles.unit}>PM2.5</Text>
        </View>
      </View>
      <Text style={[styles.level, { color: level.color }]}>{level.label}</Text>
      <PmGauge value={latest.pm25} />
      <View style={styles.heroFoot}>
        <ReliabilityPill level={latest.reliability} />
        <Text style={styles.meta}>
          {latest.source} · {latest.kind === 'observed' ? 'Số đo' : 'Mô hình'}
          {latest.measuredAt ? ` · ${vnTime(latest.measuredAt)}` : ''}
        </Text>
      </View>
    </PressScale>
  );
}

function StationRow({ station, last, onPress }: { station: StationSummary; last: boolean; onPress: () => void }) {
  const { latest } = station;
  const level = pm25Level(latest.pm25);
  return (
    <PressScale onPress={onPress} accessibilityLabel={`Trạm ${station.name}`} style={[styles.row, !last && styles.rowLine]}>
      <View style={[styles.rowBar, { backgroundColor: level.color }]} />
      <View style={styles.rowMain}>
        <Text style={styles.rowName} numberOfLines={1}>
          {station.name}
        </Text>
        <Text style={styles.meta}>
          {station.distanceKm} km
          {latest.measuredAt ? ` · ${vnTime(latest.measuredAt)}` : ''}
          {latest.status === 'stale' ? ' · Dữ liệu cũ' : ''}
        </Text>
      </View>
      <View style={styles.rowRight}>
        <Text style={styles.rowValue}>{latest.pm25 === null ? '–' : Math.round(latest.pm25)}</Text>
        <Text style={[styles.rowLevel, { color: level.color }]}>
          {latest.pm25 === null ? 'Không có dữ liệu' : level.label}
        </Text>
      </View>
    </PressScale>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 140 },
  header: { alignItems: 'center', paddingTop: 18, paddingBottom: 10 },
  place: { fontSize: 30, fontWeight: '600', color: text.primary },
  headerSub: { fontSize: 15, color: text.secondary, marginTop: 2 },
  loading: { marginTop: 80 },
  hero: {
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 22,
    borderRadius: 30,
    backgroundColor: glass.strong,
    borderWidth: 1,
    borderColor: glass.border,
    boxShadow: '0 14px 34px rgba(0,0,0,0.25)',
  },
  liveRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  live: { fontSize: 12, color: text.secondary, fontWeight: '600' },
  heroName: { fontSize: 19, fontWeight: '700', color: text.primary, marginTop: 8 },
  valueRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 10, marginTop: 4 },
  value: {
    fontSize: 92,
    fontWeight: '200',
    color: text.primary,
    lineHeight: 100,
    textShadowColor: 'rgba(0,0,0,0.2)',
    textShadowRadius: 12,
  },
  unit: { fontSize: 14, color: text.secondary, marginBottom: 4 },
  level: { fontSize: 22, fontWeight: '800', marginBottom: 14 },
  heroFoot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, gap: 8 },
  meta: { fontSize: 12, color: text.faint },
  body: { fontSize: 15, lineHeight: 22, color: text.primary },
  bold: { fontWeight: '800' },
  note: { fontSize: 11, color: text.faint, marginTop: 10 },
  listCard: { paddingHorizontal: 0, paddingBottom: 6 },
  listHead: { paddingHorizontal: 18 },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 18, gap: 12 },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: glass.border },
  rowBar: { width: 4, height: 38, borderRadius: 2 },
  rowMain: { flex: 1 },
  rowName: { fontSize: 16, fontWeight: '600', color: text.primary },
  rowRight: { alignItems: 'flex-end' },
  rowValue: { fontSize: 26, fontWeight: '300', color: text.primary },
  rowLevel: { fontSize: 11, fontWeight: '700' },
});
