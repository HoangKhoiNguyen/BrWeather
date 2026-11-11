import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { getStations } from '../api/client';
import type { StationSummary } from '../api/types';
import { Card, Pill, ReliabilityPill, SampleBanner, ScreenTitle, colors, pm25Level, vnTime } from '../components/ui';

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

  return (
    <ScrollView refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
      <ScreenTitle title="brWeather" subtitle="Chất lượng không khí tại các trạm ở Hà Nội" />
      <SampleBanner />
      {error ? (
        <Card>
          <Text style={styles.empty}>Không tải được dữ liệu. Kéo xuống để thử lại.</Text>
        </Card>
      ) : null}
      {!stations && !error ? <ActivityIndicator style={styles.loading} color={colors.accent} /> : null}
      {stations?.map(s => (
        <StationCard key={s.id} station={s} onPress={() => onOpen(s)} />
      ))}
    </ScrollView>
  );
}

function StationCard({ station, onPress }: { station: StationSummary; onPress: () => void }) {
  const { latest } = station;
  const level = pm25Level(latest.pm25);
  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      <Card>
        <View style={styles.row}>
          <View style={styles.flex}>
            <Text style={styles.name}>{station.name}</Text>
            <Text style={styles.meta}>Cách bạn {station.distanceKm} km</Text>
          </View>
          <View style={[styles.dot, { backgroundColor: level.color }]} />
        </View>
        <View style={styles.valueRow}>
          {latest.pm25 === null ? (
            <Text style={styles.noData}>Không có dữ liệu</Text>
          ) : (
            <>
              <Text style={styles.value}>{latest.pm25}</Text>
              <Text style={styles.unit}> {latest.unit} PM2.5</Text>
            </>
          )}
        </View>
        <View style={styles.pills}>
          {latest.pm25 !== null ? <Pill label={level.label} color={level.color} /> : null}
          <ReliabilityPill level={latest.reliability} />
          {latest.status === 'stale' ? <Pill label="Dữ liệu cũ" color={colors.none} /> : null}
        </View>
        <Text style={styles.meta}>
          {latest.source} · {latest.kind === 'observed' ? 'Số đo' : 'Mô hình'}
          {latest.measuredAt ? ` · Cập nhật ${vnTime(latest.measuredAt)}` : ''}
        </Text>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  loading: { marginTop: 48 },
  empty: { color: colors.text, textAlign: 'center' },
  row: { flexDirection: 'row', alignItems: 'center' },
  flex: { flex: 1 },
  name: { fontSize: 16, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.muted, marginTop: 2 },
  dot: { width: 14, height: 14, borderRadius: 7 },
  valueRow: { flexDirection: 'row', alignItems: 'baseline', marginVertical: 6 },
  value: { fontSize: 34, fontWeight: '700', color: colors.text },
  unit: { fontSize: 13, color: colors.muted },
  noData: { fontSize: 18, fontWeight: '600', color: colors.muted },
  pills: { flexDirection: 'row', gap: 6, marginBottom: 6 },
});
