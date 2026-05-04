"""
ALEX — Productivity Actions (Phase 2)
LLM-powered document generation, text summarization, and email composition.
Uses the Groq client's content generation endpoint.
"""

import os
from datetime import datetime

import config
from utils.helpers import get_logger

logger = get_logger()

# The LLM client is injected at module level by the router
_llm_client = None


def set_llm_client(client):
    """Called by the router to inject the Groq client for content generation."""
    global _llm_client
    _llm_client = client


def write_document(topic: str, length: str = "short", tone: str = "neutral") -> str:
    """
    Generate a document on the given topic using the LLM.
    Saves the output to ~/Documents/ALEX/{topic}.txt.
    """
    if _llm_client is None:
        return "Error: LLM client not available for content generation."

    # Map length to approximate word counts
    length_map = {
        "short": "200-300 words",
        "medium": "500-700 words",
        "long": "1000-1500 words",
    }
    word_count = length_map.get(length.lower(), "300-500 words")

    prompt = (
        f"Write a {tone} document about '{topic}'.\n"
        f"Length: approximately {word_count}.\n"
        f"Use clear headings and well-structured paragraphs.\n"
        f"Do not include any meta-commentary about the document itself."
    )

    logger.info(f"Generating document: topic={topic}, length={length}, tone={tone}")
    content = _llm_client.generate_content(prompt)

    if content.startswith("Error:"):
        return content

    # Save to file
    os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic)
    safe_name = safe_name[:50].strip()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{timestamp}.txt"
    filepath = os.path.join(config.DOCUMENTS_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Document saved: {filepath}")
        return f"Document written and saved to {filepath}."
    except OSError as e:
        logger.error(f"Failed to save document: {e}")
        return f"Document generated but could not be saved: {e}"


def summarize_text(text: str) -> str:
    """
    Summarize the given text using the LLM.
    Returns the summary directly.
    """
    if _llm_client is None:
        return "Error: LLM client not available for summarization."

    prompt = (
        f"Summarize the following text concisely. "
        f"Keep the key points and important details. "
        f"Output only the summary.\n\n"
        f"TEXT:\n{text}"
    )

    logger.info(f"Summarizing text: {len(text)} characters")
    summary = _llm_client.generate_content(prompt)
    return f"Summary:\n{summary}"


def generate_email(to: str, subject: str, body: str = "") -> str:
    """
    Generate a professional email draft using the LLM.
    Copies the result to the clipboard.
    """
    if _llm_client is None:
        return "Error: LLM client not available for email generation."

    body_instruction = (
        f"Use this context for the body: {body}" if body
        else "Write appropriate content based on the subject."
    )

    prompt = (
        f"Write a professional email.\n"
        f"To: {to}\n"
        f"Subject: {subject}\n"
        f"{body_instruction}\n"
        f"Include a proper greeting and sign-off. "
        f"Output only the email text, ready to send."
    )

    logger.info(f"Generating email: to={to}, subject={subject}")
    email_text = _llm_client.generate_content(prompt)

    # Try to copy to clipboard
    try:
        import subprocess
        process = subprocess.Popen(
            ["clip"], stdin=subprocess.PIPE, shell=True
        )
        process.communicate(email_text.encode("utf-8"))
        clipboard_msg = " Email copied to clipboard."
    except Exception:
        clipboard_msg = ""

    return f"Email draft generated{clipboard_msg}\n\n{email_text}"
