import React, { useEffect, useState } from 'react';
import { BackHandler, Pressable, StatusBar, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import type { StationSummary } from './src/api/types';
import { colors } from './src/components/ui';
import AlertsScreen from './src/screens/AlertsScreen';
import OverviewScreen from './src/screens/OverviewScreen';
import PlannerScreen from './src/screens/PlannerScreen';
import StationDetailScreen from './src/screens/StationDetailScreen';
import WeatherScreen from './src/screens/WeatherScreen';

type Tab = 'overview' | 'weather' | 'planner' | 'alerts';

const TABS: Array<{ id: Tab; label: string; icon: string }> = [
  { id: 'overview', label: 'Không khí', icon: '🌫️' },
  { id: 'weather', label: 'Thời tiết', icon: '⛅' },
  { id: 'planner', label: 'Chọn giờ', icon: '🕒' },
  { id: 'alerts', label: 'Cảnh báo', icon: '🔔' },
];

function Main() {
  const insets = useSafeAreaInsets();
  const [tab, setTab] = useState<Tab>('overview');
  const [station, setStation] = useState<StationSummary | null>(null);

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

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.content}>
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
      </View>
      <View style={[styles.tabBar, { paddingBottom: insets.bottom }]}>
        {TABS.map(t => {
          const active = t.id === tab;
          return (
            <Pressable
              key={t.id}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              onPress={() => selectTab(t.id)}
              style={styles.tab}>
              <Text style={styles.tabIcon}>{t.icon}</Text>
              <Text style={[styles.tabLabel, active && styles.tabLabelOn]}>{t.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="dark-content" />
      <Main />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 8 },
  tabIcon: { fontSize: 18 },
  tabLabel: { fontSize: 11, color: colors.muted, marginTop: 2 },
  tabLabelOn: { color: colors.accent, fontWeight: '700' },
});
