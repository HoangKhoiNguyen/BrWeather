package vn.brweather.util;

import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import vn.brweather.model.SeriesPoint;

/** Builds fixed hourly series so the chart always has one slot per hour, with null for gaps. */
public final class HourlySeries {

    private HourlySeries() {
    }

    public static Instant floorHour(Instant t) {
        return t.truncatedTo(ChronoUnit.HOURS);
    }

    /**
     * {@code hours} consecutive slots starting at {@code start} (already on the hour).
     * A slot missing from {@code byHour} gets value null, never 0.
     */
    public static List<SeriesPoint> fill(Map<Instant, Double> byHour, Instant start, int hours) {
        List<SeriesPoint> out = new ArrayList<>(hours);
        for (int i = 0; i < hours; i++) {
            Instant slot = start.plus(Duration.ofHours(i));
            out.add(new SeriesPoint(slot, byHour.get(slot)));
        }
        return out;
    }
}
