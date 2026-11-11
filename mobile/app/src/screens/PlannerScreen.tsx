import React, { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { getRecommendations } from '../api/client';
import type { RecommendationResult } from '../api/types';
import { Card, Chip, SampleBanner, ScreenTitle, SectionTitle, colors, vnTime } from '../components/ui';

const DURATIONS = [30, 45, 60, 90];
const WINDOWS = [
  { label: 'Sáng sớm 5–9h', start: 5, end: 9 },
  { label: 'Sáng 9–12h', start: 9, end: 12 },
  { label: 'Chiều 14–18h', start: 14, end: 18 },
  { label: 'Tối 18–22h', start: 18, end: 22 },
];

export default function PlannerScreen() {
  const [duration, setDuration] = useState(45);
  const [windowIndex, setWindowIndex] = useState(0);
  const [result, setResult] = useState<RecommendationResult | null>(null);

  useEffect(() => {
    const w = WINDOWS[windowIndex];
    getRecommendations({ durationMinutes: duration, windowStartHour: w.start, windowEndHour: w.end }).then(setResult);
  }, [duration, windowIndex]);

  return (
    <ScrollView>
      <ScreenTitle title="Chọn giờ ra ngoài" subtitle="Ngày mai, xét theo bụi mịn, khả năng mưa và nhiệt độ" />
      <SampleBanner />

      <SectionTitle>Thời lượng hoạt động</SectionTitle>
      <View style={styles.chips}>
        {DURATIONS.map(d => (
          <Chip key={d} label={`${d} phút`} selected={d === duration} onPress={() => setDuration(d)} />
        ))}
      </View>

      <SectionTitle>Khoảng giờ rảnh</SectionTitle>
      <View style={styles.chips}>
        {WINDOWS.map((w, i) => (
          <Chip key={w.label} label={w.label} selected={i === windowIndex} onPress={() => setWindowIndex(i)} />
        ))}
      </View>

      <SectionTitle>Gợi ý</SectionTitle>
      {result?.options.map((o, i) => (
        <Card key={o.start}>
          <Text style={styles.rank}>Lựa chọn {i + 1}</Text>
          <Text style={styles.time}>
            {vnTime(o.start)} – {vnTime(o.end)}
          </Text>
          <Text style={styles.reason}>{o.reason}</Text>
        </Card>
      ))}
      {result ? (
        <Card style={styles.ai}>
          <Text style={styles.aiTitle}>Giải thích{result.usedFallback ? ' (văn bản mẫu)' : ' bằng AI'}</Text>
          <Text style={styles.reason}>{result.explanation}</Text>
        </Card>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 16, marginBottom: 6 },
  rank: { fontSize: 12, color: colors.muted },
  time: { fontSize: 24, fontWeight: '700', color: colors.text, marginVertical: 2 },
  reason: { fontSize: 14, color: colors.text, lineHeight: 20 },
  ai: { backgroundColor: colors.accentSoft },
  aiTitle: { fontSize: 13, fontWeight: '700', color: colors.accent, marginBottom: 4 },
});
