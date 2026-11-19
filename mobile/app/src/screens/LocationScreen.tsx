import Geolocation from '@react-native-community/geolocation';
import React, { useState } from 'react';
import { ActivityIndicator, Linking, PermissionsAndroid, ScrollView, StyleSheet, Text, View } from 'react-native';

import { FadeIn, PressScale } from '../components/anim';
import { Glass, SectionTitle } from '../components/ui';
import { DEFAULT_PLACE, DISTRICTS, useLocation } from '../location';
import type { Place } from '../location';
import { glass, pmColors, text } from '../theme';

// We ask for permission ourselves, only when the user taps "Dùng vị trí hiện tại"
Geolocation.setRNConfiguration({ skipPermissionRequests: true, authorizationLevel: 'whenInUse', locationProvider: 'auto' });

type Status = 'idle' | 'asking' | 'locating' | 'denied' | 'blocked' | 'error';

export default function LocationScreen({ onDone }: { onDone: () => void }) {
  const { place, setPlace } = useLocation();
  const [status, setStatus] = useState<Status>('idle');

  const choose = (p: Place) => {
    setPlace(p);
    onDone();
  };

  const useMyLocation = async () => {
    setStatus('asking');
    // Android 12+ lets the user choose "approximate" in this same dialog, so asking for both is still privacy-friendly
    const { ACCESS_FINE_LOCATION: FINE, ACCESS_COARSE_LOCATION: COARSE } = PermissionsAndroid.PERMISSIONS;
    const result = await PermissionsAndroid.requestMultiple([FINE, COARSE]);
    const granted = (p: typeof FINE | typeof COARSE) => result[p] === PermissionsAndroid.RESULTS.GRANTED;
    if (!granted(FINE) && !granted(COARSE)) {
      const blocked = [FINE, COARSE].some(p => result[p] === PermissionsAndroid.RESULTS.NEVER_ASK_AGAIN);
      setStatus(blocked ? 'blocked' : 'denied');
      return;
    }
    setStatus('locating');
    Geolocation.getCurrentPosition(
      pos => choose({ label: 'Vị trí của bạn', lat: pos.coords.latitude, lon: pos.coords.longitude, source: 'gps' }),
      err => {
        console.warn('Geolocation failed', err.code, err.message);
        setStatus('error');
      },
      // Precise permission: use GPS too (devices without network location, such as the emulator, need it)
      { enableHighAccuracy: granted(FINE), timeout: 20000, maximumAge: 5 * 60 * 1000 },
    );
  };

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.topBar}>
        <PressScale onPress={onDone} accessibilityLabel="Quay lại" style={styles.back}>
          <Text style={styles.backText}>‹</Text>
        </PressScale>
        <Text style={styles.topTitle}>Chọn địa điểm</Text>
      </View>

      <FadeIn>
        <Glass>
          <SectionTitle icon="📍">Đang xem</SectionTitle>
          <Text style={styles.current}>{place.label}</Text>
          <Text style={styles.meta}>
            {place.source === 'gps' ? 'Từ vị trí của bạn' : place.source === 'manual' ? 'Bạn chọn tay' : 'Mặc định'}
          </Text>
        </Glass>
      </FadeIn>

      <FadeIn delay={100}>
        <PressScale onPress={useMyLocation} accessibilityLabel="Dùng vị trí hiện tại" style={styles.gpsButton}>
          {status === 'asking' || status === 'locating' ? (
            <ActivityIndicator color="#0B1530" />
          ) : (
            <Text style={styles.gpsText}>🛰️  Dùng vị trí hiện tại</Text>
          )}
        </PressScale>
        <Text style={styles.privacy}>Chỉ hỏi quyền khi bạn bấm nút này. Có thể chọn tay bên dưới nếu không muốn chia sẻ vị trí.</Text>
        {status === 'denied' || status === 'blocked' || status === 'error' ? (
          <View style={styles.notice}>
            <Text style={styles.noticeText}>
              {status === 'error'
                ? 'Không lấy được vị trí (GPS tắt hoặc hết thời gian chờ). Hãy chọn khu vực bên dưới.'
                : 'Bạn chưa cho phép dùng vị trí. Hãy chọn khu vực bên dưới.'}
            </Text>
            {status === 'blocked' ? (
              <PressScale onPress={() => Linking.openSettings()} style={styles.settings}>
                <Text style={styles.settingsText}>Mở cài đặt quyền của app</Text>
              </PressScale>
            ) : null}
          </View>
        ) : null}
      </FadeIn>

      <FadeIn delay={200}>
        <Glass style={styles.listCard}>
          <View style={styles.listHead}>
            <SectionTitle icon="🗺️">Chọn khu vực</SectionTitle>
          </View>
          {[DEFAULT_PLACE, ...DISTRICTS].map((p, i, all) => {
            const selected = p.label === place.label && place.source !== 'gps';
            return (
              <PressScale
                key={p.label}
                onPress={() => choose(p)}
                accessibilityLabel={`Chọn ${p.label}`}
                style={[styles.row, i < all.length - 1 && styles.rowLine]}>
                <Text style={styles.rowText}>{p.label}</Text>
                {selected ? <Text style={styles.check}>✓</Text> : null}
              </PressScale>
            );
          })}
        </Glass>
      </FadeIn>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: 140 },
  topBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 10, paddingBottom: 14, gap: 12 },
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
  topTitle: { fontSize: 22, fontWeight: '700', color: text.primary },
  current: { fontSize: 24, fontWeight: '700', color: text.primary },
  meta: { fontSize: 12, color: text.faint, marginTop: 4 },
  gpsButton: {
    marginHorizontal: 16,
    paddingVertical: 15,
    borderRadius: 18,
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    boxShadow: '0 8px 22px rgba(0,0,0,0.25)',
  },
  gpsText: { fontSize: 16, fontWeight: '800', color: text.dark },
  privacy: { fontSize: 11, color: text.faint, textAlign: 'center', marginTop: 8, marginBottom: 12, paddingHorizontal: 28 },
  notice: {
    marginHorizontal: 16,
    marginBottom: 14,
    padding: 12,
    borderRadius: 14,
    backgroundColor: 'rgba(250,204,21,0.16)',
    borderWidth: 1,
    borderColor: 'rgba(250,204,21,0.45)',
  },
  noticeText: { fontSize: 13, lineHeight: 19, color: text.primary },
  settings: { marginTop: 8, alignSelf: 'flex-start' },
  settingsText: { fontSize: 13, fontWeight: '800', color: pmColors.moderate },
  listCard: { paddingHorizontal: 0, paddingBottom: 4 },
  listHead: { paddingHorizontal: 18 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 13, paddingHorizontal: 18 },
  rowLine: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: glass.border },
  rowText: { fontSize: 16, color: text.primary },
  check: { fontSize: 18, fontWeight: '800', color: pmColors.good },
});
