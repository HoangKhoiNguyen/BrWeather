package vn.brweather.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import vn.brweather.model.PmForecast;
import vn.brweather.model.StationDetail;
import vn.brweather.model.StationSummary;
import vn.brweather.service.StationService;
import vn.brweather.util.Geo;

/** Station endpoints, see docs/api-contract.md. lat/lon default to Hà Nội centre when the app has no position. */
@RestController
@RequestMapping("/api/v1/stations")
public class StationController {

    private final StationService stations;

    public StationController(StationService stations) {
        this.stations = stations;
    }

    /** F01: all active stations, nearest first, each with distanceKm. */
    @GetMapping
    public List<StationSummary> list(
            @RequestParam(defaultValue = "" + Geo.DEFAULT_LAT) double lat,
            @RequestParam(defaultValue = "" + Geo.DEFAULT_LON) double lon) {
        return stations.listByDistance(lat, lon);
    }

    /** F01: the single nearest station; the app warns when distanceKm > 10. */
    @GetMapping("/nearest")
    public StationSummary nearest(@RequestParam double lat, @RequestParam double lon) {
        return stations.nearest(lat, lon)
                .orElseThrow(() -> new NotFoundException("no active station"));
    }

    /** F03: latest forecast issue, with issuedAt and modelVersion. available=false when there is none. */
    @GetMapping("/{id}/forecast")
    public PmForecast forecast(@PathVariable long id) {
        return stations.forecast(id).orElseThrow(() -> new NotFoundException("station " + id + " not found"));
    }

    /** F02–F04: everything the station detail screen shows, in one call. */
    @GetMapping("/{id}/detail")
    public StationDetail detail(@PathVariable long id) {
        return stations.detail(id).orElseThrow(() -> new NotFoundException("station " + id + " not found"));
    }
}
