package com.incidentai.api.controller;

import com.incidentai.api.dto.AnalyzeIncidentRequest;
import com.incidentai.api.dto.IncidentSummaryResponse;
import com.incidentai.api.service.IncidentAiClient;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@CrossOrigin
@RestController
@RequestMapping("/api/incidents")
public class IncidentController {
    private final IncidentAiClient incidentAiClient;

    public IncidentController(IncidentAiClient incidentAiClient) {
        this.incidentAiClient = incidentAiClient;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(incidentAiClient.health());
    }

    @PostMapping("/analyze")
    public ResponseEntity<IncidentSummaryResponse> analyze(@Valid @RequestBody AnalyzeIncidentRequest request) {
        return ResponseEntity.ok(incidentAiClient.analyze(request));
    }
}

