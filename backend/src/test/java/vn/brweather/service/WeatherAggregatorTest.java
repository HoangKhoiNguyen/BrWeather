package vn.brweather.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.Test;

import vn.brweather.model.Weather;
import vn.brweather.repository.WeatherRepository.HourRow;

class WeatherAggregatorTest {

    private static HourRow row(Instant t, Double temp, Double rain, Integer code) {
        return new HourRow(t, temp, temp, 80.0, rain, 20.0, code, 10.0, 90.0, 1.0);
    }

    /** 48 hourly rows from 2026-11-18T00:00Z; temperature = hour index, 0.5 mm rain each hour. */
    private static List<HourRow> twoUtcDays() {
        Instant start = Instant.parse("2026-11-18T00:00:00Z");
        List<HourRow> rows = new ArrayList<>();
        for (int i = 0; i < 48; i++) {
            rows.add(row(start.plus(Duration.ofHours(i)), (double) i, 0.5, i == 20 ? 63 : 3));
        }
        return rows;
    }

    @Test
    void currentPicksThisHourOrTheLatestEarlierOne() {
        List<HourRow> rows = twoUtcDays();
        assertEquals(Instant.parse("2026-11-18T05:00:00Z"),
                WeatherAggregator.current(rows, Instant.parse("2026-11-18T05:40:00Z")).validTime());
        assertNull(WeatherAggregator.current(rows, Instant.parse("2026-11-17T23:00:00Z")));
    }

    @Test
    void nextHoursStartsAtCurrentHourAndStopsAt24() {
        List<Weather.Hour> h = WeatherAggregator.nextHours(twoUtcDays(), Instant.parse("2026-11-18T05:40:00Z"), 24);
        assertEquals(24, h.size());
        assertEquals(Instant.parse("2026-11-18T05:00:00Z"), h.get(0).time());
        assertEquals(Instant.parse("2026-11-19T04:00:00Z"), h.get(23).time());
    }

    @Test
    void dailyUsesVietnamCalendarDays() {
        // now = 2026-11-18 08:00 VN. Rows cover VN 07:00 on the 18th to 06:00 on the 20th.
        List<Weather.Day> d = WeatherAggregator.daily(twoUtcDays(), Instant.parse("2026-11-18T01:00:00Z"), 7);

        // 18th VN: UTC hours 0..16 (17 rows) -> kept. 19th VN: UTC 17..40 (24 rows). 20th VN: 7 rows -> dropped.
        assertEquals(2, d.size());
        Weather.Day first = d.get(0);
        assertEquals(LocalDate.of(2026, 11, 18), first.date());
        assertEquals(16.0, first.maxC());
        assertEquals(0.0, first.minC());
        assertEquals(8.5, first.precipitationMm());
        assertEquals(3, first.weatherCode());

        Weather.Day second = d.get(1);
        assertEquals(LocalDate.of(2026, 11, 19), second.date());
        assertEquals(40.0, second.maxC());
        assertEquals(17.0, second.minC());
        assertEquals(12.0, second.precipitationMm());
        assertEquals(63, second.weatherCode(), "the worst code of the day wins");
    }

    @Test
    void allNullValuesStayNull() {
        Instant start = Instant.parse("2026-11-18T17:00:00Z"); // 00:00 VN on the 19th
        List<HourRow> rows = new ArrayList<>();
        for (int i = 0; i < 24; i++) {
            rows.add(row(start.plus(Duration.ofHours(i)), null, null, null));
        }
        Weather.Day day = WeatherAggregator.daily(rows, start, 7).get(0);
        assertNull(day.maxC());
        assertNull(day.minC());
        assertNull(day.precipitationMm());
        assertNull(day.weatherCode());
    }
}
