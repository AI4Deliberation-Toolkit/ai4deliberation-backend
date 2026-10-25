# KG chatbot RAG fixtures

Written by hand from the KG repo's `rag/app.py` at commit `a309fe5` (`QuestionRequest`, `ask_question`),
not captured from a live run.
Checked against the KG pod's RAG (image from `5d53af0`) on 2026-10-25 with the live check below: it
passed on the second run, in 9 s. That check covers `ask_request.json` and the top-level keys and types
of whichever of `ask_200.json` and `ask_200_not_answered.json` the answer matched; `ask_500.json` was not
checked. The first run, with a cold LLM worker, got a `500` after 91 s (`Translation failed: RunPod call
did not complete: IN_PROGRESS`): the RAG at `5d53af0` doesn't poll a RunPod job that is still running.

- `ask_request.json`: a request body for `POST /ask` (the `question` only; `history` defaults to empty)
- `ask_200.json`: a successful answer (`success: true`, with `sparql_generated` and `raw_data_count`)
- `ask_200_not_answered.json`: the HTTP 200 the RAG sends when it could not answer (`success: false`)
- `ask_500.json`: the RAG's error body when narration fails (`detail` only)

`tests/gateway/test_kg_rag_live.py` checks them against a real RAG service. It needs `KG_RAG_LIVE_URL` and
`KG_RAG_LIVE_KEY`, set for one command only (never exported), and each run sends one real question (up to
three LLM calls on the KG side). Read the key without echoing it:

```
read -rs KG_RAG_LIVE_KEY
KG_RAG_LIVE_URL=https://… KG_RAG_LIVE_KEY=$KG_RAG_LIVE_KEY python manage.py test tests.gateway.test_kg_rag_live
unset KG_RAG_LIVE_KEY
```

A slow question (cold LLM worker) fails with a `500` from the RAG or a `524` from the Runpod proxy, not
a contract change. It still counts as a question: wait a few minutes before running again.
