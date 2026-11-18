package vn.brweather.model;

import java.time.Instant;

/** One hourly value; value is null for an hour without data (never 0). */
public record SeriesPoint(Instant time, Double value) {
}
