package vn.brweather.model;

import java.time.Instant;

/** One station with its latest PM2.5 reading, as returned by GET /api/v1/stations (F01). */
public record StationSummary(
        long id,
        String name,
        double lat,
        double lon,
        Latest latest) {

    /** value is null when there is no reading; status is ok | stale | missing. */
    public record Latest(
            Double pm25,
            String unit,
            Instant measuredAt,
            String source,
            String kind,
            String reliability,
            String status) {
    }
}
