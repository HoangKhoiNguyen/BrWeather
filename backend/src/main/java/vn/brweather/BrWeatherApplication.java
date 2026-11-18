package vn.brweather;

import java.util.TimeZone;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class BrWeatherApplication {

    public static void main(String[] args) {
        // Everything is stored and served in UTC. Also needed on Windows machines set to Vietnam time:
        // the JVM then reports "Asia/Saigon", which PostgreSQL 16 rejects and every DB connection fails.
        TimeZone.setDefault(TimeZone.getTimeZone("UTC"));
        SpringApplication.run(BrWeatherApplication.class, args);
    }
}
