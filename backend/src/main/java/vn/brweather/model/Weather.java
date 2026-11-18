package vn.brweather.model;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;

/**
 * Weather for a place (GET /weather, F09). Values come from the Open-Meteo model, so kind is always
 * "modelled"; any missing value is null, never 0.
 *
 * @param fetchedAt when the pipeline fetched this forecast from Open-Meteo
 * @param validTime the hour the "current" block describes
 */
public record Weather(
        Instant fetchedAt,
        Instant validTime,
        String source,
        String kind,
        double distanceKm,
        Current current,
        List<Hour> hourly,
        List<Day> daily) {

    public record Current(
            Double temperatureC,
            Double apparentC,
            Double humidityPct,
            Double precipitationMm,
            Double windKmh,
            Double windDirectionDeg,
            Double uvIndex,
            Integer weatherCode) {
    }

    public record Hour(Instant time, Double temperatureC, Double precipitationProbPct, Integer weatherCode) {
    }

    /** One calendar day in Vietnam time. */
    public record Day(LocalDate date, Double maxC, Double minC, Double precipitationMm, Integer weatherCode) {
    }
}
