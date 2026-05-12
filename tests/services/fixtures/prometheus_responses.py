"""Mock Prometheus API responses for testing"""

# Sample Prometheus response with 50% usage (5 GB used / 10 GB quota)
PROMETHEUS_STORAGE_QUOTA_50_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314029.985, "10737418240"],  # 10 GB
            },
        ],
    },
}

PROMETHEUS_STORAGE_USAGE_50_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "5368709120"],  # 5 GB
            },
        ],
    },
}

PROMETHEUS_STORAGE_TIMESTAMP_50_PERCENT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_total_size_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                    "username": "testuser",
                },
                "value": [1771314216.003, "1771314216.003"],
            },
        ],
    },
}

# Empty results (no data for user)
PROMETHEUS_EMPTY_RESULT = {
    "status": "success",
    "data": {"resultType": "vector", "result": []},
}

# Prometheus error response
PROMETHEUS_ERROR_RESPONSE = {
    "status": "error",
    "error": "query timeout",
    "errorType": "timeout",
}

# Malformed responses
PROMETHEUS_MALFORMED_NO_DATA = {
    "status": "success",
    # missing 'data' field
}

PROMETHEUS_MALFORMED_NO_RESULT = {
    "status": "success",
    "data": {
        "resultType": "vector",
        # missing 'result' field
    },
}

PROMETHEUS_STORAGE_MALFORMED_INVALID_VALUE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                },
                "value": [1771314029.985],  # Missing second element
            },
        ],
    },
}

PROMETHEUS_STORAGE_MALFORMED_NON_NUMERIC = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {
                "metric": {
                    "__name__": "dirsize_hard_limit_bytes",
                    "directory": "testuser",
                    "namespace": "prod",
                },
                "value": [1771314029.985, "not-a-number"],
            },
        ],
    },
}
