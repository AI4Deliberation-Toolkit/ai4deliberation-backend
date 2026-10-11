# Topic toolkit fixtures

Written by hand from the toolkit's source at commit `5bcee4b`
(`topic_extraction/views.py`, `ExtractConversationView`; taxonomy `2026-05-21-1`),
not captured from a live run: no toolkit instance was reachable when they were made.

- `extract_request.json`: a request body for `POST /api/topics/extract-conversation`
- `extract_201.json`: the success body (`include_labels` and `include_raw` off)
- `extract_201_labels.json`: the success body with `?include_labels=true`
- `extract_400.json`: missing required fields
- `extract_500.json`: an extraction failure

`tests/gateway/test_toolkit_live.py` checks them against a real toolkit:
`TOOLKIT_LIVE_URL=https://… python manage.py test tests.gateway.test_toolkit_live`.
Run it before a release or when the toolkit changes. It creates one extraction row in that toolkit.
