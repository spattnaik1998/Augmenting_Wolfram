# Backend - main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from langgraph_agent import WolframAlphaLangGraphAgent
import logging
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Wolfram Alpha Chatbot API",
    description="API for chatbot powered by GPT-4o and Wolfram Alpha via LangGraph",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatMessage(BaseModel):
    id: Optional[int] = None
    type: str  # 'user' or 'bot'
    content: str
    timestamp: Optional[str] = None
    usedWolfram: Optional[bool] = False

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    content: str
    usedWolfram: bool
    timestamp: str
    processingTime: float

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    agent_initialized: bool

# Global agent instance
agent = None

@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup"""
    global agent
    try:
        logger.info("Initializing Wolfram Alpha LangGraph Agent...")
        agent = WolframAlphaLangGraphAgent()
        logger.info("Agent initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {str(e)}")
        logger.error(traceback.format_exc())

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if agent else "unhealthy",
        timestamp=datetime.now().isoformat(),
        agent_initialized=agent is not None
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Main chat endpoint"""
    if not agent:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Please check server logs."
        )
    
    try:
        start_time = datetime.now()
        
        # Log the request
        logger.info(f"Received chat request: {request.message[:100]}...")
        
        # Process the message with the agent
        response_content = agent.chat(request.message, debug=False)
        logger.info(f"Agent decision - Used Wolfram: {agent.last_used_wolfram if hasattr(agent, 'last_used_wolfram') else 'Unknown'}")
        
        
        # Determine if Wolfram Alpha was used
        # This is a simple heuristic - in a real implementation, you'd get this from the agent
        used_wolfram = agent.last_used_wolfram if hasattr(agent, 'last_used_wolfram') else False
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Response generated in {processing_time:.2f}s, Wolfram used: {used_wolfram}")
        
        return ChatResponse(
            content=response_content,
            usedWolfram=used_wolfram,
            timestamp=end_time.isoformat(),
            processingTime=processing_time
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing your request: {str(e)}"
        )

def _heuristic_wolfram_detection(response_content: str) -> bool:
    """
    Simple heuristic to detect if Wolfram Alpha was used
    In a real implementation, this would be returned by the agent
    """
    wolfram_indicators = [
        "wolfram alpha",
        "computational",
        "calculation",
        "integral",
        "derivative",
        "equation",
        "conversion",
        "according to",
        "results show",
        "computed"
    ]
    
    response_lower = response_content.lower()
    return any(indicator in response_lower for indicator in wolfram_indicators)

@app.get("/api/status")
async def get_status():
    """Get detailed status information"""
    return {
        "agent_initialized": agent is not None,
        "timestamp": datetime.now().isoformat(),
        "api_version": "1.0.0",
        "endpoints": [
            "/",
            "/api/chat",
            "/api/status"
        ]
    }

@app.get("/api/examples")
async def get_examples():
    """Get example queries for the frontend"""
    return {
        "wolfram_examples": [
            "What is the integral of x² + 3x + 2?",
            "Convert 100 fahrenheit to celsius",
            "What is the population of Tokyo?",
            "Solve the equation 2x + 5 = 15",
            "Calculate the compound interest on $1000 at 5% for 10 years",
            "What is the derivative of sin(x) * cos(x)?",
            "Convert 50 miles to kilometers"
        ],
        "general_examples": [
            "Tell me a joke about mathematics",
            "How are you doing today?",
            "What's your favorite color?",
            "Explain quantum computing in simple terms",
            "What's the weather like?",
            "Tell me about artificial intelligence"
        ]
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )