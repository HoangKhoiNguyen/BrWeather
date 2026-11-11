import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Switch, Text, View } from 'react-native';

import { getAlerts, getSubscriptions } from '../api/client';
import type { AlertEvent, Subscription } from '../api/types';
import { FadeIn, Pulse } from '../components/anim';
import { Chip, Glass, SampleBanner, SectionTitle, vnDay, vnTime } from '../components/ui';
import { glass, pm25Level, pmColors, text } from '../theme';

const THRESHOLDS = [25, 50, 80];
const TRACK = { false: 'rgba(255,255,255,0.25)', true: pmColors.good };

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
    <ScrollView contentContainerStyle={styles.content}>
      <FadeIn style={styles.header}>
        <Text style={styles.title}>Cảnh báo</Text>
        <Text style={styles.subtitle}>Báo khi PM2.5 vượt ngưỡng hoặc dự báo sắp vượt</Text>
        <SampleBanner />
      </FadeIn>

      {subs.map((s, i) => (
        <FadeIn key={s.id} delay={100 + i * 120}>
          <Glass style={!s.enabled && styles.dim}>
            <View style={styles.head}>
              <View style={styles.headLeft}>
                {s.enabled ? <Pulse color={pmColors.good} /> : <View style={styles.offDot} />}
                <Text style={styles.label}>{s.label}</Text>
              </View>
              <Switch
                accessibilityLabel={`Bật cảnh báo ${s.label}`}
                value={s.enabled}
                onValueChange={enabled => update(s.id, { enabled })}
                trackColor={TRACK}
                thumbColor="#FFFFFF"
              />
            </View>
            <Text style={styles.meta}>Ngưỡng PM2.5 (µg/m³)</Text>
            <View style={styles.chips}>
              {THRESHOLDS.map(t => (
                <Chip key={t} label={`${t} · ${pm25Level(t + 0.1).label}`} selected={t === s.pm25Threshold} onPress={() => update(s.id, { pm25Threshold: t })} />
              ))}
            </View>
            <View style={styles.head}>
              <Text style={styles.body}>🔮 Cảnh báo sớm theo dự báo</Text>
              <Switch
                accessibilityLabel={`Cảnh báo sớm ${s.label}`}
                value={s.useForecast}
                onValueChange={useForecast => update(s.id, { useForecast })}
                trackColor={TRACK}
                thumbColor="#FFFFFF"
              />
            </View>
          </Glass>
        </FadeIn>
      ))}

      <FadeIn delay={380}>
        <Glass>
          <SectionTitle icon="🔔">Đã gửi gần đây</SectionTitle>
          {alerts.map((a, i) => (
            <View key={a.id} style={styles.event}>
              <View style={styles.timeline}>
                <View style={[styles.eventDot, { backgroundColor: pm25Level(a.value).color }]} />
                {i < alerts.length - 1 ? <View style={styles.line} /> : null}
              </View>
              <View style={styles.eventBody}>
                <Text style={styles.meta}>
                  {vnDay(a.time)} · {vnTime(a.time)} · {a.label}
                </Text>
                <Text style={styles.body}>{a.reason}</Text>
              </View>
            </View>
          ))}
        </Glass>
      </FadeIn>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 140 },
  header: { alignItems: 'center', paddingTop: 18, paddingBottom: 6 },
  title: { fontSize: 28, fontWeight: '700', color: text.primary },
  subtitle: { fontSize: 14, color: text.secondary, marginTop: 4, marginBottom: 12 },
  dim: { opacity: 0.7 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  offDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: pmColors.none },
  label: { fontSize: 18, fontWeight: '700', color: text.primary },
  meta: { fontSize: 12, color: text.faint, marginTop: 10, marginBottom: 8 },
  body: { fontSize: 14, lineHeight: 21, color: text.primary },
  chips: { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 4 },
  event: { flexDirection: 'row', gap: 12 },
  timeline: { alignItems: 'center', width: 14 },
  eventDot: { width: 12, height: 12, borderRadius: 6, marginTop: 14, borderWidth: 2, borderColor: glass.border },
  line: { flex: 1, width: 2, backgroundColor: glass.border, marginTop: 4 },
  eventBody: { flex: 1, paddingBottom: 12 },
});
