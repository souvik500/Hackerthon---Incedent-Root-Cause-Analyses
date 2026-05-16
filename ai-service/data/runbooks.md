# Checkout Payment Failure Runbook

Symptoms:
- Checkout API latency increases above 2 seconds.
- Checkout API returns 503 when payment-service is unhealthy.
- Payment provider timeout may be caused by upstream provider degradation or local database pool exhaustion.

Checks:
- Inspect payment-service database pool usage.
- Check payment provider timeout rate.
- Compare checkout failures with payment-service error logs.

Actions:
- Scale payment-service workers if CPU or DB pool is saturated.
- Increase payment ledger connection pool only after checking database capacity.
- Temporarily drain retry queue and enable provider fallback if timeout rate remains high.
- Notify payments on-call and customer support for failed checkout impact.

# Database Pool Exhaustion Runbook

Symptoms:
- Logs mention connection pool exhausted.
- Latency and retry queue depth increase together.
- Services may return 503 while waiting for database connections.

Actions:
- Restart unhealthy payment-service pods one at a time.
- Reduce retry concurrency.
- Check for slow ledger queries and recent deployment changes.
- Roll back the payment-service release if pool exhaustion started after deployment.

