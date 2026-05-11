"""Processed storage usage data for testing"""

USAGE_50_PCT = {
    "username": "testuser",
    "usage_bytes": 5368709120,
    "quota_bytes": 10737418240,
    "usage_gb": 5.0,
    "quota_gb": 10.0,
    "percentage": 50.0,
    "last_updated": "2026-02-24T12:00:00+00:00",
}

USAGE_95_PCT = {
    "username": "testuser",
    "usage_bytes": 10200547328,
    "quota_bytes": 10737418240,
    "usage_gb": 9.5,
    "quota_gb": 10.0,
    "percentage": 95.0,
    "last_updated": "2026-02-24T12:00:00+00:00",
}

USAGE_0_PCT = {
    "username": "testuser",
    "usage_bytes": 0,
    "quota_bytes": 10737418240,
    "usage_gb": 0.0,
    "quota_gb": 10.0,
    "percentage": 0.0,
    "last_updated": "2026-02-24T12:00:00+00:00",
}

USAGE_100_PCT = {
    "username": "testuser",
    "usage_bytes": 10737418240,
    "quota_bytes": 10737418240,
    "usage_gb": 10.0,
    "quota_gb": 10.0,
    "percentage": 100.0,
    "last_updated": "2026-02-24T12:00:00+00:00",
}

USAGE_TERABYTES = {
    "username": "testuser",
    "usage_bytes": 549755813888,
    "quota_bytes": 1099511627776,
    "usage_gb": 512.0,
    "quota_gb": 1024.0,
    "percentage": 50.0,
    "last_updated": "2026-02-24T12:00:00+00:00",
}

USAGE_PROMETHEUS_ERROR = {
    "username": "testuser",
    "error": "Unable to reach Prometheus. Please try again later.",
}

USAGE_NO_DATA = {
    "username": "testuser",
    "error": "No storage data found for your account.",
}

COMPUTE_DATA_PLACEHOLDER = [
    {
        "username": "testuser",
        "usage": 5,
        "quota": 10,
        "percentage": 50.0,
        "window": 7,
        "last_updated": "2026-02-24T12:00:00+00:00",
    }
]

COMPUTE_DATA_ERROR = [
    {"username": "testuser", "error": "No compute data found for your account."}
]
