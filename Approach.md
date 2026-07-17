# Approach Document

## Tech Stack
- **Framework**: FastAPI (Python)
- **Database**: Raw SQLite (basic SQL)
- **AI Tool**: Google Gemini
- **Validation**: Pydantic (To ensure the API gets the correct data format)

## Data Model & Parsing
To read the document correctly, the parser keeps track of which section it is currently in. This ensures that even if a subheading is numbered incorrectly (like jumping from Heading 2 to Heading 4), it still gets placed under the correct parent section. 

To handle sections that have the exact same name (like two "Error Codes" sections), the system creates a unique "Path" for every section based on its parents (e.g., `Device Overview -> Intended Use`). If a duplicate name is found under the same parent, it adds a number to it (e.g., `Error Codes [2]`) so it doesn't get confused.

## Document Versioning
The system uses the section's "Path" and a hash of its text to figure out if it changed between Version 1 and Version 2. 
When Version 2 is uploaded:
- If a section has the exact same Path and the exact same text, **it does not copy the section into the database again**. It just marks the existing one as belonging to both Version 1 and Version 2.
- If the text has changed, it creates a new entry for Version 2.

## Browse API
The API lets you do four things:
- `/nodes/top`: View only the main, top-level sections of the document.
- `/nodes/{id}`: View a specific section and a list of its sub-sections.
- `/search`: Search for specific words anywhere in the document.
- `/nodes/{id}/diff`: See exactly which lines of text were added or removed between versions.

## Decision Log

**1. What's the one part of this system most likely to silently give wrong results without erroring? How would you catch it?**
The system relies heavily on the section names to track them across versions. If a user completely renames a section (like changing "Device Overview" to "System Overview"), the system will lose track of it. It will think the old section was deleted and a brand-new one was added. To fix this, I would need to write a more advanced algorithm that looks at how similar the actual text is, rather than just looking at the title.

**2. Where did you choose simplicity over correctness because of time, and what would break first if this went to production as-is?**
For the feature that shows text differences (diffs), the system currently only compares the very first version of a section against the very latest version. If there were 10 versions of a document, it doesn't show you the step-by-step changes. In a real production environment, users would be confused as to why they can't see the exact changes between Version 3 and Version 4.

**3. Name one input (to your parser, your versioning matcher, or your LLM call) that you did not handle, and what your system does when it sees it.**
The parser does not know how to handle Markdown tables or hidden HTML comments (like developer "TODO" notes). It just blindly reads them as normal text. When this normal text is sent to the AI to generate test cases, the AI might get confused by the hidden comments or messy table formatting.
