package com.incidentai.api.service;

import com.incidentai.api.dto.AnalyzeIncidentRequest;
import com.incidentai.api.dto.IncidentSummaryResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Service
public class IncidentAiClient {
    private final RestClient restClient;

    public IncidentAiClient(@Value("${incident.ai-service-url}") String aiServiceUrl) {
        this.restClient = RestClient.builder()
                .baseUrl(aiServiceUrl)
                .build();
    }

    public Map<String, String> health() {
        return restClient.get()
                .uri("/health")
                .retrieve()
                .body(Map.class);
    }

    public IncidentSummaryResponse analyze(AnalyzeIncidentRequest request) {
        return restClient.post()
                .uri("/analyze")
                .body(Map.of(
                        "incident_id", request.incidentId(),
                        "query", request.query()
                ))
                .retrieve()
                .body(IncidentSummaryResponse.class);
    }
}

