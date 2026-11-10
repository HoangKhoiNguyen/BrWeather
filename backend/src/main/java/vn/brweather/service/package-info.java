/**
 * Business logic, to be added sprint by sprint:
 * <ul>
 *   <li>RecommendationService (F06): rank time windows by PM2.5 forecast, rain probability and temperature
 *       over the whole activity duration; return at most 3 with reasons.</li>
 *   <li>AlertService (F07a): evaluate subscriptions each hour, suppress duplicates within 60 minutes.</li>
 *   <li>ExplanationService (F05): send validated numbers to the LLM, check every number in the answer,
 *       fall back to fixed templates on error, timeout or budget limit.</li>
 *   <li>WeatherService (F09): serve the latest Open-Meteo snapshot for a location.</li>
 * </ul>
 */
package vn.brweather.service;
