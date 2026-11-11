import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { getRecommendations } from '../api/client';
import type { Recommendation, RecommendationResult } from '../api/types';
import { FadeIn } from '../components/anim';
import { Chip, Glass, SampleBanner, SectionTitle, vnTime } from '../components/ui';
import { glass, pm25Level, text } from '../theme';

const DURATIONS = [30, 45, 60, 90];
const WINDOWS = [
  { label: '🌅 Sáng sớm 5–9h', start: 5, end: 9 },
  { label: '☀️ Sáng 9–12h', start: 9, end: 12 },
  { label: '🌤️ Chiều 14–18h', start: 14, end: 18 },
  { label: '🌆 Tối 18–22h', start: 18, end: 22 },
];

export default function PlannerScreen() {
  const [duration, setDuration] = useState(45);
  const [windowIndex, setWindowIndex] = useState(0);
  const [result, setResult] = useState<RecommendationResult | null>(null);

  useEffect(() => {
    const w = WINDOWS[windowIndex];
    getRecommendations({ durationMinutes: duration, windowStartHour: w.start, windowEndHour: w.end }).then(setResult);
  }, [duration, windowIndex]);

  const runKey = `${duration}-${windowIndex}`;

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <FadeIn style={styles.header}>
        <Text style={styles.title}>Chọn giờ ra ngoài</Text>
        <Text style={styles.subtitle}>Ngày mai · xét bụi mịn, khả năng mưa và nhiệt độ</Text>
        <SampleBanner />
      </FadeIn>

      <FadeIn delay={120}>
        <Glass>
          <SectionTitle icon="🏃">Thời lượng hoạt động</SectionTitle>
          <View style={styles.chips}>
            {DURATIONS.map(d => (
              <Chip key={d} label={`${d} phút`} selected={d === duration} onPress={() => setDuration(d)} />
            ))}
          </View>
          <View style={styles.gap} />
          <SectionTitle icon="🗓️">Khoảng giờ rảnh</SectionTitle>
          <View style={styles.chips}>
            {WINDOWS.map((w, i) => (
              <Chip key={w.label} label={w.label} selected={i === windowIndex} onPress={() => setWindowIndex(i)} />
            ))}
          </View>
        </Glass>
      </FadeIn>

      {result?.options.map((o, i) => (
        <FadeIn key={`${runKey}-${o.start}`} delay={80 + i * 110}>
          <Option option={o} best={i === 0} rank={i + 1} />
        </FadeIn>
      ))}

      {result ? (
        <FadeIn key={`${runKey}-ai`} delay={420}>
          <Glass style={styles.ai}>
            <Text style={styles.aiTitle}>✨ Giải thích{result.usedFallback ? ' · văn bản mẫu' : ' · AI'}</Text>
            <Text style={styles.body}>{result.explanation}</Text>
          </Glass>
        </FadeIn>
      ) : null}
    </ScrollView>
  );
}

function Option({ option, best, rank }: { option: Recommendation; best: boolean; rank: number }) {
  return (
    <View style={[styles.option, best && styles.optionBest]}>
      <View style={styles.optionHead}>
        <Text style={styles.rank}>Lựa chọn {rank}</Text>
        {best ? (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>★ Tốt nhất</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.time}>
        {vnTime(option.start)} – {vnTime(option.end)}
      </Text>
      <View style={styles.metrics}>
        <Metric icon="🌫️" label="PM2.5" value={`${option.pm25}`} color={pm25Level(option.pm25).color} />
        <Metric icon="🌧️" label="Mưa" value={`${option.rainPct}%`} />
        <Metric icon="🌡️" label="Nhiệt độ" value={`${option.temperatureC}°`} />
      </View>
    </View>
  );
}

function Metric({ icon, label, value, color }: { icon: string; label: string; value: string; color?: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricIcon}>{icon}</Text>
      <Text style={[styles.metricValue, color ? { color } : null]}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 140 },
  header: { alignItems: 'center', paddingTop: 18, paddingBottom: 6 },
  title: { fontSize: 28, fontWeight: '700', color: text.primary },
  subtitle: { fontSize: 14, color: text.secondary, marginTop: 4, marginBottom: 12 },
  chips: { flexDirection: 'row', flexWrap: 'wrap' },
  gap: { height: 10 },
  option: {
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 18,
    borderRadius: 24,
    backgroundColor: glass.bg,
    borderWidth: 1,
    borderColor: glass.border,
  },
  optionBest: {
    backgroundColor: glass.strong,
    borderColor: 'rgba(255,214,90,0.75)',
    borderWidth: 1.5,
    boxShadow: '0 0 26px rgba(255,200,80,0.35)',
  },
  optionHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  rank: { fontSize: 12, fontWeight: '700', letterSpacing: 1, color: text.faint },
  badge: { backgroundImage: 'linear-gradient(90deg, #FFD54A, #FFAA00)', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 },
  badgeText: { fontSize: 12, fontWeight: '800', color: text.dark },
  time: { fontSize: 34, fontWeight: '300', color: text.primary, marginVertical: 6 },
  metrics: { flexDirection: 'row', marginTop: 6 },
  metric: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 16, backgroundColor: glass.highlight, marginHorizontal: 3 },
  metricIcon: { fontSize: 18 },
  metricValue: { fontSize: 18, fontWeight: '700', color: text.primary, marginTop: 2 },
  metricLabel: { fontSize: 11, color: text.faint },
  ai: { borderColor: 'rgba(143,211,255,0.5)' },
  aiTitle: { fontSize: 13, fontWeight: '800', color: '#8FD3FF', marginBottom: 6 },
  body: { fontSize: 15, lineHeight: 22, color: text.primary },
});
