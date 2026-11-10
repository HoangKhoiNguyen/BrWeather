import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from 'react-native';

import { getStations } from '../api/client';
import type { StationSummary } from '../api/types';

// F01 first version: a list of stations. The map comes next (MapLibre + OpenStreetMap).
export default function OverviewScreen() {
  const [stations, setStations] = useState<StationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStations().then(setStations).catch(e => setError(String(e)));
  }, []);

  if (error) {
    return <Text style={styles.message}>Không tải được dữ liệu. Thử lại sau.</Text>;
  }
  if (!stations) {
    return <ActivityIndicator style={styles.message} />;
  }

  return (
    <FlatList
      data={stations}
      keyExtractor={s => String(s.id)}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <Text style={styles.name}>{item.name}</Text>
          <Text style={styles.value}>
            {item.latest.pm25 === null ? 'Không có dữ liệu' : `${item.latest.pm25} ${item.latest.unit}`}
          </Text>
          <Text style={styles.meta}>
            {item.latest.source} · {item.latest.kind === 'observed' ? 'Số đo' : 'Mô hình'}
            {item.latest.status === 'stale' ? ' · Dữ liệu cũ' : ''}
            {item.latest.reliability ? ` · Tin cậy: ${item.latest.reliability}` : ''}
          </Text>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  message: { marginTop: 48, textAlign: 'center' },
  card: { padding: 16, borderBottomWidth: 1, borderColor: '#e2e8ea' },
  name: { fontSize: 16, fontWeight: '600' },
  value: { fontSize: 28, fontWeight: '700', marginVertical: 4 },
  meta: { fontSize: 13, color: '#5b6b72' },
});
