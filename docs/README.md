# US Market Brief Final Starter

This is the near-final architecture for a personal US market briefing dashboard.

## Included layers
- 10-point summary first
- Index proxy metrics
- Movers
- Sector performance
- Economic calendar
- Headlines
- Breadth snapshot
- VIX context
- Treasury yield context
- Market-status check
- Scoring engine

## Required secrets
- FINNHUB_API_KEY
- ALPHA_VANTAGE_API_KEY
- FMP_API_KEY
- FRED_API_KEY

## Final tuning after deploy
- Replace placeholder fallbacks with your preferred paid or higher-confidence feeds.
- Tune scoring thresholds to fit your reading style.
- Improve Hebrew phrasing of the summary if you want a more analyst-like tone.
