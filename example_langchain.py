#!/usr/bin/env python3
"""Example usage of The Living Lexicon LangChain plugin."""

import asyncio
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from langchain_plugin import LexiconPlugin


async def main():
    """Example of using the plugin in a LangChain agent."""

    # Initialize the plugin (assuming local API server)
    plugin = LexiconPlugin(
        base_url="http://localhost:8000",
        api_key=None,  # Set if authentication is required
    )

    # Get tools from the plugin
    tools = plugin.get_tools()

    # Create a simple agent with OpenAI
    llm = ChatOpenAI(temperature=0)  # You'll need to set OPENAI_API_KEY

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant with access to etymology tools. Use them to answer questions about word origins and meanings."),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # Example queries
    queries = [
        "What is the etymology of the word 'charity'?",
        "How has the meaning of 'prevent' changed over time?",
        "What did 'passion' mean in medieval times?",
        "Search for words related to 'hold' or 'keep'",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        try:
            result = await agent_executor.ainvoke({"input": query})
            print(f"Response: {result['output']}")
        except Exception as e:
            print(f"Error: {e}")

    # Clean up
    await plugin.close()


if __name__ == "__main__":
    asyncio.run(main())