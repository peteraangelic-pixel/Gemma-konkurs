# Locator ranking vs recorded outcome (per task)

Locator: `gemma4-agent/submission-v6.6/tools/locate.py`. Sample: the 30 tasks of `gemma4-agent/kaggle_results/v6-4-benchmark/agent_benchmark_result.json`.

`gold_rank` = position of the first gold fixable file in the locator's ranking (the list the agent is shown in step 2), `-` = the file is not in the top 10.

| task | bucket | gold_rank | top-3 shown |
| --- | --- | --- | --- |
| requests_6644 | P resolved | 1 | src/requests/adapters.py, tests/test_requests.py, src/requests/models.py |
| rich_3934 | N no edit | 1 | rich/live.py, rich/console.py, rich/live_render.py |
| fastapi_14851 | N no edit | 1 | fastapi/routing.py, fastapi/__init__.py, fastapi/applications.py |
| rich_3718 | P resolved | 1 | rich/panel.py, rich/text.py, rich/console.py |
| fastapi_14266 | N no edit | - (> 10) | scripts/people.py, fastapi/__init__.py, scripts/notify_translations.py |
| fastapi_14487 | N no edit | - (> 10) | fastapi/routing.py, fastapi/__init__.py, fastapi/applications.py |
| fastapi_14953 | R gold file edited, failed | 8 | fastapi/openapi/models.py, fastapi/__init__.py, fastapi/_compat/shared.py |
| rich_3518 | P resolved | 1 | rich/table.py, rich/text.py, rich/progress.py |
| fastapi_14297 | R gold file edited, failed | 1 | fastapi/_compat/v2.py, fastapi/__init__.py, fastapi/_compat/main.py |
| rich_3894 | P resolved | 1 | rich/_inspect.py, rich/console.py, rich/__init__.py |
| fastapi_14303 | R gold file edited, failed | 1 | fastapi/dependencies/utils.py, fastapi/__init__.py, fastapi/param_functions.py |
| rich_3052 | R gold file edited, failed | 1 | rich/prompt.py, rich/console.py, tests/test_prompt.py |
| rich_3043 | N no edit | - (> 10) | rich/console.py, rich/text.py, rich/style.py |
| rich_3105 | N no edit | - (> 10) | rich/progress.py, rich/console.py, benchmarks/snippets.py |
| fastapi_14873 | P resolved | 1 | fastapi/routing.py, fastapi/__init__.py, fastapi/applications.py |
| fastapi_15030 | R gold file edited, failed | - (> 10) | docs_src/dataclasses_/tutorial002_py310.py, fastapi/__init__.py, fastapi/openapi/models.py |
| fastapi_15588 | N no edit | 2 | scripts/notify_translations.py, fastapi/sse.py, fastapi/openapi/models.py |
| rich_3006 | P resolved | 10 | rich/text.py, rich/color.py, rich/style.py |
| fastapi_14186 | R gold file edited, failed | 4 | scripts/contributors.py, fastapi/__init__.py, scripts/sponsors.py |
| rich_3882 | P resolved | 1 | rich/prompt.py, rich/progress.py, rich/console.py |
| fastapi_14459 | N no edit | 5 | fastapi/security/oauth2.py, fastapi/__init__.py, fastapi/openapi/models.py |
| requests_6757 | N no edit | 1 | src/requests/utils.py, src/requests/adapters.py, src/requests/sessions.py |
| fastapi_14262 | R gold file edited, failed | 1 | fastapi/routing.py, fastapi/__init__.py, fastapi/security/oauth2.py |
| rich_2725 | P resolved | 3 | rich/__main__.py, rich/text.py, rich/table.py |
| requests_7309 | R gold file edited, failed | 1 | src/requests/utils.py, tests/test_utils.py, src/requests/exceptions.py |
| fastapi_14482 | W wrong file edited | - (> 10) | fastapi/utils.py, fastapi/openapi/models.py, fastapi/params.py |
| fastapi_15745 | N no edit | 1 | fastapi/routing.py, scripts/docs.py, fastapi/__init__.py |
| fastapi_14458 | P resolved | 1 | fastapi/dependencies/models.py, fastapi/__init__.py, tests/test_dependency_class.py |
| fastapi_14077 | P resolved | 3 | scripts/sponsors.py, fastapi/__init__.py, fastapi/exception_handlers.py |
| httpx_3672 | N no edit | 1 | src/httpx/_parsers.py, src/ahttpx/_parsers.py, src/httpx/_pool.py |
