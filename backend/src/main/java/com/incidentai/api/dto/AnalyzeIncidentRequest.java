package com.incidentai.api.dto;

import jakarta.validation.constraints.NotBlank;

public record AnalyzeIncidentRequest(
        @NotBlank String incidentId,
        @NotBlank String query
) {
}

