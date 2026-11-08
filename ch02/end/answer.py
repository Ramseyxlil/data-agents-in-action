"""The structured answer the agent hands back."""

from pydantic import BaseModel, Field


class Answer(BaseModel):
    """A checkable answer: the number, and how the agent got it."""

    value: str = Field(
        description="The answer in one short sentence, as a manager "
                    "would read it.")
    number: float | None = Field(
        default=None,
        description="The headline number on its own, if the answer "
                    "is a number.")
    unit: str | None = Field(
        default=None,
        description='The unit of number, for example "USD", "stores" '
                    'or "percent".')
    sql: str = Field(
        description="The final SQL query the answer came from.")
    rows_used: int = Field(
        description="How many rows that final query returned.")
    explanation: str = Field(
        description="One or two plain sentences on how the answer was "
                    "worked out.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Anything assumed, such as which column was "
                    "treated as revenue.")


# The agent finishes by calling a tool, not by writing prose. Both
# providers support tool calls with a JSON schema, so this gives us the
# same structured output from either one. The schema is built from the
# pydantic model, so the two can never drift apart.
ANSWER_TOOL = {
    "name": "final_answer",
    "description": (
        "Give your final answer to the user. Call this once, after "
        "you have the facts from run_sql."
    ),
    "parameters": Answer.model_json_schema(),
}


def format_answer(answer):
    """Format an Answer for the terminal, readable by a manager."""
    lines = [f"Answer:  {answer.value}",
             f"How:     {answer.explanation}"]
    for assumption in answer.assumptions:
        lines.append(f"Assumed: {assumption}")
    lines.append(f"Query ({answer.rows_used} rows):")
    lines += [f"    {line}" for line in answer.sql.strip().splitlines()]
    return "\n".join(lines)
