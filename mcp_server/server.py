from mcp.server.fastmcp import FastMCP
import os
import fnmatch
from pathlib import Path

# Create an MCP server
mcp = FastMCP("Filesystem & Notes MCP")

NOTES_FILE = Path(__file__).resolve().parent.parent / "notes.txt"


def ensure_file():
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("")


# Safety: restrict access to files only within a specific directory
ALLOWED_ROOT = os.path.expanduser("/Users/hyeonbinchun/Documents")


def _safe_path(path: str)->str:
    """Resolve and validate that path stays inside ALLOWED_ROOT."""
    resolved = os.path.realpath(os.path.expanduser(path))
    if not resolved.startswith(os.path.realpath(ALLOWED_ROOT)):
        raise PermissionError(
            f"Access denied: '{path}' is outside the allowed root '{ALLOWED_ROOT}'"
        )
    return resolved


# ── Sticky Notes tools ────────────────────────────────────────────────────────

@mcp.tool()
def add_note(message: str) -> str:
    """
    Append a new note to the sticky note file.
    Args:
        message(str): The note content to be added.
    return:
        str: Confirmation message indicating the note was saved.
    """
    ensure_file()
    with NOTES_FILE.open("a") as f:
        f.write(message + "\n")
    return "Note saved!"

@mcp.tool()
def read_notes() -> str:
    """
    Read and return all notes from the sticky note file.

    return:
        str: All notes as a single string separated by line breaks.
            If no notes exist, a default message is returned.
    """
    ensure_file()
    with NOTES_FILE.open("r") as f:
        content = f.read().strip()
    return content or "No notes yet."

# ── Filesystem tools ──────────────────────────────────────────────────────────

@mcp.tool()
def list_directory(path: str = "~") -> str:
    """ 
    List the conents of a directory.
       Args:
        path (str): Absolute or ~ path to list. Defaults to home directory.
 
    Returns:
        str: A formatted directory listing showing files and sub-folders.
    """
    safe = _safe_path(path)
    if not os.path.isdir(safe):
        return f"'{path}' is not a directory."
    entries = sorted(os.scandir(safe), key=lambda e: (not e.is_dir(), e.name.lower()))
    lines = [f"📁  {safe}", ""]
    for e in entries:
        if e.is_dir():
            lines.append(f"  📂  {e.name}/")
        else:
            size = e.stat().st_size
            lines.append(f"  📄  {e.name}  ({_human_size(size)})")
    return "\n".join(lines)
 

@mcp.tool()
def read_file(path: str, max_chars: int = 8000) -> str:
    """
    Read a plain-text file (txt, md, py, json, csv, …) and return its contents.
 
    Args:
        path     (str): Absolute or ~ path to the file.
        max_chars(int): Maximum characters to return (default 8 000).
 
    Returns:
        str: The file's text content, truncated if it exceeds max_chars.
    """
    safe = _safe_path(path)
    if not os.path.isfile(safe):
        return f"File not found: '{path}'"
 
    with open(safe, "r", errors="replace") as f:
        content = f.read(max_chars)
 
    truncated = os.path.getsize(safe) > max_chars
    suffix = f"\n\n[… truncated – file is larger than {max_chars} chars]" if truncated else ""
    return content + suffix


@mcp.tool()
def read_pdf(path: str, max_pages: int = 10) -> str:
    """
    Extract text from a PDF file using pdfminer / pypdf.
 
    Args:
        path     (str): Absolute or ~ path to the PDF.
        max_pages(int): Maximum number of pages to extract (default 10).
 
    Returns:
        str: Extracted text from the PDF.
    """
    safe = _safe_path(path)
    if not os.path.isfile(safe):
        return f"File not found: '{path}'"
 
    # Try pypdf first (usually installed), fall back to pdfminer
    try:
        from pypdf import PdfReader
        reader = PdfReader(safe)
        pages = reader.pages[:max_pages]
        text = "\n\n".join(p.extract_text() or "" for p in pages)
        total = len(reader.pages)
        note = f"\n\n[Showing {min(max_pages, total)} of {total} pages]" if total > max_pages else ""
        return (text.strip() or "(No extractable text found – PDF may be scanned/image-based.)") + note
    except ImportError:
        pass
 
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(safe, maxpages=max_pages)
        return text.strip() or "(No extractable text found.)"
    except ImportError:
        return (
            "Neither 'pypdf' nor 'pdfminer.six' is installed. "
            "Run: pip install pypdf  or  pip install pdfminer.six"
        )
    
@mcp.tool()
def read_docx(path: str) -> str:
    """
    Extract text from a Word (.docx) file.
 
    Args:
        path (str): Absolute or ~ path to the .docx file.
 
    Returns:
        str: The full text content of the document.
    """
    safe = _safe_path(path)
    if not os.path.isfile(safe):
        return f"File not found: '{path}'"
 
    try:
        from docx import Document
        doc = Document(safe)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) or "(Document appears to be empty.)"
    except ImportError:
        return "The 'python-docx' package is not installed. Run: pip install python-docx"
 
 
@mcp.tool()
def find_files(name_pattern: str, search_path: str = "~", max_results: int = 20) -> str:
    """
    Search for files whose names match a wildcard pattern (e.g. '*resume*', '*.pdf').
 
    Args:
        name_pattern (str): Shell glob pattern to match filenames.
        search_path  (str): Directory to search in (default: home directory).
        max_results  (int): Maximum number of results to return (default 20).
 
    Returns:
        str: Newline-separated list of matching file paths.
    """
    safe = _safe_path(search_path)
    matches = []
 
    for root, dirs, files in os.walk(safe):
        # Skip hidden directories (e.g. .git, .cache)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if fnmatch.fnmatch(filename.lower(), name_pattern.lower()):
                matches.append(os.path.join(root, filename))
                if len(matches) >= max_results:
                    return "\n".join(matches) + f"\n\n[Stopped at {max_results} results]"
 
    return "\n".join(matches) if matches else f"No files matching '{name_pattern}' found in '{search_path}'."
 
 
@mcp.tool()
def grep_files(search_term: str, search_path: str = "~", file_pattern: str = "*", max_results: int = 20) -> str:
    """
    Search for a text string inside files (like the 'grep' command).
 
    Args:
        search_term  (str): Text to search for (case-insensitive).
        search_path  (str): Directory to search in (default: home directory).
        file_pattern (str): Only search files matching this glob (e.g. '*.txt', '*.md').
        max_results  (int): Maximum number of matching lines to return (default 20).
 
    Returns:
        str: Lines that contain the search term, with their file paths.
    """
    safe = _safe_path(search_path)
    results = []
 
    for root, dirs, files in os.walk(safe):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if not fnmatch.fnmatch(filename.lower(), file_pattern.lower()):
                continue
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if search_term.lower() in line.lower():
                            results.append(f"{filepath}:{lineno}: {line.rstrip()}")
                            if len(results) >= max_results:
                                return "\n".join(results) + f"\n\n[Stopped at {max_results} results]"
            except (PermissionError, IsADirectoryError):
                continue
 
    return "\n".join(results) if results else f"No matches for '{search_term}' found."
 
 
@mcp.tool()
def get_file_info(path: str) -> str:
    """
    Return metadata about a file or directory (size, type, dates).
 
    Args:
        path (str): Absolute or ~ path to the file or directory.
 
    Returns:
        str: Human-readable file metadata.
    """
    safe = _safe_path(path)
    if not os.path.exists(safe):
        return f"Path not found: '{path}'"
 
    stat = os.stat(safe)
    import datetime
    kind = "Directory" if os.path.isdir(safe) else "File"
    modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    created  = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
 
    lines = [
        f"Path      : {safe}",
        f"Type      : {kind}",
        f"Size      : {_human_size(stat.st_size)}",
        f"Modified  : {modified}",
        f"Created   : {created}",
    ]
    if os.path.isfile(safe):
        _, ext = os.path.splitext(safe)
        lines.append(f"Extension : {ext or '(none)'}")
    return "\n".join(lines)
 
@mcp.resource("notes://latest")
def get_latest_note() -> str:
    """
    Get the most recently added note from the sticky note file.

    Return:
        str: The latest note entry. If no notes exist, a default message is returned.
    """
    ensure_file()
    with NOTES_FILE.open("r") as f:
        lines = f.readlines()
    return lines[-1].strip() if lines else "No notes yet."


@mcp.prompt()
def note_summary_prompt() -> str:
    """
    Generate a prompt asking the AI to summarize all current notes.

    Returns:
        str: A prompt string that includes all notes and ask for a summary.
            if no notes exist, a message will be shown indicating that.
    """
    ensure_file()
    with NOTES_FILE.open("r") as f:
        content = f.read().strip()
    if not content:
        return "There are no notes yet."
    return f"Summarize the current notes: {content}"


 
 
# ── Helpers ───────────────────────────────────────────────────────────────────
 
def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"