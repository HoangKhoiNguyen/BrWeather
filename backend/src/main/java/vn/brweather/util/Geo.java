package vn.brweather.util;

/** Distance helpers. Coordinates are WGS84 degrees. */
public final class Geo {

    /** Hà Nội city centre (Hoàn Kiếm), used when the app does not send a position. */
    public static final double DEFAULT_LAT = 21.0285;
    public static final double DEFAULT_LON = 105.8542;

    private static final double EARTH_RADIUS_KM = 6371.0;

    private Geo() {
    }

    /** Great-circle distance in km. */
    public static double distanceKm(double lat1, double lon1, double lat2, double lon2) {
        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);
        double h = Math.pow(Math.sin(dLat / 2), 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) * Math.pow(Math.sin(dLon / 2), 2);
        return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
    }

    /** Rounds to one decimal, the precision shown in the app. */
    public static double roundKm(double km) {
        return Math.round(km * 10) / 10.0;
    }

    public static void requireValid(double lat, double lon) {
        if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
            throw new IllegalArgumentException("lat must be in [-90, 90] and lon in [-180, 180]");
        }
    }
}
