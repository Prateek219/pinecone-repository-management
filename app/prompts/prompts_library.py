# prompts.py

first_prompt = """ 
Hello! You will be transcribing scanned images of handwritten UPSC answers. Please extract the text **exactly as written**, even if it contains spelling mistakes. The structure of the answer is important and must follow the formatting guidelines below.

### Guidelines:

1. **Transcribe into the following format**:
   - Use `[PARAGRAPH]` for continuous blocks of text.
   - Use `[HEADING]` for headings and subheadings (combine into one field).
   - Use `[BULLET POINT TABLE]` for bulleted or numbered lists.
   -  - **Special Structures**:
     - [TABLE] for comparison or data tables.
     - [FLOWCHART] for diagrams or flow processes.
   - Identify flowcharts or comparison tables and label them accordingly if present.
   - Maintain line breaks and content structure as closely as possible.
   - **Never break or rearrange logical flow** — Introduction → Body → Subheadings → Bullet Points → Conclusion.
   2. **Tables and Flowcharts**:

- **Tables** (`[TABLE]`):
  - If a table or comparison is found, mark it with `[TABLE]`.
  - Represent it as simple text using pipes (`|`) and dashes (`---`) for columns.
  - Example:
    ```
    [TABLE]
    Column1 | Column2
    --- | ---
    Point A | Point B
    Advantage | Disadvantage
    ```

- **Flowcharts** (`[FLOWCHART]`):
  - If a flowchart or process diagram is found, mark it with `[FLOWCHART]`.
  - Represent the flow using arrows (`→`) between steps.
  - Example:
    ```
    [FLOWCHART]
    Step 1 → Step 2 → Step 3
    ```

2. **Include the question** at the top, if available in the answer.

3. **`feedback`** *(as structured pairs)*  
   - Extract each feedback comment **as a pair**:
     ```
     ["<related_text>", "<feedback_text>"]
     ```
   - If feedback refers to a heading, paragraph, or bullet point — use the closest or most relevant text from the answer as the `related_text`.
   - Include general advice too (e.g., "Work on structure") and pair it with a suitable related text (or `"General"` if no specific text).

4. **Output Format**:
   Return your response in the following JSON format:
```json
{
  "question": "<question_text>",
  "answer": "Answer:\n\n[PARAGRAPH] <text>\n\n[HEADING] <heading_text>\n\n[BULLET POINT TABLE] <bullet_points>",
  "feedback": " [
    ["Swadeshi movement boycotted foreign products", "Good point on cultural assertion."],
    ["General", "Try to improve the flow and coherence of arguments."],
    ["History celebrating Indian kings", "Nice historical connection."]
  ]",
  "word_limit": <estimated_word_limit>,
  "maximum_marks": <max_marks>"
}
```

5. **If handwriting is unclear**, flag it and request clarification.

6. **Preserve original spelling errors**, unless it's a proper noun or clearly wrong — in which case, provide a comment in `[FEEDBACK]`.

7. **Keep temperature at 0.** Do not add your own interpretations or make changes to the student’s content.

---

Let me know if you also want to include flow diagrams or comparison tables as markdown-style structures.
"""

middle_prompt = """
Hello! You will be transcribing scanned images of handwritten UPSC answer continuation pages.  
These pages **may not contain a question**.  
Focus only on extracting the **answer content** and **feedback** based on the handwriting.

### Guidelines:

1. **Only Extract Answer and Feedback**:
   - Do not include `question`, `word_limit`, or `maximum_marks` fields.
   - Only generate `answer` and `feedback`.

2. **Maintain Structure**:
   - Use `[PARAGRAPH]` for continuous blocks of text.
   - Use `[HEADING]` for headings and subheadings.
   - Use `[BULLET POINT TABLE]` for bullet points or numbered lists.
    - **Special Structures**:
     - [TABLE] for comparison or data tables.
     - [FLOWCHART] for diagrams or flow processes.
   - Capture any flow diagrams or comparison tables and label accordingly.
   - Maintain the logical flow of the answer, no breaking.
   **Tables** (`[TABLE]`):
  - If a table or comparison is found, mark it with `[TABLE]`.
  - Represent it as simple text using pipes (`|`) and dashes (`---`) for columns.
  - Example:
    ```
    [TABLE]
    Column1 | Column2
    --- | ---
    Point A | Point B
    Advantage | Disadvantage
    ```

- **Flowcharts** (`[FLOWCHART]`):
  - If a flowchart or process diagram is found, mark it with `[FLOWCHART]`.
  - Represent the flow using arrows (`→`) between steps.
  - Example:
    ```
    [FLOWCHART]
    Step 1 → Step 2 → Step 3
    ```


3.. **`feedback`** *(as structured pairs)*  
   - Extract each feedback comment **as a pair**:
     ```
     ["<related_text>", "<feedback_text>"]
     ```
   - If feedback refers to a heading, paragraph, or bullet point — use the closest or most relevant text from the answer as the `related_text`.
   - Include general advice too (e.g., "Work on structure") and pair it with a suitable related text (or `"General"` if no specific text).


4. **Output Format**:
Return your response strictly in this JSON format:
```json
{
  "answer": "Answer:\n\n[PARAGRAPH] <text>\n\n[HEADING] <heading_text>\n\n[BULLET POINT TABLE] <bullet_points>",
  "feedback":  [
    ["Swadeshi movement boycotted foreign products", "Good point on cultural assertion."],
    ["General", "Try to improve the flow and coherence of arguments."],
    ["History celebrating Indian kings", "Nice historical connection."]
  ],
}
```

5. **Additional Instructions**:
   - Preserve original spelling mistakes unless it's a technical/proper noun; if corrected, note it inside `[FEEDBACK]`.
   - Maintain original structure, don't change meaning.
   - If handwriting is unclear, ask for clarification.
   - Keep temperature at 0.

"""

last_prompt = """
Here’s your **
Hello! You will be transcribing the **last page** of a handwritten UPSC answer copy.

This page may contain:
- Final portion of the student’s **answer**
- Margin or end-of-page **feedback**
- Overall **total marks**
- Additional evaluator **advice or suggestions**

---

### ✅ What to Extract:

1. **`answer`**  
   - Transcribe the remaining part of the answer.  
   - Maintain structure using tags:  
     - `[PARAGRAPH]`, `[HEADING]`, `[BULLET POINT TABLE]`, etc.
    - **Special Structures**:
     - [TABLE] for comparison or data tables.
     - [FLOWCHART] for diagrams or flow processes.  
   - Preserve original spellings (except for obvious proper nouns/technical terms).
   - Preserve the logical answer structure fully.
   **Tables** (`[TABLE]`):
  - If a table or comparison is found, mark it with `[TABLE]`.
  - Represent it as simple text using pipes (`|`) and dashes (`---`) for columns.
  - Example:
    ```
    [TABLE]
    Column1 | Column2
    --- | ---
    Point A | Point B
    Advantage | Disadvantage
    ```

- **Flowcharts** (`[FLOWCHART]`):
  - If a flowchart or process diagram is found, mark it with `[FLOWCHART]`.
  - Represent the flow using arrows (`→`) between steps.
  - Example:
    ```
    [FLOWCHART]
    Step 1 → Step 2 → Step 3
    ```


2. **`feedback`** *(as structured pairs)*  
   - Extract each feedback comment **as a pair**:
     ```
     ["<related_text>", "<feedback_text>"]
     ```
   - If feedback refers to a heading, paragraph, or bullet point — use the closest or most relevant text from the answer as the `related_text`.
   - Include general advice too (e.g., "Work on structure") and pair it with a suitable related text (or `"General"` if no specific text).

3. **`total_marks`**  
   - Extract total marks written on the page (e.g., `"7/10"`, `"Marks: 8"`).  
   - Return as a **string**.

---

### 🧾 Output JSON Format:
```json
{
  "answer": "Answer:\n\n[PARAGRAPH] ... \n\n[HEADING] ... \n\n[BULLET POINT TABLE] ...",
  "feedback": [
    ["Swadeshi movement boycotted foreign products", "Good point on cultural assertion."],
    ["General", "Try to improve the flow and coherence of arguments."],
    ["History celebrating Indian kings", "Nice historical connection."]
  ],
  "total_marks": "7/10"
}
```

---

### ⚠️ Notes:
- ❌ Do **not** include question, word_limit, or maximum_marks.
- ✅ If marks are unclear, use `"total_marks": null`
- ✅ Use temperature **0** for factual and faithful transcription.
- ✅ Do **not invent** feedback — only transcribe what’s written.
"""
