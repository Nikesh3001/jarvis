import json


DEEP_RESEARCH_PROMPT = """You are a deep research assistant. Your task is to thoroughly investigate a topic.

Follow this research process:
1. PLAN: Break the topic into 3-5 key sub-questions
2. SEARCH: For each sub-question, use web_search to find current information
3. SYNTHESIS: Combine findings into a comprehensive report
4. REFINE: Check for gaps and do additional searches if needed

When you have enough information, produce a final report with:
- Executive summary
- Key findings with sources
- Analysis and insights
- Conclusions

Be thorough and cite sources."""


class DeepResearchAgent:
    def __init__(self, brain):
        self.brain = brain
        self.max_steps = 15

    def research(self, topic):
        messages = [
            {"role": "system", "content": DEEP_RESEARCH_PROMPT},
            {"role": "user", "content": f"Research topic: {topic}\n\nFollow the research process. Start by planning your approach."}
        ]

        original_model = self.brain.current_model
        self.brain.current_model = self.brain.deep_model

        result = self.brain.chat_with_tools(messages, on_speak=lambda t: None)

        self.brain.current_model = original_model
        return result[:10000]

    def get_tool_definitions(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "deep_research",
                    "description": "Perform multi-step deep research on a topic. Searches the web, synthesizes findings, and produces a comprehensive report.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "The research topic or question"}
                        },
                        "required": ["topic"]
                    }
                }
            }
        ]

    def get_handler(self, name):
        handlers = {
            "deep_research": self.research,
        }
        return handlers.get(name)
