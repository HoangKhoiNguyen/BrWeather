package vn.brweather.repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import vn.brweather.model.StationSummary;

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

    private final JdbcTemplate jdbc;
    private final Duration staleAfter;

    public StationRepository(JdbcTemplate jdbc, @Value("${brweather.stale-after-hours}") long staleAfterHours) {
        this.jdbc = jdbc;
        this.staleAfter = Duration.ofHours(staleAfterHours);
    }

    public List<StationSummary> findActiveWithLatest() {
        Instant now = Instant.now();
        return jdbc.query(LATEST_SQL, (rs, i) -> map(rs, now));
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
                rs.getDouble("lat"), rs.getDouble("lon"), latest);
    }
}
