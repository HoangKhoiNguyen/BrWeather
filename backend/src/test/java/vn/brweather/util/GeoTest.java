package vn.brweather.util;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class GeoTest {

    @Test
    void samePointIsZero() {
        assertEquals(0.0, Geo.distanceKm(21.0285, 105.8542, 21.0285, 105.8542), 1e-9);
    }

    @Test
    void hoanKiemToNoiBaiIsAbout21Km() {
        // Hoàn Kiếm lake -> Nội Bài airport, about 21 km in a straight line.
        double km = Geo.distanceKm(21.0285, 105.8542, 21.2187, 105.8042);
        assertEquals(21.7, Geo.roundKm(km), 0.5);
    }

    @Test
    void roundsToOneDecimal() {
        assertEquals(7.3, Geo.roundKm(7.26));
        assertEquals(7.2, Geo.roundKm(7.24));
    }

    @Test
    void rejectsOutOfRangeCoordinates() {
        assertThrows(IllegalArgumentException.class, () -> Geo.requireValid(91, 105));
        assertThrows(IllegalArgumentException.class, () -> Geo.requireValid(21, 181));
    }
}
