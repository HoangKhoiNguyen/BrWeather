package vn.brweather.service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import java.util.function.Function;

import vn.brweather.model.Weather;
import vn.brweather.repository.WeatherRepository.HourRow;

/**
 * Pure functions that turn the hourly rows of one snapshot into the current / hourly / daily blocks.
 * Kept free of Spring and the database so they can be unit tested.
 */
public final class WeatherAggregator {

    /** Days are calendar days in Vietnam time (UTC+7), not the UTC days Open-Meteo returned. */
    public static final ZoneId VN = ZoneId.of("Asia/Ho_Chi_Minh");

    /** A day with fewer hours than this is cut off by the snapshot window and is left out. */
    static final int MIN_HOURS_PER_DAY = 12;

    private WeatherAggregator() {
    }

    /** The row for the current hour, or the latest earlier row if that hour is missing; null if none. */
    public static HourRow current(List<HourRow> rows, Instant now) {
        Instant hour = now.truncatedTo(ChronoUnit.HOURS);
        HourRow best = null;
        for (HourRow r : rows) {
            if (!r.validTime().isAfter(hour) && (best == null || r.validTime().isAfter(best.validTime()))) {
                best = r;
            }
        }
        return best;
    }

    /** Up to {@code count} rows starting at the current hour. */
    public static List<Weather.Hour> nextHours(List<HourRow> rows, Instant now, int count) {
        Instant hour = now.truncatedTo(ChronoUnit.HOURS);
        return rows.stream()
                .filter(r -> !r.validTime().isBefore(hour))
                .sorted((a, b) -> a.validTime().compareTo(b.validTime()))
                .limit(count)
                .map(r -> new Weather.Hour(r.validTime(), r.temperatureC(), r.precipitationProbPct(), r.weatherCode()))
                .toList();
    }

    /**
     * Daily summary from today (Vietnam time) onward, at most {@code maxDays} days.
     * max/min temperature, total precipitation, and the highest WMO code of the day
     * (higher codes are worse weather, so it shows the day's worst). Null when no hour had a value.
     */
    public static List<Weather.Day> daily(List<HourRow> rows, Instant now, int maxDays) {
        LocalDate today = now.atZone(VN).toLocalDate();
        Map<LocalDate, List<HourRow>> byDay = new TreeMap<>();
        for (HourRow r : rows) {
            LocalDate d = r.validTime().atZone(VN).toLocalDate();
            if (!d.isBefore(today)) {
                byDay.computeIfAbsent(d, k -> new ArrayList<>()).add(r);
            }
        }
        List<Weather.Day> out = new ArrayList<>();
        for (Map.Entry<LocalDate, List<HourRow>> e : byDay.entrySet()) {
            List<HourRow> hours = e.getValue();
            if (hours.size() < MIN_HOURS_PER_DAY || out.size() >= maxDays) {
                continue;
            }
            List<Double> temps = values(hours, HourRow::temperatureC);
            List<Double> rain = values(hours, HourRow::precipitationMm);
            Integer code = hours.stream().map(HourRow::weatherCode).filter(Objects::nonNull)
                    .max(Integer::compare).orElse(null);
            out.add(new Weather.Day(e.getKey(),
                    temps.stream().max(Double::compare).orElse(null),
                    temps.stream().min(Double::compare).orElse(null),
                    rain.isEmpty() ? null : round1(rain.stream().mapToDouble(Double::doubleValue).sum()),
                    code));
        }
        return out;
    }

    private static List<Double> values(List<HourRow> hours, Function<HourRow, Double> f) {
        return hours.stream().map(f).filter(Objects::nonNull).toList();
    }

    private static double round1(double v) {
        return Math.round(v * 10) / 10.0;
    }
}
