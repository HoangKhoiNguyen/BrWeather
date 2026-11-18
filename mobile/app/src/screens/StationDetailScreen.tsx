import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import { getStationDetail } from '../api/client';
import type { Anomaly, StationDetail, StationSummary } from '../api/types';
import { FadeIn, PressScale, useCountUp } from '../components/anim';
import {
  BarChart,
  ChartLegend,
  FarWarning,
  Glass,
  PmGauge,
  ReliabilityPill,
  SectionTitle,
  vnDay,
  vnTime,
} from '../components/ui';
import { PM_SCALE_NAME, glass, pm25Level, pmColors, text } from '../theme';

const CATEGORY: Record<Anomaly['category'], { label: string; color: string; icon: string }> = {
  environment: { label: 'Ô nhiễm tăng thật', color: pmColors.veryHigh, icon: '⚠️' },
  data: { label: 'Lỗi dữ liệu', color: pmColors.none, icon: '🛠️' },
  needs_review: { label: 'Cần kiểm tra', color: pmColors.moderate, icon: '🔍' },
};

export default function StationDetailScreen({ station, onBack }: { station: StationSummary; onBack: () => void }) {
  const [detail, setDetail] = useState<StationDetail | null>(null);
  const shown = useCountUp(station.latest.pm25);
  const level = pm25Level(station.latest.pm25);

  useEffect(() => {
    getStationDetail(station.id).then(setDetail);
  }, [station.id]);

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.topBar}>
        <PressScale onPress={onBack} accessibilityLabel="Quay lại" style={styles.back}>
          <Text style={styles.backText}>‹</Text>
        </PressScale>
        <Text style={styles.topTitle} numberOfLines={1}>
          {station.name}
        </Text>
      </View>

      <FadeIn style={styles.hero}>
        <Text style={styles.value}>{shown}</Text>
        <Text style={styles.unit}>µg/m³ PM2.5</Text>
        <Text style={[styles.level, { color: level.color }]}>{level.label}</Text>
        <Text style={styles.advice}>{level.advice}</Text>
      </FadeIn>

      <FadeIn delay={100}>
        <Glass>
          <PmGauge value={station.latest.pm25} />
          <Text style={styles.note}>{PM_SCALE_NAME}</Text>
          <FarWarning km={station.distanceKm} />
          <View style={styles.footRow}>
            <ReliabilityPill level={station.latest.reliability} />
            <Text style={styles.meta}>
              {station.latest.source} · cách bạn {station.distanceKm} km
            </Text>
          </View>
        </Glass>
      </FadeIn>

      {!detail ? <ActivityIndicator color="#fff" style={styles.loading} /> : null}
      {detail ? (
        <>
          <FadeIn delay={200}>
            <Glass>
              <SectionTitle icon="📈">24 giờ qua</SectionTitle>
              <BarChart data={detail.history} />
              <Text style={styles.note}>Số đo OpenAQ · khoảng trống là giờ không có dữ liệu</Text>
            </Glass>
          </FadeIn>

          <FadeIn delay={320}>
            <Glass style={styles.forecastCard}>
              <SectionTitle icon="🔮">Dự báo 24 giờ tới</SectionTitle>
              {detail.forecast && detail.forecastIssuedAt ? (
                <>
                  <ChartLegend />
                  <BarChart data={detail.forecast} variant="forecast" />
                  <Text style={styles.note}>
                    Dự báo, không phải số đo · phát hành {vnTime(detail.forecastIssuedAt)} ({vnDay(detail.forecastIssuedAt)})
                    {detail.modelVersion ? ` · mô hình ${detail.modelVersion}` : ''}
                  </Text>
                </>
              ) : (
                <View style={styles.noForecast}>
                  <Text style={styles.noForecastTitle}>Chưa có dự báo</Text>
                  <Text style={styles.note}>
                    Trạm này chưa đủ dữ liệu lịch sử để dự báo. Số đo hiện tại và 24 giờ qua vẫn hiển thị bình thường.
                  </Text>
                </View>
              )}
            </Glass>
          </FadeIn>

          <FadeIn delay={440}>
            <Glass>
              <SectionTitle icon="🧭">Bất thường gần đây</SectionTitle>
              {detail.anomalies.map(a => (
                <View key={a.id} style={[styles.anomaly, { borderLeftColor: CATEGORY[a.category].color }]}>
                  <View style={styles.anomalyHead}>
                    <Text style={[styles.anomalyLabel, { color: CATEGORY[a.category].color }]}>
                      {CATEGORY[a.category].icon} {CATEGORY[a.category].label}
                    </Text>
                    <Text style={styles.meta}>{vnTime(a.time)}</Text>
                  </View>
                  <Text style={styles.body}>{a.description}</Text>
                </View>
              ))}
            </Glass>
          </FadeIn>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 140 },
  topBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 10, gap: 12 },
  back: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: glass.strong,
    borderWidth: 1,
    borderColor: glass.border,
  },
  backText: { fontSize: 28, color: text.primary, marginTop: -4 },
  topTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: text.primary },
  hero: { alignItems: 'center', paddingVertical: 18 },
  value: { fontSize: 96, fontWeight: '200', color: text.primary, lineHeight: 104 },
  unit: { fontSize: 14, color: text.secondary },
  level: { fontSize: 24, fontWeight: '800', marginTop: 6 },
  advice: { fontSize: 14, color: text.secondary, textAlign: 'center', marginTop: 4, paddingHorizontal: 40 },
  footRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, gap: 8 },
  meta: { fontSize: 12, color: text.faint },
  note: { fontSize: 11, color: text.faint, marginTop: 10 },
  loading: { marginTop: 30 },
  forecastCard: { borderStyle: 'dashed', borderColor: 'rgba(255,255,255,0.35)' },
  noForecast: { paddingVertical: 8 },
  noForecastTitle: { fontSize: 17, fontWeight: '700', color: text.primary },
  anomaly: {
    borderLeftWidth: 3,
    paddingLeft: 12,
    paddingVertical: 6,
    marginBottom: 12,
    borderRadius: 4,
  },
  anomalyHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  anomalyLabel: { fontSize: 13, fontWeight: '800' },
  body: { fontSize: 14, lineHeight: 20, color: text.primary, marginTop: 4 },
});
