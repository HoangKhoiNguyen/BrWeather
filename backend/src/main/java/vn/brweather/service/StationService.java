package vn.brweather.service;

import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;

import vn.brweather.model.PmForecast;
import vn.brweather.model.SeriesPoint;
import vn.brweather.model.StationDetail;
import vn.brweather.model.StationSummary;
import vn.brweather.repository.StationRepository;
import vn.brweather.repository.StationRepository.ForecastIssue;
import vn.brweather.util.Geo;
import vn.brweather.util.HourlySeries;

@Service
public class StationService {

    static final int HISTORY_HOURS = 24;
    static final Duration ANOMALY_WINDOW = Duration.ofDays(14);

    private final StationRepository repo;

    public StationService(StationRepository repo) {
        this.repo = repo;
    }

    /** Active stations sorted nearest first, each with distanceKm from (lat, lon). */
    public List<StationSummary> listByDistance(double lat, double lon) {
        Geo.requireValid(lat, lon);
        return repo.findActiveWithLatest().stream()
                .map(s -> s.withDistanceKm(Geo.roundKm(Geo.distanceKm(lat, lon, s.lat(), s.lon()))))
                .sorted(Comparator.comparingDouble(StationSummary::distanceKm).thenComparing(StationSummary::name))
                .toList();
    }

    public Optional<StationSummary> nearest(double lat, double lon) {
        return listByDistance(lat, lon).stream().findFirst();
    }

    /** Latest forecast issue; empty only when the station does not exist. */
    public Optional<PmForecast> forecast(long stationId) {
        if (!repo.exists(stationId)) {
            return Optional.empty();
        }
        Instant from = HourlySeries.floorHour(Instant.now());
        Optional<ForecastIssue> issue = repo.findLatestForecastIssue(stationId);
        if (issue.isEmpty()) {
            return Optional.of(PmForecast.unavailable(stationId));
        }
        List<SeriesPoint> points = repo.findForecastPoints(stationId, issue.get().issuedAt(), from);
        if (points.isEmpty()) {
            // The latest issue is entirely in the past: the forecast job has stopped, do not show old values.
            return Optional.of(PmForecast.unavailable(stationId));
        }
        return Optional.of(new PmForecast(stationId, true, issue.get().issuedAt(),
                issue.get().modelVersion(), "forecast", points));
    }

    /** History (last 24 h, null gaps), forecast and recent anomalies; empty when the station does not exist. */
    public Optional<StationDetail> detail(long stationId) {
        Optional<PmForecast> fc = forecast(stationId);
        if (fc.isEmpty()) {
            return Optional.empty();
        }
        Instant now = Instant.now();
        Instant end = HourlySeries.floorHour(now).plus(Duration.ofHours(1));
        Instant start = end.minus(Duration.ofHours(HISTORY_HOURS));
        List<SeriesPoint> history = HourlySeries.fill(repo.findHourlyPm25(stationId, start, end), start, HISTORY_HOURS);
        PmForecast f = fc.get();
        return Optional.of(new StationDetail(history, f.points(), f.issuedAt(), f.modelVersion(),
                repo.findAnomaliesSince(stationId, now.minus(ANOMALY_WINDOW))));
    }
}
