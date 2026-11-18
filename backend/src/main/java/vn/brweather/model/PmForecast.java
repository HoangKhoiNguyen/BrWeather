package vn.brweather.model;

import java.time.Instant;
import java.util.List;

/**
 * Latest PM2.5 forecast of a station (F03, GET /stations/{id}/forecast).
 * When the station has no forecast yet, available is false and issuedAt, modelVersion and points are null.
 */
public record PmForecast(
        long stationId,
        boolean available,
        Instant issuedAt,
        String modelVersion,
        String kind,
        List<SeriesPoint> points) {

    public static PmForecast unavailable(long stationId) {
        return new PmForecast(stationId, false, null, null, "forecast", null);
    }
}
