package vn.brweather.model;

import java.time.Instant;
import java.util.List;

/**
 * Everything the station detail screen needs in one call (GET /stations/{id}/detail, F02–F04).
 * forecast, forecastIssuedAt and modelVersion are null when the station has no forecast yet.
 */
public record StationDetail(
        List<SeriesPoint> history,
        List<SeriesPoint> forecast,
        Instant forecastIssuedAt,
        String modelVersion,
        List<Anomaly> anomalies) {

    public record Anomaly(long id, Instant time, String category, String description) {
    }
}
