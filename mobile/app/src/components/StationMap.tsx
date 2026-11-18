import { Camera, Map, Marker } from '@maplibre/maplibre-react-native';
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { StationSummary } from '../api/types';
import type { Place } from '../location';
import { glass, pm25Level, text } from '../theme';

// OpenFreeMap serves OpenStreetMap vector tiles without an API key
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';

/** Stations coloured by PM2.5; stations without data are grey. Tapping one opens its detail (T2.2-1, T2.2-2). */
export function StationMap({
  stations,
  place,
  onOpen,
}: {
  stations: StationSummary[];
  place: Place;
  onOpen: (s: StationSummary) => void;
}) {
  return (
    <View style={styles.wrap}>
      <Map style={StyleSheet.absoluteFill} mapStyle={MAP_STYLE} logo={false} compass={false} attribution>
        <Camera center={[place.lon, place.lat]} zoom={10.4} />
        <Marker id="place" lngLat={[place.lon, place.lat]}>
          <View style={styles.me}>
            <View style={styles.meDot} />
          </View>
        </Marker>
        {stations.map(s => {
          const level = pm25Level(s.latest.pm25);
          return (
            <Marker key={s.id} id={`station-${s.id}`} lngLat={[s.lon, s.lat]} onPress={() => onOpen(s)}>
              <View
                accessibilityLabel={`Trạm ${s.name}, ${s.latest.pm25 === null ? 'không có dữ liệu' : `${s.latest.pm25} microgam`}`}
                style={[
                  styles.pin,
                  { backgroundColor: level.color },
                  s.latest.status === 'stale' && styles.pinStale,
                ]}>
                <Text style={styles.pinText}>{s.latest.pm25 === null ? '–' : Math.round(s.latest.pm25)}</Text>
              </View>
            </Marker>
          );
        })}
      </Map>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    height: 280,
    marginHorizontal: 16,
    marginBottom: 14,
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: glass.border,
    backgroundColor: glass.bg,
  },
  pin: {
    minWidth: 34,
    height: 34,
    paddingHorizontal: 6,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#FFFFFF',
    boxShadow: '0 2px 6px rgba(0,0,0,0.35)',
  },
  pinStale: { opacity: 0.55 },
  pinText: { fontSize: 13, fontWeight: '800', color: text.dark },
  me: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: 'rgba(59,130,246,0.25)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  meDot: { width: 12, height: 12, borderRadius: 6, backgroundColor: '#3B82F6', borderWidth: 2, borderColor: '#FFFFFF' },
});
