"""Sample Google Health API payloads, shaped after the v4 docs."""

SLEEP_POINTS = [
    {
        "name": "users/111/dataTypes/sleep/dataPoints/nap",
        "sleep": {
            "interval": {"startTime": "2026-11-08T13:00:00Z", "endTime": "2026-11-08T13:40:00Z"},
            "type": "STAGES",
            "metadata": {"mainSleep": False},
            "summary": {"minutesAsleep": "35", "minutesAwake": "5", "stagesSummary": []},
        },
    },
    {
        "name": "users/111/dataTypes/sleep/dataPoints/main",
        "sleep": {
            "interval": {"startTime": "2026-11-08T04:10:00Z", "endTime": "2026-11-08T11:40:00Z"},
            "type": "STAGES",
            "metadata": {"mainSleep": True, "processed": True, "stagesStatus": "SUCCEEDED"},
            "summary": {
                "minutesInSleepPeriod": "450",
                "minutesAsleep": "412",
                "minutesAwake": "38",
                "stagesSummary": [
                    {"type": "DEEP", "minutes": "71", "count": "4"},
                    {"type": "LIGHT", "minutes": "238", "count": "20"},
                    {"type": "REM", "minutes": "103", "count": "6"},
                    {"type": "AWAKE", "minutes": "38", "count": "19"},
                ],
            },
        },
    },
]

STEPS_ROLLUP = [
    {
        "civilStartTime": {"date": {"year": 2026, "month": 11, "day": 8}},
        "civilEndTime": {"date": {"year": 2026, "month": 11, "day": 9}},
        "steps": {"countSum": "9312"},
    },
    {
        "civilStartTime": {"date": {"year": 2026, "month": 11, "day": 9}},
        "civilEndTime": {"date": {"year": 2026, "month": 11, "day": 10}},
        "steps": {"countSum": "1200"},
    },
]

RHR_POINTS = [
    {
        "dailyRestingHeartRate": {
            "date": {"year": 2026, "month": 11, "day": 9},
            "beatsPerMinute": "61",
        }
    },
    {
        "dailyRestingHeartRate": {
            "date": {"year": 2026, "month": 11, "day": 8},
            "beatsPerMinute": "58",
        }
    },
]
