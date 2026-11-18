package vn.brweather.repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import vn.brweather.model.SeriesPoint;
import vn.brweather.model.StationDetail;
import vn.brweather.model.StationSummary;

/** Read access to stations, their PM2.5 readings, forecasts and anomalies. */
@Repository
public class StationRepository {

    private static final String LATEST_SQL = """
            SELECT s.id, s.name, s.lat, s.lon, m.value, m.unit, m.measured_at, m.kind,
                   (SELECT r.level FROM reliability_scores r
                     WHERE r.station_id = s.id ORDER BY r.computed_at DESC LIMIT 1) AS reliability
            FROM stations s
            LEFT JOIN LATERAL (
                SELECT value, unit, measured_at, kind FROM air_measurements
                WHERE station_id = s.id AND parameter = 'pm25' AND source = 'openaq'
                ORDER BY measured_at DESC LIMIT 1
            ) m ON TRUE
            WHERE s.is_active
            ORDER BY s.name
            """;

    /** Hourly mean, so a station that reports more often than hourly still gives one value per hour. */
    private static final String HOURLY_SQL = """
            SELECT date_trunc('hour', measured_at) AS hour, avg(value) AS value
            FROM air_measurements
            WHERE station_id = ? AND parameter = 'pm25' AND source = 'openaq'
              AND measured_at >= ? AND measured_at < ?
            GROUP BY 1
            """;

    private static final String LATEST_ISSUE_SQL = """
            SELECT issued_at, model_version FROM pm25_forecasts
            WHERE station_id = ? ORDER BY issued_at DESC LIMIT 1
            """;

    private static final String FORECAST_POINTS_SQL = """
            SELECT target_time, value FROM pm25_forecasts
            WHERE station_id = ? AND issued_at = ? AND target_time >= ?
            ORDER BY target_time
            """;

    private static final String ANOMALIES_SQL = """
            SELECT id, start_time, category, description FROM anomalies
            WHERE station_id = ? AND start_time >= ?
            ORDER BY start_time DESC
            """;

    private final JdbcTemplate jdbc;
    private final Duration staleAfter;

    public StationRepository(JdbcTemplate jdbc, @Value("${brweather.stale-after-hours}") long staleAfterHours) {
        this.jdbc = jdbc;
        this.staleAfter = Duration.ofHours(staleAfterHours);
    }

    /** Active stations with their latest reading; distanceKm is 0 here and filled in by the service. */
    public List<StationSummary> findActiveWithLatest() {
        Instant now = Instant.now();
        return jdbc.query(LATEST_SQL, (rs, i) -> map(rs, now));
    }

    public boolean exists(long stationId) {
        Integer n = jdbc.queryForObject("SELECT count(*) FROM stations WHERE id = ?", Integer.class, stationId);
        return n != null && n > 0;
    }

    /** PM2.5 hourly means in [from, to), keyed by the start of the hour (UTC). */
    public Map<Instant, Double> findHourlyPm25(long stationId, Instant from, Instant to) {
        Map<Instant, Double> out = new HashMap<>();
        jdbc.query(HOURLY_SQL, rs -> {
            out.put(rs.getTimestamp("hour").toInstant(), rs.getDouble("value"));
        }, stationId, Timestamp.from(from), Timestamp.from(to));
        return out;
    }

    public record ForecastIssue(Instant issuedAt, String modelVersion) {
    }

    public Optional<ForecastIssue> findLatestForecastIssue(long stationId) {
        List<ForecastIssue> rows = jdbc.query(LATEST_ISSUE_SQL,
                (rs, i) -> new ForecastIssue(rs.getTimestamp("issued_at").toInstant(), rs.getString("model_version")),
                stationId);
        return rows.stream().findFirst();
    }

    /** Points of one forecast issue whose target time is at or after {@code from}. */
    public List<SeriesPoint> findForecastPoints(long stationId, Instant issuedAt, Instant from) {
        return jdbc.query(FORECAST_POINTS_SQL,
                (rs, i) -> new SeriesPoint(
                        rs.getTimestamp("target_time").toInstant(), rs.getDouble("value")),
                stationId, Timestamp.from(issuedAt), Timestamp.from(from));
    }

    public List<StationDetail.Anomaly> findAnomaliesSince(long stationId, Instant since) {
        return jdbc.query(ANOMALIES_SQL,
                (rs, i) -> new StationDetail.Anomaly(rs.getLong("id"), rs.getTimestamp("start_time").toInstant(),
                        rs.getString("category"), rs.getString("description")),
                stationId, Timestamp.from(since));
    }

    private StationSummary map(ResultSet rs, Instant now) throws SQLException {
        Timestamp ts = rs.getTimestamp("measured_at");
        Instant measuredAt = ts == null ? null : ts.toInstant();
        Double value = rs.getObject("value") == null ? null : rs.getDouble("value");
        String status;
        if (measuredAt == null || value == null) {
            status = "missing";
        } else if (Duration.between(measuredAt, now).compareTo(staleAfter) > 0) {
            status = "stale";
        } else {
            status = "ok";
        }
        StationSummary.Latest latest = new StationSummary.Latest(
                value, rs.getString("unit"), measuredAt, "OpenAQ", rs.getString("kind"),
                rs.getString("reliability"), status);
        return new StationSummary(rs.getLong("id"), rs.getString("name"),
                rs.getDouble("lat"), rs.getDouble("lon"), 0, latest);
    }
}
