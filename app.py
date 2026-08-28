"""CSC484 Module 2 - State of the Union Text Analyzer.

Single-file Tkinter application that demonstrates file processing, error handling,
text analysis, and a small bounded extension beyond the assignment requirements.
"""

from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import ssl
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_TITLE = "State of the Union Text Analyzer"
OFFICIAL_2014_URL = "https://www.govinfo.gov/content/pkg/DCPD-201400050/html/DCPD-201400050.htm"
OFFICIAL_2014_FILE = "2014_State_of_the_Union.txt"

WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
BRACKETED_STAGE_DIRECTION_RE = re.compile(r"\[(?:Applause|Laughter)[^\]]*\]", re.IGNORECASE)

# These words are still included in the required full frequency distribution.
# They are separated here only for the optional meaningful-repetition view.
CONNECTIVE_WORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "between",
    "both", "but", "by", "can", "could", "did", "do", "does", "doing", "down",
    "each", "even", "every", "few", "for", "from", "had", "has", "have", "he",
    "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "just", "me", "more", "most", "my", "no", "not", "now", "of",
    "on", "once", "only", "or", "other", "our", "out", "over", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "up", "us", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "why", "will", "with", "would", "you", "your",
}

# A deliberately small transparent action-word vocabulary. This is a heuristic,
# not a full part-of-speech model.
ACTION_BASE_WORDS = {
    "act", "add", "ask", "build", "change", "close", "connect", "create", "cut",
    "defend", "deliver", "develop", "expand", "fight", "fix", "give", "grow",
    "help", "hire", "improve", "increase", "invest", "lead", "lower", "make",
    "move", "open", "prepare", "prevent", "protect", "raise", "rebuild", "reduce",
    "reform", "restore", "save", "serve", "strengthen", "support", "train", "work",
}

IRREGULAR_ACTIONS = {
    "built": "build",
    "brought": "bring",
    "came": "come",
    "did": "do",
    "done": "do",
    "gave": "give",
    "gone": "go",
    "grew": "grow",
    "made": "make",
    "ran": "run",
    "took": "take",
    "went": "go",
}

SENTENCE_START_EXCLUSIONS = {
    "A", "An", "And", "As", "At", "Because", "But", "By", "For", "From", "He",
    "Her", "Here", "His", "I", "If", "In", "It", "Its", "Look", "My", "No",
    "Now", "On", "Our", "She", "So", "That", "The", "Their", "There", "These",
    "They", "This", "Those", "To", "Tonight", "We", "What", "When", "Where",
    "Which", "Who", "Why", "With", "Yes", "You", "Your", "Folks",
}

ANALYSIS_LIMITATION = (
    "Analysis note: meaningful-repetition categories use transparent, rule-based text processing. "
    "They highlight recurring actions and subjects but are not definitive linguistic or contextual "
    "interpretation. A deeper analysis would require a more advanced NLP or language-model layer."
)


class TextAnalysisError(Exception):
    """Raised when a selected file cannot be safely analyzed."""


class _GovInfoTextParser(HTMLParser):
    """Small standard-library HTML-to-text helper for the official GovInfo page."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def load_text_file(file_path: str | Path) -> str:
    """Read a local .txt file with a small safe encoding fallback."""
    path = Path(file_path)

    if not path.exists():
        raise TextAnalysisError("The selected file does not exist.")
    if not path.is_file():
        raise TextAnalysisError("The selected path is not a file.")
    if path.suffix.lower() != ".txt":
        raise TextAnalysisError("Please select a .txt file for this assignment.")

    raw = path.read_bytes()
    if not raw:
        raise TextAnalysisError("The selected text file is empty.")

    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise TextAnalysisError("The file could not be decoded as common Windows or UTF-8 text.")

    if not text.strip():
        raise TextAnalysisError("The selected file contains no readable text.")

    return text


def clean_official_2014_transcript(page_text: str) -> str:
    """Extract the actual 2014 address from the official GovInfo page text.

    Publication metadata after the speech is excluded. Obvious audience/stage markers
    are removed so the statistics represent the President's address rather than the
    printed document surrounding it.
    """
    start_marker = "Mr. Speaker, Mr. Vice President, Members of Congress, my fellow Americans:"
    end_marker = "God bless you, and God bless the United States of America."

    start = page_text.find(start_marker)
    end = page_text.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise TextAnalysisError(
            "The official GovInfo page was downloaded, but the speech boundaries could not be identified."
        )

    speech = page_text[start : end + len(end_marker)]
    speech = BRACKETED_STAGE_DIRECTION_RE.sub("", speech)

    # Remove the audience chant and speaker labels that are transcript metadata,
    # not words spoken by President Obama.
    speech = re.sub(r"\bAudience members\.\s*U\.S\.A\.!\s*U\.S\.A\.!\s*U\.S\.A\.!", "", speech)
    speech = re.sub(r"\bThe President\.\s*", "", speech)

    # Normalize whitespace while retaining paragraph breaks where the source provides them.
    cleaned_lines: list[str] = []
    for line in speech.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    speech = "\n\n".join(cleaned_lines).strip()
    if len(WORD_RE.findall(speech)) < 1000:
        raise TextAnalysisError(
            "The downloaded text did not contain enough words to be the complete 2014 address."
        )
    return speech


def download_official_2014_speech(destination: str | Path) -> Path:
    """Download, clean, and save the official full 2014 State of the Union speech."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    request = Request(
        OFFICIAL_2014_URL,
        headers={"User-Agent": "CSC484-State-of-the-Union-Analyzer/1.0"},
    )
    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=20, context=context) as response:
            raw = response.read()
    except HTTPError as exc:
        raise TextAnalysisError(f"GovInfo returned HTTP error {exc.code}.") from exc
    except URLError as exc:
        raise TextAnalysisError(
            "The official 2014 speech could not be downloaded. Check the internet connection, "
            "or download the GovInfo text manually and use Browse."
        ) from exc
    except OSError as exc:
        raise TextAnalysisError(f"The official speech could not be downloaded: {exc}") from exc

    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            html_text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise TextAnalysisError("The GovInfo page could not be decoded as readable text.")

    parser = _GovInfoTextParser()
    parser.feed(html_text)
    speech = clean_official_2014_transcript(parser.text())
    destination.write_text(speech, encoding="utf-8")
    return destination


def tokenize_words(text: str) -> list[str]:
    """Return normalized lowercase words while retaining internal apostrophes."""
    return [match.group(0).lower().replace("’", "'") for match in WORD_RE.finditer(text)]


def count_sentences(text: str) -> int:
    """Estimate sentence count using terminal punctuation."""
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return 0
    candidates = SENTENCE_SPLIT_RE.split(normalized)
    return len([candidate for candidate in candidates if WORD_RE.search(candidate)])


def alphabetic_length(word: str) -> int:
    return sum(character.isalpha() for character in word)


def normalize_action_word(word: str) -> str | None:
    """Return an action base when a word matches the transparent heuristic."""
    if word in IRREGULAR_ACTIONS:
        return IRREGULAR_ACTIONS[word]
    if word in ACTION_BASE_WORDS:
        return word

    candidates: list[str] = []
    if word.endswith("ies") and len(word) > 4:
        candidates.append(word[:-3] + "y")
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        candidates.extend((stem, stem + "e"))
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        candidates.extend((stem, stem + "e"))
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            candidates.append(stem[:-1])
    if word.endswith("es") and len(word) > 4:
        candidates.extend((word[:-2], word[:-1]))
    elif word.endswith("s") and len(word) > 3:
        candidates.append(word[:-1])

    for candidate in candidates:
        if candidate in ACTION_BASE_WORDS:
            return candidate
    return None


def extract_named_terms(text: str) -> Counter[str]:
    """Heuristically identify repeated capitalized names/organizations/places."""
    named_counter: Counter[str] = Counter()
    pattern = re.compile(
        r"\b(?:[A-Z][a-z]+|[A-Z]{2,})"
        r"(?:\s+(?:(?:of|the|and|for|in|on)\s+)?(?:[A-Z][a-z]+|[A-Z]{2,})){0,4}\b"
    )

    for match in pattern.finditer(text):
        term = re.sub(r"\s+", " ", match.group(0)).strip()
        first = term.split()[0]
        if first in SENTENCE_START_EXCLUSIONS or len(term) < 3:
            continue
        named_counter[term] += 1
    return named_counter


def analyze_text(text: str, file_name: str) -> dict:
    """Calculate all required metrics plus the two bounded enhanced analyses."""
    words = tokenize_words(text)
    if not words:
        raise TextAnalysisError("No words were found in the selected file.")

    frequency = Counter(words)
    word_count = len(words)
    character_count = len(text)
    sentence_count = count_sentences(text)
    unique_word_count = len(frequency)

    total_letters = sum(alphabetic_length(word) for word in words)
    average_word_length = total_letters / word_count
    average_sentence_length = word_count / sentence_count if sentence_count else 0.0
    lexical_diversity = (unique_word_count / word_count) * 100

    frequency_rows = [
        (word, count, (count / word_count) * 100)
        for word, count in sorted(frequency.items(), key=lambda item: (-item[1], item[0]))
    ]

    longest_words = [
        (word, alphabetic_length(word), frequency[word])
        for word in sorted(frequency, key=lambda item: (-alphabetic_length(item), item))[:10]
    ]

    connective_rows = [
        (word, frequency[word])
        for word in sorted(
            (word for word in frequency if word in CONNECTIVE_WORDS),
            key=lambda item: (-frequency[item], item),
        )[:15]
    ]

    action_counter: Counter[str] = Counter()
    classified_action_words: set[str] = set()
    for word, count in frequency.items():
        base = normalize_action_word(word)
        if base:
            action_counter[base] += count
            classified_action_words.add(word)
    action_rows = sorted(action_counter.items(), key=lambda item: (-item[1], item[0]))[:15]

    named_counter = extract_named_terms(text)
    named_rows = [
        (term, "Named term", count)
        for term, count in sorted(named_counter.items(), key=lambda item: (-item[1], item[0].lower()))
        if count >= 2
    ]

    subject_candidates = [
        (word, count)
        for word, count in frequency.items()
        if word not in CONNECTIVE_WORDS
        and word not in classified_action_words
        and len(word) >= 4
        and count >= 2
    ]
    subject_candidates.sort(key=lambda item: (-item[1], item[0]))
    content_rows = [(word, "Repeated subject", count) for word, count in subject_candidates[:20]]

    seen: set[str] = set()
    subject_rows: list[tuple[str, str, int]] = []
    for row in named_rows + content_rows:
        key = row[0].lower()
        if key in seen:
            continue
        seen.add(key)
        subject_rows.append(row)
        if len(subject_rows) >= 20:
            break

    return {
        "file_name": file_name,
        "character_count": character_count,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "average_word_length": average_word_length,
        "average_sentence_length": average_sentence_length,
        "unique_word_count": unique_word_count,
        "lexical_diversity": lexical_diversity,
        "frequency_rows": frequency_rows,
        "longest_words": longest_words,
        "connective_rows": connective_rows,
        "action_rows": action_rows,
        "subject_rows": subject_rows,
    }


def analyze_file(file_path: str | Path) -> dict:
    path = Path(file_path)
    return analyze_text(load_text_file(path), path.name)


class SOTUAnalyzerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x780")
        self.minsize(980, 680)

        self.selected_file = tk.StringVar()
        self.status_text = tk.StringVar(value="Choose a State of the Union .txt file or load the official 2014 speech.")
        self.frequency_search = tk.StringVar()
        self.result: dict | None = None

        self.configure_styles()
        self.build_layout()

    def configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("TkDefaultFont", 10))
        style.configure("CardValue.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("CardLabel.TLabel", font=("TkDefaultFont", 9))
        style.configure("Section.TLabel", font=("TkDefaultFont", 12, "bold"))
        style.configure("Treeview", rowheight=26)

    def build_layout(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="CSC484 Module 2 | File processing, error handling, frequency analysis, and bounded text insights",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        controls = ttk.LabelFrame(outer, text="Speech File", padding=10)
        controls.pack(fill="x")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Selected file:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(controls, textvariable=self.selected_file, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Button(controls, text="Browse...", command=self.browse_file).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(controls, text="Analyze Speech", command=self.analyze_selected).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(controls, text="Reset", command=self.reset).grid(row=0, column=4)

        official = ttk.Frame(controls)
        official.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        ttk.Button(official, text="Load Official 2014 State of the Union", command=self.load_official_2014).pack(side="left")
        ttk.Label(
            official,
            text="Downloads the complete Jan. 28, 2014 GovInfo transcript, saves it locally, then analyzes the speech.",
        ).pack(side="left", padx=(10, 0))

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True, pady=(12, 10))

        self.summary_tab = ttk.Frame(self.notebook, padding=12)
        self.frequency_tab = ttk.Frame(self.notebook, padding=12)
        self.longest_tab = ttk.Frame(self.notebook, padding=12)
        self.insights_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.summary_tab, text="Summary")
        self.notebook.add(self.frequency_tab, text="Word Frequency")
        self.notebook.add(self.longest_tab, text="Longest Words")
        self.notebook.add(self.insights_tab, text="Meaningful Repetition")

        self.build_summary_tab()
        self.build_frequency_tab()
        self.build_longest_tab()
        self.build_insights_tab()

        ttk.Separator(outer).pack(fill="x")
        ttk.Label(outer, textvariable=self.status_text).pack(anchor="w", pady=(8, 0))

    def build_summary_tab(self) -> None:
        self.summary_tab.columnconfigure((0, 1, 2), weight=1)

        required = ttk.LabelFrame(self.summary_tab, text="Required Assignment Metrics", padding=12)
        required.grid(row=0, column=0, columnspan=3, sticky="nsew")
        for column in range(3):
            required.columnconfigure(column, weight=1)

        self.metric_vars = {
            "words": tk.StringVar(value="—"),
            "characters": tk.StringVar(value="—"),
            "avg_word": tk.StringVar(value="—"),
            "sentences": tk.StringVar(value="—"),
            "avg_sentence": tk.StringVar(value="—"),
            "unique": tk.StringVar(value="—"),
            "diversity": tk.StringVar(value="—"),
            "file": tk.StringVar(value="—"),
        }

        cards = [
            ("Word Count", "words"),
            ("Character Count\n(including spaces)", "characters"),
            ("Average Word Length", "avg_word"),
            ("Sentence Count", "sentences"),
            ("Average Sentence Length\n(words per sentence)", "avg_sentence"),
        ]
        for index, (label, key) in enumerate(cards):
            row, col = divmod(index, 3)
            card = ttk.Frame(required, padding=12, relief="ridge")
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            ttk.Label(card, textvariable=self.metric_vars[key], style="CardValue.TLabel").pack(anchor="center")
            ttk.Label(card, text=label, style="CardLabel.TLabel", justify="center").pack(anchor="center", pady=(4, 0))

        extra = ttk.LabelFrame(self.summary_tab, text="Additional Analysis", padding=12)
        extra.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        extra.columnconfigure((0, 1, 2), weight=1)
        self.small_metric(extra, 0, "Source File", self.metric_vars["file"])
        self.small_metric(extra, 1, "Unique Words", self.metric_vars["unique"])
        self.small_metric(extra, 2, "Lexical Diversity", self.metric_vars["diversity"])

        definitions = ttk.LabelFrame(self.summary_tab, text="Calculation Definitions", padding=12)
        definitions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(
            definitions,
            justify="left",
            wraplength=1050,
            text=(
                "Words are alphabetic sequences that may contain an internal apostrophe. Character count uses the original local text file, "
                "including spaces and punctuation. Average word length counts alphabetic characters only. Sentences are estimated from ., ?, and ! punctuation. "
                "Word frequency is case-insensitive. The ten longest words are unique words sorted by length and then alphabetically."
            ),
        ).pack(anchor="w")

    def small_metric(self, parent: ttk.Widget, column: int, label: str, variable: tk.StringVar) -> None:
        frame = ttk.Frame(parent, padding=8)
        frame.grid(row=0, column=column, sticky="nsew")
        ttk.Label(frame, text=label, style="CardLabel.TLabel").pack(anchor="center")
        ttk.Label(frame, textvariable=variable, font=("TkDefaultFont", 12, "bold"), wraplength=300).pack(
            anchor="center", pady=(3, 0)
        )

    def build_frequency_tab(self) -> None:
        header = ttk.Frame(self.frequency_tab)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Complete Word Frequency Distribution", style="Section.TLabel").pack(side="left")

        search_frame = ttk.Frame(header)
        search_frame.pack(side="right")
        ttk.Label(search_frame, text="Filter:").pack(side="left", padx=(0, 5))
        ttk.Entry(search_frame, textvariable=self.frequency_search, width=24).pack(side="left")
        self.frequency_search.trace_add("write", lambda *_: self.refresh_frequency_table())

        self.frequency_tree = self.make_tree(
            self.frequency_tab,
            columns=("word", "count", "percent"),
            headings=("Word", "Count", "Percentage of All Words"),
            widths=(350, 160, 220),
        )

    def build_longest_tab(self) -> None:
        ttk.Label(self.longest_tab, text="Top Ten Longest Unique Words", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(self.longest_tab, text="Ties are sorted alphabetically so the result is reproducible.").pack(anchor="w", pady=(0, 8))
        self.longest_tree = self.make_tree(
            self.longest_tab,
            columns=("word", "length", "count"),
            headings=("Word", "Length", "Occurrences"),
            widths=(500, 150, 150),
        )

    def build_insights_tab(self) -> None:
        ttk.Label(self.insights_tab, text="Meaningful Repetition Analysis", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.insights_tab, text=ANALYSIS_LIMITATION, justify="left", wraplength=1080).pack(
            anchor="w", pady=(5, 10)
        )

        panels = ttk.Panedwindow(self.insights_tab, orient="horizontal")
        panels.pack(fill="both", expand=True)

        connective_frame = ttk.LabelFrame(panels, text="Connective / Filler Words", padding=8)
        action_frame = ttk.LabelFrame(panels, text="Likely Action Words", padding=8)
        subject_frame = ttk.LabelFrame(panels, text="Recurring Named / Subject Terms", padding=8)
        panels.add(connective_frame, weight=1)
        panels.add(action_frame, weight=1)
        panels.add(subject_frame, weight=2)

        self.connective_tree = self.make_tree(
            connective_frame, ("word", "count"), ("Word", "Count"), (170, 90)
        )
        self.action_tree = self.make_tree(
            action_frame, ("word", "count"), ("Action", "Count"), (170, 90)
        )
        self.subject_tree = self.make_tree(
            subject_frame,
            ("term", "type", "count"),
            ("Term", "Heuristic Type", "Count"),
            (260, 150, 80),
        )

    def make_tree(self, parent: ttk.Widget, columns, headings, widths) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for column, heading, width in zip(columns, headings, widths):
            tree.heading(column, text=heading)
            anchor = "e" if column in {"count", "percent", "length"} else "w"
            tree.column(column, width=width, minwidth=70, anchor=anchor)
        return tree

    def browse_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select a State of the Union text file",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        if file_path:
            self.selected_file.set(file_path)
            self.status_text.set(f"Ready to analyze {Path(file_path).name}.")

    def load_official_2014(self) -> None:
        destination = Path(__file__).resolve().parent / "sample_data" / OFFICIAL_2014_FILE
        try:
            if not destination.exists():
                self.status_text.set("Downloading the complete official 2014 State of the Union from GovInfo...")
                self.update_idletasks()
                download_official_2014_speech(destination)
            self.selected_file.set(str(destination))
            self.status_text.set("Official 2014 speech is ready. Running full-speech analysis...")
            self.update_idletasks()
            self.result = analyze_file(destination)
        except TextAnalysisError as exc:
            self.status_text.set("The official 2014 speech could not be prepared.")
            messagebox.showerror("2014 Speech Download", str(exc))
            return

        self.display_result()
        self.status_text.set(f"Full 2014 State of the Union analysis completed successfully ({self.result['word_count']:,} words).")
        self.notebook.select(self.summary_tab)

    def analyze_selected(self) -> None:
        file_path = self.selected_file.get().strip()
        if not file_path:
            messagebox.showwarning("No File Selected", "Choose a .txt speech file before running the analysis.")
            return
        try:
            self.status_text.set("Analyzing speech...")
            self.update_idletasks()
            self.result = analyze_file(file_path)
        except TextAnalysisError as exc:
            self.status_text.set("Analysis stopped because the file could not be processed.")
            messagebox.showerror("Unable to Analyze File", str(exc))
            return
        except OSError as exc:
            self.status_text.set("A file-system error occurred.")
            messagebox.showerror("File Error", f"The file could not be read:\n{exc}")
            return
        except Exception as exc:
            self.status_text.set("An unexpected analysis error occurred.")
            messagebox.showerror("Unexpected Error", f"The analysis could not be completed:\n{exc}")
            return

        self.display_result()
        self.status_text.set(f"Analysis completed successfully for {self.result['file_name']}.")
        self.notebook.select(self.summary_tab)

    def display_result(self) -> None:
        if self.result is None:
            return
        result = self.result
        self.metric_vars["words"].set(f"{result['word_count']:,}")
        self.metric_vars["characters"].set(f"{result['character_count']:,}")
        self.metric_vars["avg_word"].set(f"{result['average_word_length']:.2f}")
        self.metric_vars["sentences"].set(f"{result['sentence_count']:,}")
        self.metric_vars["avg_sentence"].set(f"{result['average_sentence_length']:.2f}")
        self.metric_vars["unique"].set(f"{result['unique_word_count']:,}")
        self.metric_vars["diversity"].set(f"{result['lexical_diversity']:.2f}%")
        self.metric_vars["file"].set(result["file_name"])

        self.refresh_frequency_table()
        self.replace_tree_rows(self.longest_tree, result["longest_words"])
        self.replace_tree_rows(self.connective_tree, result["connective_rows"])
        self.replace_tree_rows(self.action_tree, result["action_rows"])
        self.replace_tree_rows(self.subject_tree, result["subject_rows"])

    def refresh_frequency_table(self) -> None:
        if self.result is None:
            self.replace_tree_rows(self.frequency_tree, [])
            return
        search = self.frequency_search.get().strip().lower()
        rows = self.result["frequency_rows"]
        if search:
            rows = [row for row in rows if search in row[0]]
        display_rows = [(word, f"{count:,}", f"{percent:.3f}%") for word, count, percent in rows]
        self.replace_tree_rows(self.frequency_tree, display_rows)

    @staticmethod
    def replace_tree_rows(tree: ttk.Treeview, rows) -> None:
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)

    def reset(self) -> None:
        self.selected_file.set("")
        self.frequency_search.set("")
        self.result = None
        for variable in self.metric_vars.values():
            variable.set("—")
        for tree in (
            self.frequency_tree,
            self.longest_tree,
            self.connective_tree,
            self.action_tree,
            self.subject_tree,
        ):
            tree.delete(*tree.get_children())
        self.status_text.set("Choose a State of the Union .txt file or load the official 2014 speech.")
        self.notebook.select(self.summary_tab)


def main() -> None:
    app = SOTUAnalyzerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
