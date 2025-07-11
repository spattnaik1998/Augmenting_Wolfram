# Backend - langgraph_agent.py
import openai
import requests
import json
import re
import os
from typing import Dict, List, Optional, Any, TypedDict, Annotated
from dataclasses import dataclass
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate
import operator
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

@dataclass
class ToolResult:
    """Result from a tool execution"""
    success: bool
    result: Any
    error: Optional[str] = None
    source: Optional[str] = None

class AgentState(TypedDict):
    """State of the agent workflow"""
    messages: Annotated[List, add_messages]
    user_query: str
    needs_wolfram: bool
    wolfram_result: Optional[str]
    final_response: Optional[str]
    used_wolfram: bool  # Track if Wolfram was actually used

class WolframAlphaLangGraphAgent:
    """Agent that uses LangGraph to orchestrate GPT-4o with Wolfram Alpha API"""
    
    def __init__(self, openai_api_key: Optional[str] = None, wolfram_app_id: Optional[str] = None):
        """
        Initialize the agent with API keys
        
        Args:
            openai_api_key: OpenAI API key (optional, will use env var if not provided)
            wolfram_app_id: Wolfram Alpha App ID (optional, will use env var if not provided)
        """
        # Use provided keys or fall back to environment variables
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.wolfram_app_id = wolfram_app_id or os.getenv("WOLFRAM_APP_ID")
        
        # Validate API keys
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable or pass it as parameter.")
        
        if not self.wolfram_app_id:
            raise ValueError("Wolfram Alpha App ID not found. Please set WOLFRAM_APP_ID environment variable or pass it as parameter.")
        
        self.llm = ChatOpenAI(
            model="gpt-4o",
            api_key=self.openai_api_key,
            temperature=0
        )
        
        self.wolfram_base_url = "http://api.wolframalpha.com/v2/query"
        self.last_used_wolfram = False  # Track last usage
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        
        logger.info("WolframAlphaLangGraphAgent initialized successfully")
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("classifier", self._classify_query)
        workflow.add_node("wolfram_search", self._query_wolfram)
        workflow.add_node("generate_response", self._generate_response)
        
        # Add edges
        workflow.set_entry_point("classifier")
        workflow.add_conditional_edges(
            "classifier",
            self._should_use_wolfram,
            {
                "wolfram": "wolfram_search",
                "direct": "generate_response"
            }
        )
        workflow.add_edge("wolfram_search", "generate_response")
        workflow.add_edge("generate_response", END)
        
        return workflow
    
    def _classify_query(self, state: AgentState) -> AgentState:
        """Classify whether the query needs Wolfram Alpha"""
        
        classification_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a query classifier. Determine if a user query requires Wolfram Alpha for computational, mathematical, scientific, or factual lookups.

USE WOLFRAM ALPHA for:
- Mathematical calculations, equations, derivatives, integrals
- Scientific computations or data lookups
- Unit conversions (temperature, distance, weight, etc.)
- Weather information
- Geographic or demographic data (population, area, etc.)
- Statistical analysis
- Financial calculations (compound interest, etc.)
- Physical constants or scientific facts
- Real-time data queries
- Complex mathematical word problems
- Solving equations or systems of equations
- Matrix operations
- Probability calculations
- Chemistry calculations
- Physics problems

DO NOT USE WOLFRAM ALPHA for:
- General conversation
- Creative writing requests
- Explanations that don't require computation
- Opinion-based questions
- Simple definitions
- Jokes or casual chat
- Philosophical discussions
- General advice
- Programming help (unless it involves mathematical calculations)

Respond with ONLY 'YES' if Wolfram Alpha is needed, or 'NO' if it's not needed."""),
            ("human", "{query}")
        ])
        
        try:
            response = self.llm.invoke(
                classification_prompt.format_messages(query=state["user_query"])
            )
            
            needs_wolfram = response.content.strip().upper() == "YES"
            
            logger.info(f"Query classification: {'Needs Wolfram Alpha' if needs_wolfram else 'Direct response'}")
            
            return {
                **state,
                "needs_wolfram": needs_wolfram,
                "used_wolfram": False,
                "messages": state["messages"] + [
                    SystemMessage(content=f"Query classification: {'Needs Wolfram Alpha' if needs_wolfram else 'Direct response'}")
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in classification: {e}")
            return {
                **state,
                "needs_wolfram": False,
                "used_wolfram": False,
                "messages": state["messages"] + [
                    SystemMessage(content=f"Classification error: {e}")
                ]
            }
    
    def _should_use_wolfram(self, state: AgentState) -> str:
        """Decide the next step based on classification"""
        return "wolfram" if state["needs_wolfram"] else "direct"
    
    def _query_wolfram(self, state: AgentState) -> AgentState:
        """Query Wolfram Alpha API"""
        
        # First, let the LLM formulate the best query for Wolfram Alpha
        query_formulation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at formulating queries for Wolfram Alpha. 
Given a user question, create the most effective Wolfram Alpha query.

Guidelines:
- Keep it concise and specific
- Use mathematical notation when appropriate
- For unit conversions, use format like "100 fahrenheit to celsius"
- For equations, use standard mathematical syntax like "solve 2x + 5 = 15"
- For derivatives, use "derivative of x^2 + 3x"
- For integrals, use "integral of x^2 + 3x"
- For population data, use "population of [city/country]"
- For scientific constants, be specific like "speed of light"
- Remove unnecessary words and focus on the core computation

Examples:
- "What is the integral of x squared plus 3x?" → "integral of x^2 + 3x"
- "Convert 100 degrees Fahrenheit to Celsius" → "100 fahrenheit to celsius"
- "What's the population of Tokyo?" → "population of Tokyo"
- "Solve the equation 2x plus 5 equals 15" → "solve 2x + 5 = 15"

Return ONLY the Wolfram Alpha query, nothing else."""),
            ("human", "{original_query}")
        ])
        
        try:
            # Get optimized query
            wolfram_query_response = self.llm.invoke(
                query_formulation_prompt.format_messages(original_query=state["user_query"])
            )
            
            wolfram_query = wolfram_query_response.content.strip()
            logger.info(f"Wolfram Alpha query: {wolfram_query}")
            
            # Execute Wolfram Alpha query
            result = self._execute_wolfram_query(wolfram_query)
            
            return {
                **state,
                "wolfram_result": result.result if result.success else f"Error: {result.error}",
                "used_wolfram": result.success,
                "messages": state["messages"] + [
                    SystemMessage(content=f"Wolfram Query: {wolfram_query}"),
                    SystemMessage(content=f"Wolfram Result: {result.result if result.success else result.error}")
                ]
            }
            
        except Exception as e:
            logger.error(f"Error in Wolfram query: {e}")
            return {
                **state,
                "wolfram_result": f"Error querying Wolfram Alpha: {str(e)}",
                "used_wolfram": False,
                "messages": state["messages"] + [
                    SystemMessage(content=f"Wolfram Alpha error: {e}")
                ]
            }
    
    def _execute_wolfram_query(self, query: str) -> ToolResult:
        """Execute a query against Wolfram Alpha API"""
        try:
            params = {
                'appid': self.wolfram_app_id,
                'input': query,
                'format': 'plaintext',
                'output': 'json'
            }
            
            logger.info(f"Executing Wolfram Alpha query: {query}")
            response = requests.get(self.wolfram_base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('queryresult', {}).get('success', False):
                logger.warning("Wolfram Alpha query was not successful")
                return ToolResult(
                    success=False,
                    result=None,
                    error="Wolfram Alpha could not process the query",
                    source="wolfram_alpha"
                )
            
            # Extract meaningful results
            pods = data['queryresult'].get('pods', [])
            results = []
            
            for pod in pods:
                title = pod.get('title', '')
                subpods = pod.get('subpods', [])
                
                for subpod in subpods:
                    plaintext = subpod.get('plaintext', '')
                    if plaintext and plaintext.strip():
                        results.append(f"{title}: {plaintext}")
            
            if not results:
                logger.warning("No readable results found from Wolfram Alpha")
                return ToolResult(
                    success=False,
                    result=None,
                    error="No readable results found",
                    source="wolfram_alpha"
                )
            
            result_text = '\n'.join(results)
            logger.info(f"Wolfram Alpha result: {result_text[:200]}...")
            
            return ToolResult(
                success=True,
                result=result_text,
                source="wolfram_alpha"
            )
            
        except requests.RequestException as e:
            logger.error(f"Wolfram Alpha API request failed: {e}")
            return ToolResult(
                success=False,
                result=None,
                error=f"API request failed: {str(e)}",
                source="wolfram_alpha"
            )
        except Exception as e:
            logger.error(f"Unexpected error in Wolfram Alpha query: {e}")
            return ToolResult(
                success=False,
                result=None,
                error=f"Unexpected error: {str(e)}",
                source="wolfram_alpha"
            )
    
    def _generate_response(self, state: AgentState) -> AgentState:
        """Generate the final response"""
        
        # Create the response prompt based on whether we have Wolfram data
        if state["needs_wolfram"] and state.get("wolfram_result") and state.get("used_wolfram"):
            response_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant. The user asked a question that required computational/factual lookup, and you received results from Wolfram Alpha.

Based on the Wolfram Alpha results, provide a clear, helpful response to the user's original question. 
- Explain the results in an understandable way
- If there are multiple pieces of information, organize them clearly
- If the Wolfram Alpha query failed, acknowledge this and try to provide what help you can
- Be conversational and helpful
- Don't mention "Wolfram Alpha" unless it's relevant to explain the source

Be conversational and helpful."""),
                ("human", "Original question: {original_query}"),
                ("human", "Wolfram Alpha results: {wolfram_result}")
            ])
            
            response = self.llm.invoke(
                response_prompt.format_messages(
                    original_query=state["user_query"],
                    wolfram_result=state["wolfram_result"]
                )
            )
        else:
            # Direct response without Wolfram Alpha
            direct_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful AI assistant. Respond to the user's question directly and conversationally. 
This question doesn't require computational tools or factual lookups - just provide a helpful, engaging response.

Be friendly, informative, and conversational."""),
                ("human", "{query}")
            ])
            
            response = self.llm.invoke(
                direct_prompt.format_messages(query=state["user_query"])
            )
        
        # Update the instance variable for tracking
        self.last_used_wolfram = state.get("used_wolfram", False)
        
        return {
            **state,
            "final_response": response.content,
            "messages": state["messages"] + [AIMessage(content=response.content)]
        }
    
    def chat(self, user_message: str, debug: bool = False) -> str:
        """
        Process a user message and return a response
        
        Args:
            user_message: The user's message
            debug: Whether to print debug information
            
        Returns:
            The agent's response
        """
        try:
            # Initialize state
            initial_state = {
                "messages": [HumanMessage(content=user_message)],
                "user_query": user_message,
                "needs_wolfram": False,
                "wolfram_result": None,
                "final_response": None,
                "used_wolfram": False
            }
            
            # Run the workflow
            final_state = self.app.invoke(initial_state)
            
            # Update instance variable
            self.last_used_wolfram = final_state.get("used_wolfram", False)
            
            if debug:
                logger.info(f"Debug Info:")
                logger.info(f"- Needs Wolfram: {final_state['needs_wolfram']}")
                logger.info(f"- Used Wolfram: {final_state.get('used_wolfram', False)}")
                if final_state.get('wolfram_result'):
                    logger.info(f"- Wolfram Result: {final_state['wolfram_result'][:200]}...")
                logger.info(f"- Final Response Length: {len(final_state['final_response'])}")
                logger.info("-" * 50)
            
            return final_state["final_response"]
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return f"I apologize, but I encountered an error processing your request: {str(e)}"
    
    def get_workflow_diagram(self) -> str:
        """Get a text representation of the workflow"""
        return """
LangGraph Workflow:
        
[User Query] 
     ↓
[Classifier] → Determines if Wolfram Alpha is needed
     ↓
[Decision Point]
     ↓                    ↓
[Wolfram Search]      [Direct Response]
     ↓                    ↓
[Generate Response] ← [Generate Response]
     ↓
[Final Answer]
        """