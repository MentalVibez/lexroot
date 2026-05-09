"""Domain exceptions for clean error handling in consumer projects."""


class LexiconError(Exception):
    """Base exception for all living-lexicon errors."""


class WordNotFoundError(LexiconError):
    def __init__(self, word: str):
        super().__init__(f"'{word}' not found in the lexicon")
        self.word = word


class EraNotFoundError(LexiconError):
    def __init__(self, era: str):
        super().__init__(f"Era '{era}' not found")
        self.era = era


class SourceNotFoundError(LexiconError):
    def __init__(self, slug: str):
        super().__init__(f"Source '{slug}' not found")
        self.slug = slug


class StoreConnectionError(LexiconError):
    """Raised when the data store is unreachable."""


class LLMError(LexiconError):
    """Raised when LLM inference fails or no provider is configured."""
