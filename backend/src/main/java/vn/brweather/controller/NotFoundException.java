package vn.brweather.controller;

/** Mapped to HTTP 404 by {@link ApiErrorHandler}. */
public class NotFoundException extends RuntimeException {

    public NotFoundException(String message) {
        super(message);
    }
}
