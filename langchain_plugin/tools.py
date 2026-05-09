"""LangChain tools for The Living Lexicon API."""

import asyncio
import time
from typing import Any, Dict, Optional, Type

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class BaseLexiconTool(BaseTool):
    """Base class for Living Lexicon tools with common HTTP handling."""

    base_url: str = Field(description="Base URL of the Living Lexicon API")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries for rate limits")
    backoff_factor: float = Field(default=2.0, description="Backoff factor for retries")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with authentication and retry logic."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(
                    method, url, headers=headers, params=params, json=json
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit
                    if attempt < self.max_retries:
                        wait_time = self.backoff_factor ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded after {self.max_retries} retries")
                elif e.response.status_code >= 500:  # Server error
                    if attempt < self.max_retries:
                        wait_time = self.backoff_factor ** attempt
                        await asyncio.sleep(wait_time)
                        continue
                raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                if attempt < self.max_retries:
                    wait_time = self.backoff_factor ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                raise Exception(f"Request failed: {str(e)}")

    async def _close_client(self):
        """Close the HTTP client."""
        await self._client.aclose()


class WordLookupTool(BaseLexiconTool):
    """Tool for looking up basic word context from The Living Lexicon."""

    name: str = "word_lookup"
    description: str = "Get basic etymology and context for a word, including definition, root, cognates, and sources."

    def _run(self, word: str) -> str:
        """Synchronous run method for LangChain."""
        return asyncio.run(self._arun(word))

    async def _arun(self, word: str) -> str:
        """Async run method."""
        try:
            data = await self._make_request("GET", f"/word/{word}")
            # Format the response nicely
            result = f"Word: {data.get('word', word)}\n"
            if data.get('definition'):
                result += f"Definition: {data['definition']}\n"
            if data.get('root'):
                result += f"Root: {data['root']}\n"
            if data.get('cognates'):
                result += f"Cognates: {', '.join(data['cognates'])}\n"
            if data.get('sources'):
                result += f"Sources: {', '.join(data['sources'])}\n"
            return result
        except Exception as e:
            return f"Error looking up word '{word}': {str(e)}"


class SemanticDriftTool(BaseLexiconTool):
    """Tool for explaining semantic drift of words."""

    name: str = "semantic_drift"
    description: str = "Explain how a word's meaning has changed over time, with optional context (biblical, legal, medical, literary)."

    def _run(self, word: str, context: Optional[str] = None) -> str:
        """Synchronous run method."""
        return asyncio.run(self._arun(word, context))

    async def _arun(self, word: str, context: Optional[str] = None) -> str:
        """Async run method."""
        try:
            params = {}
            if context:
                params["context"] = context
            data = await self._make_request("GET", f"/word/{word}/drift", params=params)
            return data.get("explanation", "No explanation available")
        except Exception as e:
            return f"Error getting semantic drift for '{word}': {str(e)}"


class EraTimelineTool(BaseLexiconTool):
    """Tool for getting word meanings across historical eras."""

    name: str = "era_timeline"
    description: str = "Get the timeline of meanings for a word across 7 historical eras."

    def _run(self, word: str) -> str:
        """Synchronous run method."""
        return asyncio.run(self._arun(word))

    async def _arun(self, word: str) -> str:
        """Async run method."""
        try:
            data = await self._make_request("GET", f"/word/{word}/era-timeline")
            timeline = data.get("timeline", [])
            if not timeline:
                return f"No timeline data available for '{word}'"

            result = f"Meaning timeline for '{word}':\n"
            for era in timeline:
                result += f"- {era['era']}: {era['meaning']}\n"
            return result
        except Exception as e:
            return f"Error getting era timeline for '{word}': {str(e)}"


class SearchTool(BaseLexiconTool):
    """Tool for searching words in the lexicon."""

    name: str = "lexicon_search"
    description: str = "Search for words in the lexicon database. Returns up to 10 results."

    def _run(self, query: str, limit: int = 10) -> str:
        """Synchronous run method."""
        return asyncio.run(self._arun(query, limit))

    async def _arun(self, query: str, limit: int = 10) -> str:
        """Async run method."""
        try:
            params = {"q": query, "limit": min(limit, 10)}  # Cap at 10
            data = await self._make_request("GET", "/search", params=params)
            results = data.get("results", [])
            if not results:
                return f"No search results for '{query}'"

            result = f"Search results for '{query}':\n"
            for word in results:
                result += f"- {word['word']}: {word.get('definition', 'No definition')}\n"
            return result
        except Exception as e:
            return f"Error searching for '{query}': {str(e)}"


class GuardrailsTool(BaseLexiconTool):
    """Tool for validating AI responses against lexicon data to reduce hallucinations."""

    name: str = "guardrails_check"
    description: str = "Validate an AI-generated response against lexicon data to check for accuracy and reduce hallucinations. Provide the word and the AI response to validate."

    def _run(self, word: str, ai_response: str) -> str:
        """Synchronous run method."""
        return asyncio.run(self._arun(word, ai_response))

    async def _arun(self, word: str, ai_response: str) -> str:
        """Async run method."""
        try:
            # Get actual lexicon data
            lexicon_data = await self._make_request("GET", f"/word/{word}")

            # Simple validation logic - check if key facts match
            validation_results = []

            # Check if definition is mentioned
            if lexicon_data.get('definition'):
                if lexicon_data['definition'].lower() in ai_response.lower():
                    validation_results.append("✅ Definition matches lexicon data")
                else:
                    validation_results.append("⚠️ Definition not found in AI response")

            # Check root etymology
            if lexicon_data.get('root'):
                if lexicon_data['root'].lower() in ai_response.lower():
                    validation_results.append("✅ Root etymology matches")
                else:
                    validation_results.append("⚠️ Root etymology not mentioned")

            # Check cognates
            cognates = lexicon_data.get('cognates', [])
            if cognates:
                mentioned_cognates = [c for c in cognates if c.lower() in ai_response.lower()]
                if mentioned_cognates:
                    validation_results.append(f"✅ Found cognates: {', '.join(mentioned_cognates)}")
                else:
                    validation_results.append("⚠️ No cognates mentioned in AI response")

            # Overall confidence score
            matches = len([r for r in validation_results if r.startswith("✅")])
            total_checks = len(validation_results)
            confidence = matches / total_checks if total_checks > 0 else 0

            result = f"Validation Results for '{word}':\n"
            result += f"Confidence Score: {confidence:.1%} ({matches}/{total_checks} checks passed)\n\n"
            result += "\n".join(validation_results)

            if confidence < 0.5:
                result += "\n\n⚠️ LOW CONFIDENCE: Consider fact-checking this response against authoritative sources."
            elif confidence >= 0.8:
                result += "\n\n✅ HIGH CONFIDENCE: Response appears accurate based on lexicon data."

            return result

        except Exception as e:
            return f"Error validating response for '{word}': {str(e)}"