import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { getStationDetail } from '../api/client';
import type { Anomaly, StationDetail, StationSummary } from '../api/types';
import { BarChart, Card, Pill, ReliabilityPill, SectionTitle, colors, fmt, pm25Level, vnTime } from '../components/ui';

const CATEGORY: Record<Anomaly['category'], { label: string; color: string }> = {
  environment: { label: 'Ô nhiễm tăng thật', color: colors.veryHigh },
  data: { label: 'Lỗi dữ liệu', color: colors.none },
  needs_review: { label: 'Cần kiểm tra', color: colors.moderate },
};

export default function StationDetailScreen({ station, onBack }: { station: StationSummary; onBack: () => void }) {
  const [detail, setDetail] = useState<StationDetail | null>(null);

  useEffect(() => {
    getStationDetail(station.id).then(setDetail);
  }, [station.id]);

  const level = pm25Level(station.latest.pm25);

  return (
    <ScrollView>
      <Pressable accessibilityRole="button" onPress={onBack} style={styles.back}>
        <Text style={styles.backText}>‹ Quay lại</Text>
      </Pressable>
      <Text style={styles.title}>{station.name}</Text>
      <Card>
        <Text style={styles.value}>
          {fmt(station.latest.pm25)} <Text style={styles.unit}>{station.latest.unit}</Text>
        </Text>
        <View style={styles.pills}>
          <Pill label={level.label} color={level.color} />
          <ReliabilityPill level={station.latest.reliability} />
        </View>
      </Card>

      {!detail ? <ActivityIndicator color={colors.accent} /> : null}
      {detail ? (
        <>
          <SectionTitle>24 giờ qua</SectionTitle>
          <Card>
            <BarChart data={detail.history} />
            <Text style={styles.meta}>Số đo OpenAQ. Khoảng trống là giờ không có dữ liệu.</Text>
          </Card>

          <SectionTitle>Dự báo 24 giờ tới</SectionTitle>
          <Card>
            <BarChart data={detail.forecast} />
            <Text style={styles.meta}>
              Phát hành {vnTime(detail.forecastIssuedAt)} · Mô hình {detail.modelVersion}
            </Text>
          </Card>

          <SectionTitle>Bất thường gần đây</SectionTitle>
          {detail.anomalies.map(a => (
            <Card key={a.id}>
              <View style={styles.anomalyHead}>
                <Pill label={CATEGORY[a.category].label} color={CATEGORY[a.category].color} />
                <Text style={styles.meta}>{vnTime(a.time)}</Text>
              </View>
              <Text style={styles.body}>{a.description}</Text>
            </Card>
          ))}
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  back: { paddingHorizontal: 16, paddingVertical: 12 },
  backText: { fontSize: 16, color: colors.accent, fontWeight: '600' },
  title: { fontSize: 22, fontWeight: '700', color: colors.text, marginHorizontal: 16, marginBottom: 12 },
  value: { fontSize: 40, fontWeight: '700', color: colors.text },
  unit: { fontSize: 15, fontWeight: '400', color: colors.muted },
  pills: { flexDirection: 'row', gap: 6, marginTop: 6 },
  meta: { fontSize: 12, color: colors.muted, marginTop: 6 },
  body: { fontSize: 14, color: colors.text, marginTop: 8 },
  anomalyHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
});
