import React, { useEffect, useRef, useState } from 'react';
import { Animated, BackHandler, Pressable, StatusBar, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import { getWeather } from './src/api/client';
import type { StationSummary } from './src/api/types';
import { FadeIn } from './src/components/anim';
import { SkyBackground } from './src/components/sky';
import AlertsScreen from './src/screens/AlertsScreen';
import OverviewScreen from './src/screens/OverviewScreen';
import PlannerScreen from './src/screens/PlannerScreen';
import StationDetailScreen from './src/screens/StationDetailScreen';
import WeatherScreen from './src/screens/WeatherScreen';
import { glass, skyFor, text } from './src/theme';
import type { SkyKind } from './src/theme';

type Tab = 'overview' | 'weather' | 'planner' | 'alerts';

const TABS: Array<{ id: Tab; label: string; icon: string }> = [
  { id: 'overview', label: 'Không khí', icon: '🌫️' },
  { id: 'weather', label: 'Thời tiết', icon: '⛅' },
  { id: 'planner', label: 'Chọn giờ', icon: '🏃' },
  { id: 'alerts', label: 'Cảnh báo', icon: '🔔' },
];

function TabBar({ tab, onSelect, bottom }: { tab: Tab; onSelect: (t: Tab) => void; bottom: number }) {
  const [width, setWidth] = useState(0);
  const index = TABS.findIndex(t => t.id === tab);
  const x = useRef(new Animated.Value(0)).current;
  const tabWidth = width / TABS.length;

  useEffect(() => {
    Animated.spring(x, { toValue: index * tabWidth, useNativeDriver: true, speed: 18, bounciness: 8 }).start();
  }, [index, tabWidth, x]);

  return (
    <View style={[styles.tabBar, { bottom: bottom + 10 }]} onLayout={e => setWidth(e.nativeEvent.layout.width - 12)}>
      {width > 0 ? (
        <Animated.View style={[styles.indicator, { width: tabWidth, transform: [{ translateX: x }] }]} />
      ) : null}
      {TABS.map(t => {
        const active = t.id === tab;
        return (
          <Pressable
            key={t.id}
            accessibilityRole="tab"
            accessibilityLabel={t.label}
            accessibilityState={{ selected: active }}
            onPress={() => onSelect(t.id)}
            style={styles.tab}>
            <Text style={[styles.tabIcon, active && styles.tabIconOn]}>{t.icon}</Text>
            <Text style={[styles.tabLabel, active && styles.tabLabelOn]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function Main() {
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState<Tab>('overview');
  const [station, setStation] = useState<StationSummary | null>(null);
  const [sky, setSky] = useState<SkyKind>('clear-day');

  // The whole app sits under a sky that follows the current weather and time of day
  useEffect(() => {
    getWeather().then(w => setSky(skyFor(w.current.weatherCode, w.fetchedAt)));
  }, []);

  // Android back button leaves the station detail instead of closing the app
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (station) {
        setStation(null);
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [station]);

  const selectTab = (id: Tab) => {
    setStation(null);
    setTab(id);
  };

  const screenKey = station ? `station-${station.id}` : tab;

  return (
    <View style={styles.root}>
      <SkyBackground kind={sky} />
      <View style={[styles.content, { paddingTop: insets.top }]}>
        <FadeIn key={screenKey} style={styles.content}>
          {station ? (
            <StationDetailScreen station={station} onBack={() => setStation(null)} />
          ) : tab === 'overview' ? (
            <OverviewScreen onOpen={setStation} />
          ) : tab === 'weather' ? (
            <WeatherScreen />
          ) : tab === 'planner' ? (
            <PlannerScreen />
          ) : (
            <AlertsScreen />
          )}
        </FadeIn>
      </View>
      <TabBar tab={tab} onSelect={selectTab} bottom={insets.bottom} />
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" />
      <Main />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0B1530' },
  content: { flex: 1 },
  tabBar: {
    position: 'absolute',
    left: 16,
    right: 16,
    flexDirection: 'row',
    padding: 6,
    borderRadius: 28,
    backgroundColor: 'rgba(12,24,50,0.94)',
    borderWidth: 1,
    borderColor: glass.border,
    boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
  },
  indicator: {
    position: 'absolute',
    top: 6,
    bottom: 6,
    left: 6,
    borderRadius: 22,
    backgroundColor: 'rgba(255,255,255,0.16)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.22)',
  },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 8 },
  tabIcon: { fontSize: 20, opacity: 0.7 },
  tabIconOn: { opacity: 1, transform: [{ scale: 1.12 }] },
  tabLabel: { fontSize: 11, color: text.faint, marginTop: 2, fontWeight: '600' },
  tabLabelOn: { color: text.primary, fontWeight: '800' },
});
