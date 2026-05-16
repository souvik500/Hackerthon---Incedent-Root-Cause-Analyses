package com.hackathon.incidentservice.controller;

import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/incident")
public class IncidentController {

    @PostMapping("/analyze")
    public String analyzeIncident() {

        RestTemplate restTemplate = new RestTemplate();

        String url = "http://localhost:8000/analyze";

        Map<String, String> request = new HashMap<>();
        request.put("incidentId", "INC001");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, String>> entity =
                new HttpEntity<>(request, headers);

        ResponseEntity<String> response =
                restTemplate.postForEntity(
                        url,
                        entity,
                        String.class
                );

        return response.getBody();
    }
}