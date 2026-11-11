import React, { useEffect, useRef, useState } from 'react';
import { Animated, Easing, Pressable, StyleSheet, View } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';

/** Fades and slides its children in when mounted; `delay` staggers lists. */
export function FadeIn({
  children,
  delay = 0,
  style,
}: {
  children: React.ReactNode;
  delay?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, {
      toValue: 1,
      duration: 560,
      delay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [v, delay]);
  const translateY = v.interpolate({ inputRange: [0, 1], outputRange: [22, 0] });
  return <Animated.View style={[style, { opacity: v, transform: [{ translateY }] }]}>{children}</Animated.View>;
}

/** Pressable that springs down slightly while pressed. */
export function PressScale({
  children,
  onPress,
  style,
  accessibilityLabel,
}: {
  children: React.ReactNode;
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
}) {
  const scale = useRef(new Animated.Value(1)).current;
  const to = (value: number) =>
    Animated.spring(scale, { toValue: value, useNativeDriver: true, speed: 40, bounciness: 6 }).start();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={onPress}
      onPressIn={() => to(0.965)}
      onPressOut={() => to(1)}>
      <Animated.View style={[style, { transform: [{ scale }] }]}>{children}</Animated.View>
    </Pressable>
  );
}

/** Counts a number up from 0, keeping the target's number of decimals. */
export function useCountUp(target: number | null, duration = 1000): string {
  const [shown, setShown] = useState(0);
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (target === null) {
      return;
    }
    v.setValue(0);
    const id = v.addListener(({ value }) => setShown(value));
    Animated.timing(v, {
      toValue: target,
      duration,
      easing: Easing.out(Easing.exp),
      useNativeDriver: false,
    }).start();
    return () => v.removeListener(id);
  }, [target, duration, v]);
  if (target === null) {
    return '–';
  }
  const decimals = Number.isInteger(target) ? 0 : 1;
  return shown.toFixed(decimals);
}

/** A dot with an expanding ring, used to show live data. */
export function Pulse({ color, size = 8 }: { color: string; size?: number }) {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(v, { toValue: 1, duration: 1600, easing: Easing.out(Easing.quad), useNativeDriver: true }),
    );
    loop.start();
    return () => loop.stop();
  }, [v]);
  const scale = v.interpolate({ inputRange: [0, 1], outputRange: [1, 2.8] });
  const opacity = v.interpolate({ inputRange: [0, 1], outputRange: [0.6, 0] });
  return (
    <View style={{ width: size, height: size }}>
      <Animated.View
        style={[
          StyleSheet.absoluteFill,
          { borderRadius: size, backgroundColor: color, opacity, transform: [{ scale }] },
        ]}
      />
      <View style={[StyleSheet.absoluteFill, { borderRadius: size, backgroundColor: color }]} />
    </View>
  );
}

/** Animated 0 → 1 value, started on mount (for gauges and bars). */
export function useGrow(delay = 0, duration = 900): Animated.Value {
  const v = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(v, {
      toValue: 1,
      duration,
      delay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [v, delay, duration]);
  return v;
}
