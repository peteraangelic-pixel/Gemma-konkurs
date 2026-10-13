# Trace schema census (keys and types only - no model text)

traces read: 30 | parse failures: 0

| key path | occurrences | types | max string length |
| --- | --- | --- | --- |
| `agent` | 30 | dict | 0 |
| `agent.name` | 30 | str | 13 |
| `agent.version` | 30 | str | 3 |
| `final_metrics` | 30 | dict | 0 |
| `final_metrics.total_cached_tokens` | 30 | int | 0 |
| `final_metrics.total_completion_tokens` | 30 | int | 0 |
| `final_metrics.total_prompt_tokens` | 30 | int | 0 |
| `final_metrics.total_steps` | 30 | int | 0 |
| `final_metrics.total_tokens` | 30 | int | 0 |
| `schema_version` | 30 | str | 9 |
| `steps` | 30 | list | 0 |
| `steps[].extra` | 752 | dict | 0 |
| `steps[].extra.author` | 752 | str | 21 |
| `steps[].extra.elapsed_s` | 752 | float | 0 |
| `steps[].extra.event_type` | 737 | str | 18 |
| `steps[].extra.timestamp` | 752 | float | 0 |
| `steps[].llm_call_count` | 675 | int | 0 |
| `steps[].message` | 737 | str | 19309 |
| `steps[].metrics` | 662 | dict | 0 |
| `steps[].metrics.cached_tokens` | 662 | int | 0 |
| `steps[].metrics.completion_tokens` | 662 | int | 0 |
| `steps[].metrics.prompt_tokens` | 662 | int | 0 |
| `steps[].metrics.total_tokens` | 662 | int | 0 |
| `steps[].model_name` | 675 | str | 71 |
| `steps[].observation` | 633 | dict | 0 |
| `steps[].observation.content` | 633 | str | 10851 |
| `steps[].observation.extra` | 633 | dict | 0 |
| `steps[].observation.extra.author` | 633 | str | 21 |
| `steps[].observation.extra.elapsed_s` | 633 | float | 0 |
| `steps[].observation.extra.timestamp` | 633 | float | 0 |
| `steps[].observation.extra.tool_name` | 633 | str | 11 |
| `steps[].source` | 752 | str | 6 |
| `steps[].step_id` | 752 | int | 0 |
| `steps[].tool_calls` | 633 | list | 0 |
| `steps[].tool_calls[].arguments` | 633 | dict | 0 |
| `steps[].tool_calls[].arguments.command` | 364 | str | 12037 |
| `steps[].tool_calls[].arguments.content` | 9 | str | 7874 |
| `steps[].tool_calls[].arguments.def on_validate_error(self, value` | 1 | str | 3 |
| `steps[].tool_calls[].arguments.end_line` | 110 | int | 0 |
| `steps[].tool_calls[].arguments.error` | 1 | str | 263 |
| `steps[].tool_calls[].arguments.filepath` | 267 | str | 61 |
| `steps[].tool_calls[].arguments.for key, value in received_params.items()` | 5 | str | 74 |
| `steps[].tool_calls[].arguments.if title_text is not None` | 5 | str | 48 |
| `steps[].tool_calls[].arguments.new_string` | 78 | str | 1625 |
| `steps[].tool_calls[].arguments.old_string` | 46 | str | 2231 |
| `steps[].tool_calls[].arguments.start_line` | 123 | int | 0 |
| `steps[].tool_calls[].arguments.start_line"` | 2 | int | 0 |
| `steps[].tool_calls[].extra` | 633 | dict | 0 |
| `steps[].tool_calls[].extra.author` | 633 | str | 21 |
| `steps[].tool_calls[].extra.elapsed_s` | 633 | float | 0 |
| `steps[].tool_calls[].extra.model_version` | 633 | str | 71 |
| `steps[].tool_calls[].extra.timestamp` | 633 | float | 0 |
| `steps[].tool_calls[].extra.usage` | 13 | dict | 0 |
| `steps[].tool_calls[].extra.usage.cached_tokens` | 13 | int | 0 |
| `steps[].tool_calls[].extra.usage.completion_tokens` | 13 | int | 0 |
| `steps[].tool_calls[].extra.usage.prompt_tokens` | 13 | int | 0 |
| `steps[].tool_calls[].extra.usage.total_tokens` | 13 | int | 0 |
| `steps[].tool_calls[].function_name` | 633 | str | 11 |
| `steps[].tool_calls[].tool_call_id` | 633 | str | 8 |
