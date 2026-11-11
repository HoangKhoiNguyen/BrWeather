import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Switch, Text, View } from 'react-native';

import { getAlerts, getSubscriptions } from '../api/client';
import type { AlertEvent, Subscription } from '../api/types';
import { Card, Chip, SampleBanner, ScreenTitle, SectionTitle, colors, vnDay, vnTime } from '../components/ui';

const THRESHOLDS = [25, 50, 80];

export default function AlertsScreen() {
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);

  useEffect(() => {
    getSubscriptions().then(setSubs);
    getAlerts().then(setAlerts);
  }, []);

  const update = (id: number, patch: Partial<Subscription>) =>
    setSubs(list => list.map(s => (s.id === id ? { ...s, ...patch } : s)));

  return (
    <ScrollView>
      <ScreenTitle title="Cảnh báo" subtitle="Báo khi PM2.5 vượt ngưỡng hoặc dự báo sắp vượt" />
      <SampleBanner />

      <SectionTitle>Địa điểm theo dõi</SectionTitle>
      {subs.map(s => (
        <Card key={s.id}>
          <View style={styles.head}>
            <Text style={styles.label}>{s.label}</Text>
            <Switch
              accessibilityLabel={`Bật cảnh báo ${s.label}`}
              value={s.enabled}
              onValueChange={enabled => update(s.id, { enabled })}
              trackColor={{ true: colors.accent }}
            />
          </View>
          <Text style={styles.meta}>Ngưỡng PM2.5 (µg/m³)</Text>
          <View style={styles.chips}>
            {THRESHOLDS.map(t => (
              <Chip
                key={t}
                label={String(t)}
                selected={t === s.pm25Threshold}
                onPress={() => update(s.id, { pm25Threshold: t })}
              />
            ))}
          </View>
          <View style={styles.head}>
            <Text style={styles.body}>Cảnh báo sớm theo dự báo</Text>
            <Switch
              accessibilityLabel={`Cảnh báo sớm ${s.label}`}
              value={s.useForecast}
              onValueChange={useForecast => update(s.id, { useForecast })}
              trackColor={{ true: colors.accent }}
            />
          </View>
        </Card>
      ))}

      <SectionTitle>Đã gửi gần đây</SectionTitle>
      {alerts.map(a => (
        <Card key={a.id}>
          <Text style={styles.meta}>
            {vnDay(a.time)} · {vnTime(a.time)} · {a.label}
          </Text>
          <Text style={styles.body}>{a.reason}</Text>
        </Card>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { fontSize: 16, fontWeight: '600', color: colors.text },
  meta: { fontSize: 12, color: colors.muted, marginBottom: 6 },
  body: { fontSize: 14, color: colors.text, lineHeight: 20 },
  chips: { flexDirection: 'row', marginTop: 2 },
});
