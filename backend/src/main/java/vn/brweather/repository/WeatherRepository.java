package vn.brweather.repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** Open-Meteo snapshots written by the pipeline (one snapshot = one 7-day hourly forecast for one point). */
@Repository
public class WeatherRepository {

    /** Latest snapshot of every point fetched since {@code since}. */
    private static final String LATEST_PER_POINT_SQL = """
            SELECT DISTINCT ON (lat, lon) snapshot_id, lat, lon, fetched_at, source
            FROM weather_snapshots
            WHERE fetched_at >= ?
            ORDER BY lat, lon, fetched_at DESC
            """;

    private static final String HOURS_SQL = """
            SELECT valid_time, temperature_c, apparent_temperature_c, humidity_pct, precipitation_mm,
                   precipitation_prob_pct, weather_code, wind_speed_kmh, wind_direction_deg, uv_index
            FROM weather_hourly
            WHERE snapshot_id = ?
            ORDER BY valid_time
            """;

    public record Snapshot(long id, double lat, double lon, Instant fetchedAt, String source) {
    }

    /** One row of weather_hourly; every value may be null. */
    public record HourRow(
            Instant validTime,
            Double temperatureC,
            Double apparentC,
            Double humidityPct,
            Double precipitationMm,
            Double precipitationProbPct,
            Integer weatherCode,
            Double windKmh,
            Double windDirectionDeg,
            Double uvIndex) {
    }

    private final JdbcTemplate jdbc;

    public WeatherRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Snapshot> findLatestPerPoint(Instant since) {
        return jdbc.query(LATEST_PER_POINT_SQL,
                (rs, i) -> new Snapshot(rs.getLong("snapshot_id"), rs.getDouble("lat"), rs.getDouble("lon"),
                        rs.getTimestamp("fetched_at").toInstant(), rs.getString("source")),
                Timestamp.from(since));
    }

    public List<HourRow> findHours(long snapshotId) {
        return jdbc.query(HOURS_SQL, (rs, i) -> new HourRow(
                rs.getTimestamp("valid_time").toInstant(),
                dbl(rs, "temperature_c"),
                dbl(rs, "apparent_temperature_c"),
                dbl(rs, "humidity_pct"),
                dbl(rs, "precipitation_mm"),
                dbl(rs, "precipitation_prob_pct"),
                rs.getObject("weather_code") == null ? null : rs.getInt("weather_code"),
                dbl(rs, "wind_speed_kmh"),
                dbl(rs, "wind_direction_deg"),
                dbl(rs, "uv_index")), snapshotId);
    }

    /** getDouble returns 0 for SQL NULL; the contract wants null. */
    private static Double dbl(ResultSet rs, String col) throws SQLException {
        double v = rs.getDouble(col);
        return rs.wasNull() ? null : v;
    }
}
