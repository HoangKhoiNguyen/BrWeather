package vn.brweather.util;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import vn.brweather.model.SeriesPoint;

class HourlySeriesTest {

    @Test
    void missingHoursAreNullNotZero() {
        Instant start = Instant.parse("2026-11-18T00:00:00Z");
        Map<Instant, Double> data = Map.of(
                Instant.parse("2026-11-18T00:00:00Z"), 40.0,
                Instant.parse("2026-11-18T02:00:00Z"), 55.5);

        List<SeriesPoint> s = HourlySeries.fill(data, start, 4);

        assertEquals(4, s.size());
        assertEquals(40.0, s.get(0).value());
        assertNull(s.get(1).value());
        assertEquals(55.5, s.get(2).value());
        assertNull(s.get(3).value());
        assertEquals(Instant.parse("2026-11-18T03:00:00Z"), s.get(3).time());
    }

    @Test
    void floorHourDropsMinutes() {
        assertEquals(Instant.parse("2026-11-18T09:00:00Z"), HourlySeries.floorHour(Instant.parse("2026-11-18T09:47:12Z")));
    }
}
