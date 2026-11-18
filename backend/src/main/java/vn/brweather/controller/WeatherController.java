package vn.brweather.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import vn.brweather.model.Weather;
import vn.brweather.service.WeatherService;
import vn.brweather.util.Geo;

/** F09: current weather, next 24 hours and 7 days for a point (modelled, Open-Meteo). */
@RestController
@RequestMapping("/api/v1/weather")
public class WeatherController {

    private final WeatherService weather;

    public WeatherController(WeatherService weather) {
        this.weather = weather;
    }

    @GetMapping
    public Weather get(
            @RequestParam(defaultValue = "" + Geo.DEFAULT_LAT) double lat,
            @RequestParam(defaultValue = "" + Geo.DEFAULT_LON) double lon) {
        return weather.at(lat, lon)
                .orElseThrow(() -> new NotFoundException("no recent weather data near this point"));
    }
}
