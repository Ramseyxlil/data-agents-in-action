# Chapter 2 listings

The listings in the order the chapter prints them. Every listing is
cut from `ch02/end/`, and a `# Listing 2.N` comment marks where each
one starts in the code. The marker itself is not printed.

Line counts are the printed lines: the code plus the comments directly
above and inside it, which become #A annotations in the book. A
listing made of two pieces that are apart in the file counts one blank
line between them. Every line is 76 characters or fewer, and no
listing is over 40 lines.

| Listing | Section | What it shows | File | Function or name | Lines |
| --- | --- | --- | --- | --- | --- |
| 2.1 | 2.1 | The reply types and the one-method model interface | `models.py` | `ToolCall`, `ModelReply`, `ChatModel` | 18 |
| 2.2 | 2.1 | Calling OpenAI through that interface | `models.py` | `OpenAIModel` | 23 |
| 2.3 | 2.1 | The naive system prompt | `agent.py` | `SYSTEM_PROMPT_TEMPLATE`, `build_system_prompt` | 25 |
| 2.4 | 2.1 | The agent loop | `agent.py` | `run_agent` | 35 |
| 2.5 | 2.2 | The run_sql tool described as a JSON schema | `tools.py` | `RUN_SQL_TOOL` | 20 |
| 2.6 | 2.2 | The schema text the model gets | `tools.py` | `SCHEMA_SQL`, `describe_schema` | 23 |
| 2.7 | 2.3 | The read-only guard and the timed, read-only query | `tools.py` | `COMMENTS`, `is_read_only`, `execute` | 28 |
| 2.8 | 2.3 | run_sql: rows back, errors as data, a row cap | `tools.py` | `run_sql` | 25 |
| 2.9 | 2.3 | Running one tool call | `agent.py` | `handle_tool_call`, `use_run_sql` | 38 |
| 2.10 | 2.4 | The Answer model and the final_answer tool | `answer.py` | `Answer`, `ANSWER_TOOL` | 39 |
| 2.11 | 2.4 | Asking from the command line | `ask.py` | `main` | 27 |

Listing 2.3 is two pieces: the template, then `build_system_prompt`
further down `agent.py`. In `tools.py`, listing 2.6 sits below 2.7
and 2.8 in the file. The code stays in the order Python reads best,
and the markers say where each listing starts.

Not printed, but in the repo:

- `to_openai_messages` and `from_openai_response` (22 and 12 lines),
  the format conversion behind listing 2.2.
- `AnthropicModel` and its conversion functions, the same interface
  for the second provider.
- `call_model`, `format_trace` and `result_to_dict`, small helpers
  around the loop.
- `questions.py` and `break_it.py`, the section 2.5 experiment.
  Section 2.5 quotes their output, not their code.
