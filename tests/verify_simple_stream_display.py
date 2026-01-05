import sys
import os
from rich.console import Console

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.cli_monitor import SimpleEventLogger

def test_simple_stream():
    console = Console()
    logger = SimpleEventLogger(console)
    
    print("Testing streaming output...")
    
    # Simulate Agent 1 streaming
    logger.log_token("agent1", "Hello", "Agent One")
    logger.log_token("agent1", " world", "Agent One")
    logger.log_token("agent1", "!", "Agent One")
    
    # Simulate Agent 2 streaming
    logger.log_token("agent2", "I", "Agent Two")
    logger.log_token("agent2", " am", "Agent Two")
    logger.log_token("agent2", " here", "Agent Two")
    logger.log_token("agent2", ".", "Agent Two")
    
    # Check newline handling if we switch back to agent 1
    logger.log_token("agent1", "Back", "Agent One")
    logger.log_token("agent1", " again.", "Agent One")
    
    # mimic clean up
    if logger.last_stream_agent:
        console.print()
        logger.last_stream_agent = None
        
    print("Done.")

if __name__ == "__main__":
    test_simple_stream()
