# Topic toolkit fixtures

Written by hand from the toolkit's source at commit `5bcee4b`
(`topic_extraction/views.py`: `ExtractConversationView`, `TopicsListingView`, `ArticleTopicView`,
`ArticleSimilarityView`; `taxonomy.py`; taxonomy `2026-05-21-1`), not captured from a live run.
The `extract_*` fixtures were checked against the Runpod toolkit on 2026-10-12 with the live check
below: it passed. That check covers only `extract_request.json` and the top-level keys and types of
`extract_201.json`; the items inside `normalized` and the other `extract_*` fixtures were not checked.
Checked again on 2026-10-19, read endpoints included: all 4 live checks passed. They cover the
top-level keys and types of `extract_201.json`, `taxonomy_200.json`, `article_topics_200.json` and
`similar_articles_200.json`, and a taxonomy `304` round trip with a strong ETag through the Runpod
proxy when asked for an uncompressed answer. The error fixtures were not checked.

- `extract_request.json`: a request body for `POST /api/topics/extract-conversation`
- `extract_201.json`: the success body (`include_labels` and `include_raw` off)
- `extract_201_labels.json`: the success body with `?include_labels=true`
- `extract_400.json`: missing required fields
- `extract_500.json`: an extraction failure
- `taxonomy_200.json`: `GET /api/topics?language=el` (a cut-down topic list; the toolkit's ETag for it is `"2026-05-21-1-el"`)
- `taxonomy_400.json`: an unsupported language
- `article_topics_200.json`: `GET /api/topics/article/fixture-article-1` (labels and raw topics off)
- `article_topics_404.json`: no topics stored for that article
- `similar_articles_200.json`: `GET /api/articles/wp-fixture/fixture-article-1/similar`
- `similar_articles_400.json`: `k` out of range

`tests/gateway/test_toolkit_live.py` checks them against a real toolkit:
`TOOLKIT_LIVE_URL=https://… python manage.py test tests.gateway.test_toolkit_live`.
Run it before a release or when the toolkit changes. It creates one extraction row in that toolkit.
