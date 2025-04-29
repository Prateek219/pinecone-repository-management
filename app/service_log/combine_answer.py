import json
import re

def clean_markdown_json(raw_str):
    """
    Clean JSON string from markdown code blocks and prepare for parsing.
    
    Args:
        raw_str (str): Raw string potentially containing markdown JSON blocks
        
    Returns:
        str: Cleaned JSON string ready for parsing
    """
    # Remove markdown code block markers
    clean_str = re.sub(r'```json|```', '', raw_str, flags=re.IGNORECASE).strip()
    
    # Return the cleaned JSON string
    return clean_str

def parse_json_block(block_str):
    """
    Parse a JSON string block using multiple methods if needed.
    
    Args:
        block_str (str): String containing JSON data
        
    Returns:
        dict: Parsed JSON object or None if parsing fails
    """
    # Clean the string first
    clean_str = clean_markdown_json(block_str)
    
    # Try standard JSON parsing first
    try:
        return json.loads(clean_str)
    except json.JSONDecodeError as e:
        print(f"Standard JSON parsing failed: {e}")
        
        # Try to fix common issues with escaped single quotes in the JSON
        try:
            # Replace single quotes with double quotes for JSON keys/properties
            fixed_str = re.sub(r'([{,])\s*\'([^\']+)\'\s*:', r'\1 "\2":', clean_str)
            return json.loads(fixed_str)
        except json.JSONDecodeError as e:
            print(f"Fixed quotes parsing failed: {e}")
            
            # Try using a manual approach for extracting data
            result = {}
            
            # Extract fields using regex
            try:
                # Extract question if present
                question_match = re.search(r'"question":\s*"(.*?)(?<!\\)"', clean_str, re.DOTALL)
                if question_match:
                    result["question"] = question_match.group(1).replace('\\n', '\n')
                
                # Extract answer
                answer_match = re.search(r'"answer":\s*"(.*?)(?<!\\)"(?=,|\s*})', clean_str, re.DOTALL)
                if answer_match:
                    result["answer"] = answer_match.group(1).replace('\\n', '\n')
                
                # Extract word limit if present
                word_limit_match = re.search(r'"word_limit":\s*(\d+)', clean_str)
                if word_limit_match:
                    result["word_limit"] = int(word_limit_match.group(1))
                
                # Extract maximum marks if present
                max_marks_match = re.search(r'"maximum_marks":\s*(\d+)', clean_str)
                if max_marks_match:
                    result["maximum_marks"] = int(max_marks_match.group(1))
                
                # Extract total marks if present
                total_marks_match = re.search(r'"total_marks":\s*"(.*?)"', clean_str)
                if total_marks_match:
                    result["total_marks"] = total_marks_match.group(1)
                
                # Extract feedback array
                feedback_match = re.search(r'"feedback":\s*(\[.*?\])', clean_str, re.DOTALL)
                if feedback_match:
                    # Try to parse the feedback JSON array
                    try:
                        feedback_str = feedback_match.group(1)
                        # Fix potential issues with single quotes
                        feedback_str = feedback_str.replace("'", '"')
                        result["feedback"] = json.loads(feedback_str)
                    except json.JSONDecodeError:
                        # If that fails, try to extract the feedback items manually
                        feedback_items = re.findall(r'\["(.*?)",\s*"(.*?)"\]', feedback_match.group(1))
                        result["feedback"] = [[item[0], item[1]] for item in feedback_items]
                
                # Only return if we've successfully extracted at least one key field
                if result and ("answer" in result or "question" in result):
                    print("Successfully extracted data using regex")
                    return result
                else:
                    print("Failed to extract key fields with regex")
                    return None
            except Exception as e:
                print(f"Manual extraction failed: {e}")
                return None

def merge_json_blocks(raw_inputs):
    print(raw_inputs)
    """
    Parse multiple JSON blocks from markdown and merge them.
    
    Args:
        raw_inputs (list): List of strings containing JSON data, potentially in markdown code blocks
        
    Returns:
        dict: Merged JSON object
    """
    print(f"Processing {len(raw_inputs)} input blocks")
    
    # Parse all JSON blocks
    parsed_blocks = []
    for i, block in enumerate(raw_inputs):
        print(f"\nProcessing block {i+1}/{len(raw_inputs)}")
        parsed = parse_json_block(block)
        if parsed:
            parsed_blocks.append(parsed)
            print(f"✓ Successfully parsed block {i+1}")
        else:
            print(f"✗ Failed to parse block {i+1}")
    
    if not parsed_blocks:
        raise ValueError("No valid JSON blocks could be parsed.")
    
    # Extract common fields from the first available block
    question = ""
    word_limit = ""
    maximum_marks = ""
    
    for block in parsed_blocks:
        if "question" in block and not question:
            question = block["question"]
        if "word_limit" in block and not word_limit:
            word_limit = block["word_limit"]
        if "maximum_marks" in block and not maximum_marks:
            maximum_marks = block["maximum_marks"]
    
    # Get total marks from the last block if available
    final_total_marks = ""
    for block in reversed(parsed_blocks):
        if "total_marks" in block:
            final_total_marks = block["total_marks"]
            break
    
    if not final_total_marks:
        final_total_marks = "0/0"
    
    
    answers = []
    for block in parsed_blocks:
        if "answer" in block:
            answers.append(block["answer"])
    
    merged_feedback = []
    for block in parsed_blocks:
        if "feedback" in block:
            merged_feedback.extend(block["feedback"])
    
    # Build final output
    final_output = {
        "question": question,
        "word_limit": word_limit,
        "maximum_marks": maximum_marks,
        "answer": [{"text": "\n\n".join(answers)}],
        "feedback": merged_feedback,
        "total_marks": final_total_marks
    }
    
    print("\n✓ Successfully created merged output")
    print(final_output)
    return final_output