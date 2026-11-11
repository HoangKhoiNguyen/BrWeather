import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, Dimensions, Easing, StyleSheet, Text, View } from 'react-native';

import { skies } from '../theme';
import type { SkyKind } from '../theme';

const { width: W, height: H } = Dimensions.get('window');

// Deterministic pseudo-random numbers so particles don't jump between renders
function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

function useLoop(duration: number, delay = 0, easing = Easing.linear) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.delay(delay),
        Animated.timing(v, { toValue: 1, duration, easing, useNativeDriver: true }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [v, duration, delay, easing]);
  return v;
}

function RainDrop({ x, delay, duration, length }: { x: number; delay: number; duration: number; length: number }) {
  const v = useLoop(duration, delay);
  const translateY = v.interpolate({ inputRange: [0, 1], outputRange: [-60, H + 40] });
  return (
    <Animated.View
      style={[
        styles.drop,
        { left: x, height: length, transform: [{ translateY }, { rotate: '12deg' }] },
      ]}
    />
  );
}

function Star({ x, y, size, delay }: { x: number; y: number; size: number; delay: number }) {
  const v = useLoop(2400, delay, Easing.inOut(Easing.sin));
  const opacity = v.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0.25, 1, 0.25] });
  return <Animated.View style={[styles.star, { left: x, top: y, width: size, height: size, opacity }]} />;
}

function DriftCloud({ top, size, duration, delay, opacity }: { top: number; size: number; duration: number; delay: number; opacity: number }) {
  const v = useLoop(duration, delay);
  const translateX = v.interpolate({ inputRange: [0, 1], outputRange: [-size * 1.6, W + size * 0.2] });
  return (
    <Animated.Text style={[styles.cloud, { top, fontSize: size, opacity, transform: [{ translateX }] }]}>
      ☁️
    </Animated.Text>
  );
}

/** Full-screen sky gradient plus weather particles. Sits behind all screens. */
export function SkyBackground({ kind }: { kind: SkyKind }) {
  const rain = useMemo(() => {
    const r = seeded(7);
    return Array.from({ length: 34 }, (_, i) => ({
      key: i,
      x: r() * W,
      delay: r() * 1400,
      duration: 650 + r() * 500,
      length: 14 + r() * 16,
    }));
  }, []);
  const stars = useMemo(() => {
    const r = seeded(11);
    return Array.from({ length: 36 }, (_, i) => ({
      key: i,
      x: r() * W,
      y: r() * H * 0.55,
      size: 1.5 + r() * 2,
      delay: r() * 2400,
    }));
  }, []);

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <View style={[StyleSheet.absoluteFill, { backgroundImage: skies[kind] }]} />
      {kind === 'clear-day' ? <View style={[StyleSheet.absoluteFill, styles.sunGlow]} /> : null}
      {kind === 'sunset' ? <View style={[StyleSheet.absoluteFill, styles.sunsetGlow]} /> : null}
      {kind === 'night' ? stars.map(s => <Star key={s.key} x={s.x} y={s.y} size={s.size} delay={s.delay} />) : null}
      {kind !== 'night' ? (
        <>
          <DriftCloud top={H * 0.08} size={110} duration={48000} delay={0} opacity={kind === 'clear-day' ? 0.22 : 0.35} />
          <DriftCloud top={H * 0.22} size={80} duration={36000} delay={9000} opacity={kind === 'clear-day' ? 0.16 : 0.28} />
          {kind !== 'clear-day' ? (
            <DriftCloud top={H * 0.02} size={140} duration={60000} delay={20000} opacity={0.3} />
          ) : null}
        </>
      ) : null}
      {kind === 'rain'
        ? rain.map(d => <RainDrop key={d.key} x={d.x} delay={d.delay} duration={d.duration} length={d.length} />)
        : null}
    </View>
  );
}

/** Large animated weather symbol for the hero area. */
export function WeatherHeroIcon({ code, night, size = 120 }: { code: number | null; night: boolean; size?: number }) {
  const spin = useLoop(24000);
  const float = useLoop(3600, 0, Easing.inOut(Easing.sin));
  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  const translateY = float.interpolate({ inputRange: [0, 0.5, 1], outputRange: [0, -8, 0] });
  const raining = code !== null && code >= 51;
  const cloudy = code === 2 || code === 3;

  if (night) {
    return (
      <Animated.View style={[styles.hero, { width: size, height: size, transform: [{ translateY }] }]}>
        <View style={[styles.moonGlow, { width: size * 0.9, height: size * 0.9, borderRadius: size }]} />
        <Text style={{ fontSize: size * 0.62 }}>🌙</Text>
      </Animated.View>
    );
  }
  if (raining) {
    return (
      <View style={[styles.hero, { width: size, height: size }]}>
        <Animated.Text style={{ fontSize: size * 0.68, transform: [{ translateY }] }}>🌧️</Animated.Text>
      </View>
    );
  }
  const core = size * 0.46;
  return (
    <View style={[styles.hero, { width: size, height: size }]}>
      <Animated.View style={[StyleSheet.absoluteFill, styles.center, { transform: [{ rotate }] }]}>
        {Array.from({ length: 10 }, (_, i) => (
          <View
            key={i}
            style={[
              styles.ray,
              {
                height: size * 0.16,
                transform: [{ rotate: `${i * 36}deg` }, { translateY: -size * 0.38 }],
              },
            ]}
          />
        ))}
      </Animated.View>
      <View style={[styles.sun, { width: core, height: core, borderRadius: core }]} />
      {cloudy ? (
        <Animated.Text style={[styles.heroCloud, { fontSize: size * 0.5, transform: [{ translateY }] }]}>
          ☁️
        </Animated.Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  drop: {
    position: 'absolute',
    top: 0,
    width: 1.6,
    borderRadius: 1,
    backgroundColor: 'rgba(200,225,255,0.45)',
  },
  star: { position: 'absolute', borderRadius: 4, backgroundColor: '#FFFFFF' },
  cloud: { position: 'absolute', left: 0 },
  sunGlow: {
    backgroundImage: 'radial-gradient(circle at 85% 8%, rgba(255,231,140,0.55) 0%, rgba(255,231,140,0) 42%)',
  },
  sunsetGlow: {
    backgroundImage: 'radial-gradient(circle at 50% 100%, rgba(255,170,90,0.55) 0%, rgba(255,170,90,0) 55%)',
  },
  hero: { alignItems: 'center', justifyContent: 'center' },
  center: { alignItems: 'center', justifyContent: 'center' },
  ray: { position: 'absolute', width: 5, borderRadius: 3, backgroundColor: 'rgba(255,214,90,0.9)' },
  sun: {
    backgroundColor: '#FFC93C',
    backgroundImage: 'radial-gradient(circle at 35% 35%, #FFF7C2 0%, #FFD54A 55%, #FFAA00 100%)',
    boxShadow: '0 0 36px 8px rgba(255,190,60,0.65)',
  },
  heroCloud: { position: 'absolute', bottom: 2, right: -6 },
  moonGlow: {
    position: 'absolute',
    backgroundImage: 'radial-gradient(circle, rgba(200,220,255,0.35) 0%, rgba(200,220,255,0) 70%)',
  },
});
