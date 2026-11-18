package vn.brweather.service;

import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import vn.brweather.model.Weather;
import vn.brweather.repository.WeatherRepository;
import vn.brweather.repository.WeatherRepository.HourRow;
import vn.brweather.repository.WeatherRepository.Snapshot;
import vn.brweather.util.Geo;

/**
 * GET /weather (F09). The pipeline stores weather per station coordinate, so the request point is
 * answered with the nearest stored point within {@code brweather.weather.max-distance-km}.
 */
@Service
public class WeatherService {

    static final int HOURLY_COUNT = 24;
    static final int DAILY_COUNT = 7;
    /** Older snapshots no longer cover "now" (the pipeline fetches 7 days ahead). */
    static final Duration SNAPSHOT_MAX_AGE = Duration.ofDays(2);

    private final WeatherRepository repo;
    private final double maxDistanceKm;

    public WeatherService(WeatherRepository repo,
            @Value("${brweather.weather.max-distance-km:25}") double maxDistanceKm) {
        this.repo = repo;
        this.maxDistanceKm = maxDistanceKm;
    }

    public Optional<Weather> at(double lat, double lon) {
        Geo.requireValid(lat, lon);
        Instant now = Instant.now();
        Optional<Snapshot> nearest = repo.findLatestPerPoint(now.minus(SNAPSHOT_MAX_AGE)).stream()
                .filter(s -> Geo.distanceKm(lat, lon, s.lat(), s.lon()) <= maxDistanceKm)
                .min(Comparator.comparingDouble((Snapshot s) -> Geo.distanceKm(lat, lon, s.lat(), s.lon()))
                        .thenComparing(Snapshot::fetchedAt, Comparator.reverseOrder()));
        return nearest.map(s -> build(s, lat, lon, now));
    }

    private Weather build(Snapshot s, double lat, double lon, Instant now) {
        List<HourRow> rows = repo.findHours(s.id());
        HourRow cur = WeatherAggregator.current(rows, now);
        Weather.Current current = cur == null
                ? new Weather.Current(null, null, null, null, null, null, null, null)
                : new Weather.Current(cur.temperatureC(), cur.apparentC(), cur.humidityPct(), cur.precipitationMm(),
                        cur.windKmh(), cur.windDirectionDeg(), cur.uvIndex(), cur.weatherCode());
        return new Weather(
                s.fetchedAt(),
                cur == null ? null : cur.validTime(),
                "Open-Meteo",
                "modelled",
                Geo.roundKm(Geo.distanceKm(lat, lon, s.lat(), s.lon())),
                current,
                WeatherAggregator.nextHours(rows, now, HOURLY_COUNT),
                WeatherAggregator.daily(rows, now, DAILY_COUNT));
    }
}
