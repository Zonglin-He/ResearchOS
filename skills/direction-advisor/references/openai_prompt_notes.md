# OpenAI Prompt Notes For This Agent

Distilled from official OpenAI docs used while tuning this agent:
- Put stable role/tone guidance in the system prompt, and keep task-specific evidence in the user payload.
- Keep prompts shorter and clearer than older GPT-era templates; GPT-5 generally needs less scaffolding.
- Use explicit stop conditions so the model does not overthink or drift into adjacent tasks.
- Reserve `reasoning_effort=high` for genuinely complex multi-factor judgments like idea feasibility review.
- Version prompt and skill assets so they can be iterated against real evals.

Primary sources:
- https://developers.openai.com/api/docs/guides/prompting
- https://openai.com/business/guides-and-resources/a-practical-guide-to-building-with-ai/
- https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_troubleshooting_guide
