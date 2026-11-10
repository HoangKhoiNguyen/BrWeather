package vn.brweather.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import vn.brweather.model.StationSummary;
import vn.brweather.repository.StationRepository;

/**
 * Station endpoints. See docs/api-contract.md for the full list;
 * /history, /forecast, /anomalies, /nearest are still to be added.
 */
@RestController
@RequestMapping("/api/v1/stations")
public class StationController {

    private final StationRepository stations;

    public StationController(StationRepository stations) {
        this.stations = stations;
    }

    @GetMapping
    public List<StationSummary> list() {
        return stations.findActiveWithLatest();
    }
}
