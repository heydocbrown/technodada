class ModelProvider:
    CURSOR = "cursor"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROK = "grok"

class ModelConfig:
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_OPUS = "claude-3-opus"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-0125-preview"
    GPT_3_5_TURBO = "gpt-3.5-turbo-0125"
    GROK_1 = "grok-1"

    @staticmethod
    def get_default_model():
        return ModelConfig.GPT_3_5_TURBO

CONCEPTUAL_AXES = {
    "semantic": "meaning and definition",
    "functional": "purpose and use",
    "causal": "causes and effects",
    "spatial_temporal": "space and time relationships",
    "emotional": "emotional associations",
    "conceptual_abstract": "abstract properties",
} 