class AgentConfig:
    def __init__(
        self,
        name: str,
        description: str,
        prompt_file: str,
        tools: list[str],
        llm_run_limit: int | None = None,
        context: list[dict] = None,
        children: dict = None,
        temperature: float = None,
    ):
        self.name: str = name
        self.description: str = description
        self.prompt_file: str = prompt_file
        self.tools: list[str] = tools
        self.llm_run_limit: int | None = llm_run_limit
        self.children: list[AgentConfig] = []
        self.context: list[AgentContextConfig] = []
        self.temperature: float | None = temperature

        if children is not None:
            self.children = [AgentConfig(**child) for child in children]

        if context is not None:
            self.context = [AgentContextConfig(**ctx) for ctx in context]

class AgentContextConfig:
    def __init__(self, property_name: str, property_placeholder: str):
        self.property_name: str = property_name
        self.property_placeholder: str = property_placeholder