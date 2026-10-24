# KG chatbot RAG fixtures

Written by hand from the KG repo's `rag/app.py` at commit `a309fe5` (`QuestionRequest`, `ask_question`),
not captured from a live run.

- `ask_request.json`: a request body for `POST /ask` (the `question` only; `history` defaults to empty)
- `ask_200.json`: a successful answer (`success: true`, with `sparql_generated` and `raw_data_count`)
- `ask_200_not_answered.json`: the HTTP 200 the RAG sends when it could not answer (`success: false`)
- `ask_500.json`: the RAG's error body when narration fails (`detail` only)

`tests/gateway/test_kg_rag_live.py` checks them against a real RAG service. How to run it: to be filled in
with that test (it needs `KG_RAG_LIVE_URL` and `KG_RAG_LIVE_KEY`).
