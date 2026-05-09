"""Tests for LangChain plugin tools with mocked API responses."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from langchain_plugin.tools import WordLookupTool, SemanticDriftTool, EraTimelineTool, SearchTool, GuardrailsTool


@pytest.fixture
def mock_tool():
    """Create a mock tool instance."""
    return WordLookupTool(base_url="http://mock-api", api_key="test-key")


class TestWordLookupTool:
    """Test the WordLookupTool."""

    @pytest.mark.asyncio
    async def test_successful_lookup(self):
        """Test successful word lookup."""
        tool = WordLookupTool(base_url="http://mock-api")

        mock_response = {
            "word": "charity",
            "definition": "The practice of benevolent giving",
            "root": "Latin caritas (dearness)",
            "cognates": ["charitable", "cherish"],
            "sources": ["OED", "EtymOnline"]
        }

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await tool._arun("charity")

            expected = (
                "Word: charity\n"
                "Definition: The practice of benevolent giving\n"
                "Root: Latin caritas (dearness)\n"
                "Cognates: charitable, cherish\n"
                "Sources: OED, EtymOnline\n"
            )
            assert result == expected

    @pytest.mark.asyncio
    async def test_lookup_error(self):
        """Test error handling in word lookup."""
        tool = WordLookupTool(base_url="http://mock-api")

        with patch.object(tool, '_make_request', side_effect=Exception("API error")):
            result = await tool._arun("unknown")
            assert "Error looking up word 'unknown': API error" in result


class TestSemanticDriftTool:
    """Test the SemanticDriftTool."""

    @pytest.mark.asyncio
    async def test_drift_explanation(self):
        """Test semantic drift explanation."""
        tool = SemanticDriftTool(base_url="http://mock-api")

        mock_response = {
            "explanation": "The word 'prevent' originally meant 'come before' in Latin..."
        }

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await tool._arun("prevent", "legal")
            assert result == "The word 'prevent' originally meant 'come before' in Latin..."

    @pytest.mark.asyncio
    async def test_drift_with_context(self):
        """Test drift with context parameter."""
        tool = SemanticDriftTool(base_url="http://mock-api")

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"explanation": "Biblical context explanation"}

            result = await tool._arun("charity", "biblical")

            # Check that context was passed
            mock_req.assert_called_once_with(
                "GET", "/word/charity/drift", params={"context": "biblical"}
            )


class TestEraTimelineTool:
    """Test the EraTimelineTool."""

    @pytest.mark.asyncio
    async def test_timeline_formatting(self):
        """Test timeline response formatting."""
        tool = EraTimelineTool(base_url="http://mock-api")

        mock_response = {
            "timeline": [
                {"era": "Old English", "meaning": "Dear, beloved"},
                {"era": "Middle English", "meaning": "Christian love"},
                {"era": "Modern English", "meaning": "Benevolent giving"}
            ]
        }

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await tool._arun("charity")

            expected_lines = [
                "Meaning timeline for 'charity':",
                "- Old English: Dear, beloved",
                "- Middle English: Christian love",
                "- Modern English: Benevolent giving"
            ]
            for line in expected_lines:
                assert line in result


class TestSearchTool:
    """Test the SearchTool."""

    @pytest.mark.asyncio
    async def test_search_results(self):
        """Test search functionality."""
        tool = SearchTool(base_url="http://mock-api")

        mock_response = {
            "results": [
                {"word": "charity", "definition": "Benevolent giving"},
                {"word": "charitable", "definition": "Generous"}
            ]
        }

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await tool._arun("char", 5)

            assert "Search results for 'char':" in result
            assert "- charity: Benevolent giving" in result
            assert "- charitable: Generous" in result

            # Check params
            mock_req.assert_called_once_with(
                "GET", "/search", params={"q": "char", "limit": 5}
            )


class TestGuardrailsTool:
    """Test the GuardrailsTool."""

    @pytest.mark.asyncio
    async def test_high_confidence_validation(self):
        """Test validation with accurate AI response."""
        tool = GuardrailsTool(base_url="http://mock-api")

        mock_lexicon_data = {
            "word": "charity",
            "definition": "The practice of benevolent giving",
            "root": "Latin caritas (dearness)",
            "cognates": ["charitable", "cherish"]
        }

        accurate_response = "Charity is the practice of benevolent giving. It comes from Latin caritas (dearness). It's related to charitable and cherish."

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_lexicon_data

            result = await tool._arun("charity", accurate_response)

            assert "Confidence Score: 100.0%" in result
            assert "✅ Definition matches lexicon data" in result
            assert "✅ Root etymology matches" in result
            assert "✅ Found cognates: charitable, cherish" in result
            assert "HIGH CONFIDENCE" in result

    @pytest.mark.asyncio
    async def test_low_confidence_validation(self):
        """Test validation with inaccurate AI response."""
        tool = GuardrailsTool(base_url="http://mock-api")

        mock_lexicon_data = {
            "word": "charity",
            "definition": "The practice of benevolent giving",
            "root": "Latin caritas (dearness)",
            "cognates": ["charitable", "cherish"]
        }

        inaccurate_response = "Charity is about being kind to others. It has no etymological roots."

        with patch.object(tool, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_lexicon_data

            result = await tool._arun("charity", inaccurate_response)

            assert "Confidence Score: 0.0%" in result
            assert "⚠️ Definition not found in AI response" in result
            assert "⚠️ Root etymology not mentioned" in result
            assert "⚠️ No cognates mentioned" in result
            assert "LOW CONFIDENCE" in result


if __name__ == "__main__":
    # Run basic tests
    asyncio.run(TestWordLookupTool().test_successful_lookup())
    asyncio.run(TestSemanticDriftTool().test_drift_explanation())
    print("Basic tests passed!")