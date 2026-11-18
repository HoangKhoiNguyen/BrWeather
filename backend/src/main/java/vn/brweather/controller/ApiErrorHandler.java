package vn.brweather.controller;

import java.time.Instant;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/** Every error is JSON: {"error": "...", "message": "...", "time": "..."}. */
@RestControllerAdvice
public class ApiErrorHandler {

    public record ApiError(String error, String message, Instant time) {
    }

    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<ApiError> notFound(NotFoundException e) {
        return body(HttpStatus.NOT_FOUND, "not_found", e.getMessage());
    }

    @ExceptionHandler({IllegalArgumentException.class, MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class})
    public ResponseEntity<ApiError> badRequest(Exception e) {
        String msg = e instanceof MethodArgumentTypeMismatchException m
                ? "invalid value for '" + m.getName() + "'"
                : e.getMessage();
        return body(HttpStatus.BAD_REQUEST, "bad_request", msg);
    }

    private static ResponseEntity<ApiError> body(HttpStatus status, String code, String message) {
        return ResponseEntity.status(status).body(new ApiError(code, message, Instant.now()));
    }
}
