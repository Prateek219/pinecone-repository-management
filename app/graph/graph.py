"""
UPSC Answer Formatter - LangGraph Workflow

This file contains the LangGraph workflow for the UPSC answer formatting system.
"""

import json
from typing import Literal, Dict, Any, Optional, List

import langgraph.graph as lg
from langgraph.graph import END, StateGraph

# Import agents and state definitions
from .agents import (
    AgentState,
    init_llm,
    OCRProcessor,
    data_verification_agent,
    data_formatter_agent,
    merge_json_blocks
)

# Define the workflow logic
def decide_next_step(state: AgentState) -> Literal["data_formatter", "end"]:
    """Determine the next step in the workflow based on the current state."""
    status = state["status"]
    
    if status == "verified":
        return "data_formatter"
    elif status in ["failed_verification", "failed_formatting", "formatted"]:
        return "end"
    
    # Default fallback
    return "end"

# Create the LangGraph workflow
def create_upsc_formatting_workflow(api_key=None) -> StateGraph:
    """Create and return the LangGraph for UPSC answer formatting."""
    # Initialize the LLM
    llm = init_llm(api_key)
    
    # Initialize the workflow graph
    workflow = StateGraph(AgentState)
    
    # Add the nodes (agents)
    workflow.add_node("data_verification", lambda state: data_verification_agent(state, llm))
    workflow.add_node("data_formatter", lambda state: data_formatter_agent(state, llm))
    
    # Set the entry point
    workflow.set_entry_point("data_verification")
    
    # Define the edges (transitions between agents)
    workflow.add_conditional_edges(
        "data_verification",
        decide_next_step,
        {
            "data_formatter": "data_formatter",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "data_formatter",
        decide_next_step,
        {
            "end": END
        }
    )
    
    return workflow.compile()

# Main executor function
def process_upsc_answer(
    image_paths=None, 
    base64_images=None, 
    ocr_texts=None, 
    api_key=None
) -> Dict[str, Any]:
    """
    Process a UPSC answer through the formatting workflow.
    
    Args:
        image_paths: List of paths to image files (optional)
        base64_images: List of base64 encoded image strings (optional)
        ocr_texts: List of pre-extracted OCR texts (optional, if OCR is already done)
        api_key: API key for MistralAI (optional)
        
    Returns:
        The final state after processing or just the formatted data if successful
    """
    # Create OCR processor
    ocr_processor = OCRProcessor(api_key)
    
    # Extract text if needed
    extracted_texts = []
    
    if ocr_texts:
        # Convert single OCR text to list if needed
        if isinstance(ocr_texts, str):
            extracted_texts = [ocr_texts]
        else:
            extracted_texts = ocr_texts
    elif image_paths:
        # Process multiple image paths
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        
        for path in image_paths:
            text = ocr_processor.process_image(path)
            extracted_texts.append(text)
    elif base64_images:
        # Process multiple base64 images
        if isinstance(base64_images, str):
            base64_images = [base64_images]
        
        # Use batch processing for multiple images
        extracted_texts = ocr_processor.process_multiple_images(base64_images)
    else:
        return {"error": "No input provided. Please provide image_paths, base64_images, or ocr_texts."}
    
    # Create the initial state
    initial_state = AgentState(
        messages=[],
        ocr_texts=extracted_texts,
        is_relevant=False,
        has_valid_format=False,
        formatted_data=None,
        error=None,
        status="initialized"
    )
    
    total_chars = sum(len(text) for text in extracted_texts)
    print(f"Processing {len(extracted_texts)} texts with total {total_chars} characters (~{total_chars//4} tokens)")

    if total_chars//4 > 100000:
        print("WARNING: Text is very large and may exceed token limits!")
        # Truncate texts if needed
        extracted_texts = [text[:25000] for text in extracted_texts]
        print(f"Texts truncated to {sum(len(text) for text in extracted_texts)} chars")
    
    # Create the workflow
    workflow = create_upsc_formatting_workflow(api_key)
    
    # Run the workflow
    result = workflow.invoke(initial_state)
    
    # Return just the formatted data if successful
    if result["status"] == "formatted" and result["formatted_data"]:
        return result["formatted_data"]
    
    # Otherwise return the complete state for debugging
    return result

# Example of usage
# if __name__ == "__main__":
#     # Example OCR text from a UPSC answer sheet
#     sample_ocr_text = """
#     VAJIRAM & RAVI
    
#     (Q. No.) 3
    
#     The snowfall feeds to the glaciers which are source of Himalayan rivers. 
#     Agriculture - These hold immense importance for Rabi crops such as wheat.
#     However, heavy rain and hailstorms can be damaging to the crops.
    
#     Disasters during summer and monsoon seasons:
    
#     1. Occasionally they may interact with Monsoon trough and lead to cloudburst, lightning, etc.
#     2. Leh Floods (2010), Uttarakhand floods (2013), Kashmir floods (2014) etc. have been linked to Western Disturbances causing catastrophic losses.
    
#     Conclusion can be that weak western disturbances are associated with crop failure and water problems across North India and strong WD helps fight water scarcity.
    
#     Introduction: 0.5
#     Body: 3
#     Conclusion: —
#     Marks: 3.5
    
#     Suggestions: Try to write conclusion as well.
#     """
    
#     # Use your API key here
#     api_key = "your-mistral-api-key-here"
    
#     # Process the sample text
#     result = process_upsc_answer(ocr_texts=sample_ocr_text, api_key=api_key)
    
#     # Print the result
#     print(json.dumps(result, indent=2))