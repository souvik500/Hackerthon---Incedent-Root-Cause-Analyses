package com.incidentai.api.dto;

import java.util.List;

public record IncidentSummaryResponse(
        String incident_id,
        String severity,
        String root_cause,
        double confidence,
        List<String> impacted_services,
        List<String> evidence,
        List<String> recommended_actions,
        List<String> agent_trace,
        boolean human_approval_required
) {
}

