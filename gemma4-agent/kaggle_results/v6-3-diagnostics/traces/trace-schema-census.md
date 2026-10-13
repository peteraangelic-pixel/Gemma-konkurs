# Trace schema census (keys and types only - no model text)

traces read: 34 | parse failures: 0

| key path | occurrences | types | max string length |
| --- | --- | --- | --- |
| `agent` | 34 | dict | 0 |
| `agent.name` | 34 | str | 13 |
| `agent.version` | 34 | str | 3 |
| `final_metrics` | 34 | dict | 0 |
| `final_metrics.total_cached_tokens` | 34 | int | 0 |
| `final_metrics.total_completion_tokens` | 34 | int | 0 |
| `final_metrics.total_prompt_tokens` | 34 | int | 0 |
| `final_metrics.total_steps` | 34 | int | 0 |
| `final_metrics.total_tokens` | 34 | int | 0 |
| `schema_version` | 34 | str | 9 |
| `steps` | 34 | list | 0 |
| `steps[].extra` | 785 | dict | 0 |
| `steps[].extra.author` | 785 | str | 21 |
| `steps[].extra.elapsed_s` | 785 | float | 0 |
| `steps[].extra.event_type` | 782 | str | 18 |
| `steps[].extra.timestamp` | 785 | float | 0 |
| `steps[].llm_call_count` | 717 | int | 0 |
| `steps[].message` | 782 | str | 17674 |
| `steps[].metrics` | 713 | dict | 0 |
| `steps[].metrics.cached_tokens` | 713 | int | 0 |
| `steps[].metrics.completion_tokens` | 713 | int | 0 |
| `steps[].metrics.prompt_tokens` | 713 | int | 0 |
| `steps[].metrics.total_tokens` | 713 | int | 0 |
| `steps[].model_name` | 717 | str | 71 |
| `steps[].observation` | 709 | dict | 0 |
| `steps[].observation.content` | 709 | str | 10634 |
| `steps[].observation.extra` | 709 | dict | 0 |
| `steps[].observation.extra.author` | 709 | str | 21 |
| `steps[].observation.extra.elapsed_s` | 709 | float | 0 |
| `steps[].observation.extra.timestamp` | 709 | float | 0 |
| `steps[].observation.extra.tool_name` | 709 | str | 12 |
| `steps[].source` | 785 | str | 6 |
| `steps[].step_id` | 785 | int | 0 |
| `steps[].tool_calls` | 709 | list | 0 |
| `steps[].tool_calls[].arguments` | 709 | dict | 0 |
| `steps[].tool_calls[].arguments."end_line"` | 1 | int | 0 |
| `steps[].tool_calls[].arguments.Any],\n    name` | 4 | str | 12 |
| `steps[].tool_calls[].arguments.\n    call` | 4 | str | 12 |
| `steps[].tool_calls[].arguments.\n) -> Dependant` | 4 | str | 47 |
| `steps[].tool_calls[].arguments.] = None,\n    security_scopes` | 4 | str | 17 |
| `steps[].tool_calls[].arguments.], expected_result` | 5 | str | 45 |
| `steps[].tool_calls[].arguments.]] = None,\n    use_cache` | 4 | str | 11 |
| `steps[].tool_calls[].arguments.command` | 299 | str | 11784 |
| `steps[].tool_calls[].arguments.content` | 4 | str | 7379 |
| `steps[].tool_calls[].arguments.def get_dependant(\n    *,\n    path` | 4 | str | 3 |
| `steps[].tool_calls[].arguments.def test_object_is_one_of_types(
    obj` | 5 | str | 6 |
| `steps[].tool_calls[].arguments.end_line` | 136 | int | 0 |
| `steps[].tool_calls[].arguments.filepath` | 296 | str | 69 |
| `steps[].tool_calls[].arguments.from starlette.responses import StreamingResponse as StreamingResponse  # noqa
from typing_extensions import deprecated


try` | 7 | str | 18 |
| `steps[].tool_calls[].arguments.from starlette.responses import StreamingResponse as StreamingResponse  # noqa\nfrom typing_extensions import deprecated\n\n\n\ntry` | 1 | str | 21 |
| `steps[].tool_calls[].arguments.from starlette.responses import StreamingResponse as StreamingResponse  # noqa\nfrom typing_extensions import deprecated\n\n\ntry` | 1 | str | 21 |
| `steps[].tool_calls[].arguments.new_string` | 62 | str | 1388 |
| `steps[].tool_calls[].arguments.old_string` | 35 | str | 1226 |
| `steps[].tool_calls[].arguments.start_line` | 154 | int | 0 |
| `steps[].tool_calls[].arguments.start_line"` | 2 | int | 0 |
| `steps[].tool_calls[].arguments.types` | 5 | str | 12 |
| `steps[].tool_calls[].extra` | 709 | dict | 0 |
| `steps[].tool_calls[].extra.author` | 709 | str | 21 |
| `steps[].tool_calls[].extra.elapsed_s` | 709 | float | 0 |
| `steps[].tool_calls[].extra.model_version` | 709 | str | 71 |
| `steps[].tool_calls[].extra.timestamp` | 709 | float | 0 |
| `steps[].tool_calls[].extra.usage` | 1 | dict | 0 |
| `steps[].tool_calls[].extra.usage.cached_tokens` | 1 | int | 0 |
| `steps[].tool_calls[].extra.usage.completion_tokens` | 1 | int | 0 |
| `steps[].tool_calls[].extra.usage.prompt_tokens` | 1 | int | 0 |
| `steps[].tool_calls[].extra.usage.total_tokens` | 1 | int | 0 |
| `steps[].tool_calls[].function_name` | 709 | str | 12 |
| `steps[].tool_calls[].tool_call_id` | 709 | str | 8 |
