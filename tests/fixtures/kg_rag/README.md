# KG chatbot RAG fixtures

Written by hand from the KG repo's `rag/app.py` at commit `a309fe5` (`QuestionRequest`, `ask_question`),
not captured from a live run.

- `ask_request.json`: a request body for `POST /ask` (the `question` only; `history` defaults to empty)

`tests/gateway/test_kg_rag_live.py` checks them against a real RAG service. How to run it: to be filled in
with that test (it needs `KG_RAG_LIVE_URL` and `KG_RAG_LIVE_KEY`).
