"""
UPSC Answer Formatter - Agents

This file contains agent definitions and LLM initialization for the UPSC answer formatting system.
"""

import os
import json
import base64
import re
from typing import Dict, List, Any, Optional, TypedDict, Union

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langchain_mistralai import ChatMistralAI

# Import prompts
from ..prompts.prompts import (
    DATA_VERIFICATION_PROMPT,
    DATA_FORMATTER_PROMPT,
    OCR_EXTRACTION_PROMPT,
    UPSC_DATA_FORMAT,
    first_prompt,
    middle_prompt,
    last_prompt
)

# Define the state structure
class AgentState(TypedDict):
    """State for the LangGraph workflow."""
    messages: List[AnyMessage]        # Messages exchanged in the conversation
    ocr_texts: List[str]              # Raw texts extracted from OCR for each image
    is_relevant: bool                 # Whether the data is relevant for UPSC formatting
    has_valid_format: bool            # Whether the data has the correct format
    formatted_data: Optional[Dict[str, Any]]  # Data in the target format
    error: Optional[str]              # Error message if any
    status: str                       # Current status of the workflow

# Initialize LLM
def init_llm(api_key=None):
    """Initialize the LLM with the provided API key."""
    if api_key:
        os.environ["MISTRAL_API_KEY"] = api_key
    
    return ChatMistralAI(
        model="mistral-large-latest",
        temperature=0,
        api_key=os.environ.get("MISTRAL_API_KEY")
    )



# OCR Agent - Extracts text from images using MistralAI Vision capabilities
class OCRProcessor:
    def __init__(self, api_key=None):
        """Initialize OCR processor with the provided API key."""
        if api_key:
            os.environ["MISTRAL_API_KEY"] = api_key
        
        self.mistral_client = ChatMistralAI(
            model="pixtral-large-latest",
            api_key=os.environ.get("MISTRAL_API_KEY"),
            max_tokens=2000,
            temperature=0.2
        )
    
    def process_image(self, image_path: str) -> str:
        """Process an image and extract text using MistralAI OCR."""
        try:
            # Open the image
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            # Convert to base64 for API transmission
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            return self._extract_text_with_mistral(image_base64)
        except Exception as e:
            return f"OCR Error: {str(e)}"
    
    def process_base64_image(self, base64_str: str) -> str:
        """Process a base64 encoded image and extract text using MistralAI OCR."""
        try:
            return self._extract_text_with_mistral(base64_str)
        except Exception as e:
            return f"OCR Error: {str(e)}"
    
    def process_multiple_images(self, base64_images: List[str]) -> List[str]:
        """Process multiple base64 encoded images with size control."""
        results = []
        
        # Limit number of images processed if there are too many
        if len(base64_images) > 5:
            print(f"Warning: Processing only 5 of {len(base64_images)} images to avoid token limits")
            base64_images = base64_images[:5]
            
        for idx, img in enumerate(base64_images):
            try:
                # Select the appropriate prompt
                if len(base64_images) == 1:
                    prompt = first_prompt
                else:
                    if idx == 0:
                        prompt = first_prompt
                    elif idx == len(base64_images) - 1:
                        prompt = last_prompt
                    else:
                        prompt = middle_prompt
                
                message = HumanMessage(
                    content=[
                        {
                            "type": "text", 
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img}"
                            }
                        }
                    ]
                )
                
                # Get response from MistralAI
                response = self.mistral_client.invoke([message])
                
                # Extract text from response
                extracted_text = response.content
                if len(extracted_text) > 30000:  # ~30K chars limit
                    extracted_text = extracted_text[:30000] + "\n...[content truncated due to length]"
                results.append(extracted_text)
                
            except Exception as e:
                results.append(f"MistralAI OCR Error on image {idx+1}: {str(e)}")
        
        return results
            
    def _extract_text_with_mistral(self, image_base64: str) -> str:
        """Use MistralAI to extract text from image using the basic OCR prompt."""
        try:
            # Prepare the message for MistralAI with the image
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": OCR_EXTRACTION_PROMPT
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            )
            
            # Get response from MistralAI
            response = self.mistral_client.invoke([message])
            
            # Extract text from response
            extracted_text = response.content
            
            return extracted_text
        except Exception as e:
            return f"MistralAI OCR Error: {str(e)}"

# Data Verification Agent
def data_verification_agent(state: AgentState, llm) -> AgentState:
    """Verify if the OCR text is relevant to UPSC answers and has proper format."""
    ocr_texts = state["ocr_texts"]
    
    if not ocr_texts or len(ocr_texts) == 0:
        state["is_relevant"] = False
        state["has_valid_format"] = False
        state["error"] = "No OCR text provided."
        state["status"] = "failed_verification"
        return state
    
    # Estimate token count for all texts combined
    total_text_length = sum(len(text) for text in ocr_texts)
    estimated_tokens = total_text_length // 4  # Rough estimation
    
    # Check if we need to truncate
    if estimated_tokens > 100000:  # Keep well below the 131K limit
        # Option 1: Use only a subset of the texts
        if len(ocr_texts) > 3:
            # Take first, middle, and last
            subset_indices = [0, len(ocr_texts)//2, len(ocr_texts)-1]
            ocr_texts = [ocr_texts[i] for i in subset_indices]
        else:
            # Option 2: Truncate each text
            ocr_texts = [text[:25000] for text in ocr_texts]  # ~25K chars per text
    
    # For multiple images, combine the text with separators for verification
    combined_text = "\n\n--- IMAGE SEPARATION ---\n\n".join([
        f"[Image {i+1} of {len(ocr_texts)}]\n{text[:25000]}" 
        for i, text in enumerate(ocr_texts)
    ])
    
    # Prompt the LLM to verify relevance and format
    messages = [
        HumanMessage(content=DATA_VERIFICATION_PROMPT.format(ocr_text=combined_text))
    ]
    
    response = llm.invoke(messages)
    
    try:
        # Extract JSON from response
        content = response.content
        if isinstance(content, str):
            # Find JSON-like content in the response
            json_match = re.search(r'{.*}', content, re.DOTALL)
            if json_match:
                verification_result = json.loads(json_match.group())
            else:
                # Fall back to parsing what we can
                verification_result = {
                    "is_relevant": "relevant" in content.lower() and "not relevant" not in content.lower(),
                    "has_valid_format": "valid format" in content.lower() and "invalid format" not in content.lower(),
                    "reason": "Extracted from text content"
                }
        else:
            verification_result = {"is_relevant": False, "has_valid_format": False, "reason": "Invalid LLM response"}
            
        # Update the state
        state["is_relevant"] = verification_result.get("is_relevant", False)
        state["has_valid_format"] = verification_result.get("has_valid_format", False)
        
        if not state["is_relevant"] or not state["has_valid_format"]:
            state["status"] = "failed_verification"
            state["error"] = verification_result.get("reason", "Failed verification check")
        else:
            state["status"] = "verified"
            
    except Exception as e:
        state["is_relevant"] = False
        state["has_valid_format"] = False
        state["error"] = f"Verification processing error: {str(e)}"
        state["status"] = "failed_verification"
    
    return state

# Data Formatter Agent
def data_formatter_agent(state: AgentState, llm) -> AgentState:
    """Convert the verified OCR text into the required structured format."""
    ocr_texts = state["ocr_texts"]
    
    # If verification failed, skip formatting
    if not state["is_relevant"] or not state["has_valid_format"]:
        state["status"] = "skipped_formatting"
        return state
    
    # For single image or processed by specialized prompts, we may already have formatted data
    if len(ocr_texts) == 1:
        try:
            # Try to extract JSON directly from the OCR result
            json_match = re.search(r'{.*}', ocr_texts[0], re.DOTALL)
            if json_match:
                formatted_data = json.loads(json_match.group())
                
                # Check if we have all required fields or need additional processing
                required_fields = ["question", "answer", "feedback"]
                if all(field in formatted_data for field in required_fields):
                    # We have a complete formatted result
                    state["formatted_data"] = formatted_data
                    state["status"] = "formatted"
                    return state
        except:
            # If JSON extraction fails, continue with standard processing
            pass

    # For multiple images that were processed with page-specific prompts, merge the results
    if len(ocr_texts) > 1:
        try:
            # Extract JSON from each OCR result
            json_results = []
            for idx, text in enumerate(ocr_texts):
                json_match = re.search(r'{.*}', text, re.DOTALL)
                if json_match:
                    try:
                        json_data = json.loads(json_match.group())
                        json_results.append(json_data)
                    except json.JSONDecodeError:
                        # If we can't parse the JSON, add the text for later processing
                        json_results.append({"text": text, "index": idx})
                else:
                    json_results.append({"text": text, "index": idx})
            
            # If we have valid JSON results, merge them
            if json_results and all(isinstance(result, dict) and not result.get('index', None) for result in json_results):
                merged_result = merge_json_blocks(json_results)
                state["formatted_data"] = merged_result
                state["status"] = "formatted"
                return state
        except Exception as e:
            # If merging fails, continue with standard processing
            pass
    
    # Prepare OCR text with index awareness for multiple images as fallback
    formatted_ocr = "\n\n--- IMAGE SEPARATION ---\n\n".join([
        f"[Image {i+1} of {len(ocr_texts)}]\n{text}" 
        for i, text in enumerate(ocr_texts)
    ])
    
    # Prompt the LLM to extract and format the data using the standard prompt
    messages = [
        HumanMessage(content=DATA_FORMATTER_PROMPT.format(ocr_text=formatted_ocr))
    ]
    
    response = llm.invoke(messages)
    
    try:
        # Extract JSON from response
        content = response.content
        if isinstance(content, str):
            # Find JSON-like content in the response
            json_match = re.search(r'{.*}', content, re.DOTALL)
            if json_match:
                formatted_data = json.loads(json_match.group())
            else:
                # Attempt to parse the entire response as JSON
                formatted_data = json.loads(content)
        else:
            raise ValueError("Invalid LLM response format")
            
        # Validate that the response matches our expected format
        for key in UPSC_DATA_FORMAT:
            if key not in formatted_data:
                if key == "word_limit":
                    formatted_data[key] = 150  # Default value
                elif key == "maximum_marks":
                    formatted_data[key] = 10   # Default value
                else:
                    formatted_data[key] = None
                
        state["formatted_data"] = formatted_data
        state["status"] = "formatted"
        
    except Exception as e:
        state["error"] = f"Formatting error: {str(e)}"
        state["status"] = "failed_formatting"
        state["formatted_data"] = None
    
    return state

# Helper function to merge multiple JSON outputs (for multi-image processing)
def merge_json_blocks(json_outputs: List[Dict]) -> Dict[str, Any]:
    """Merge multiple JSON outputs into a single cohesive output."""
    if not json_outputs:
        return {"error": "No outputs to merge"}
    
    # Initialize the merged result with comprehensive structure
    merged = {
        "question": "",
        "answer": "",
        "feedback": [],
        "word_limit": 0,
        "maximum_marks": 0,
        "total_marks": None
    }
    
    # First pass: Extract question, word_limit, maximum_marks from first page
    first_page = json_outputs[0] if json_outputs else {}
    if "question" in first_page:
        merged["question"] = first_page["question"]
    if "word_limit" in first_page and first_page["word_limit"]:
        merged["word_limit"] = first_page["word_limit"]
    if "maximum_marks" in first_page and first_page["maximum_marks"]:
        merged["maximum_marks"] = first_page["maximum_marks"]
    
    # Second pass: Extract total_marks from last page
    last_page = json_outputs[-1] if json_outputs else {}
    if "total_marks" in last_page and last_page["total_marks"]:
        merged["total_marks"] = last_page["total_marks"]
    
    # Third pass: Merge all answers and feedback
    for output in json_outputs:
        # Append answers with proper formatting
        if "answer" in output and output["answer"]:
            if merged["answer"]:
                merged["answer"] += "\n\n--- NEXT PAGE ---\n\n"
            merged["answer"] += output["answer"]
        
        # Combine feedback
        if "feedback" in output and isinstance(output["feedback"], list):
            merged["feedback"].extend(output["feedback"])
    
    # Clean up the merged result
    if not merged["question"]:
        merged.pop("question", None)
    if merged["word_limit"] == 0:
        merged.pop("word_limit", None)
    if merged["maximum_marks"] == 0:
        merged.pop("maximum_marks", None)
    if merged["total_marks"] is None:
        merged.pop("total_marks", None)
    
    return merged