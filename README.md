# CSC484 Module 2 - State of the Union Text Analyzer

## Selected speech

President Barack H. Obama, **Address Before a Joint Session of the Congress on the State of the Union**, January 28, 2014. Official GovInfo document: **DCPD-201400050**.

The application includes a button that retrieves the complete official GovInfo transcript, cleans publication-only material, saves the speech as a local `.txt` file, and analyzes that local file. This preserves the assignment's file-processing focus while giving the project a reproducible official source.

## Assignment requirements covered

The program displays:

- Word count
- Character count
- Average word length
- Average sentence length
- Complete word-frequency distribution
- Top ten longest unique words

## Bounded extensions

The program also provides:

1. **Unique word count and lexical diversity**
2. **Meaningful repetition analysis**, which separates common connective/filler words from likely action words and recurring named/subject terms

The additional repetition analysis is explicitly labeled as rule-based and non-definitive. It is not an LLM or deep semantic analysis system.

## Program structure

The assignment solution is intentionally contained in a single Python source file:

- `app.py` - GUI, file handling, error handling, calculations, and optional analysis
- `RUN_ANALYZER.bat` - Windows convenience launcher only
- `pseudocode.txt` - assignment pseudocode
- `sample_data/` - location where the official 2014 speech is saved after retrieval
- `screenshots/` - location for submission screenshots

## Running the program

On Windows, extract the folder and double-click `RUN_ANALYZER.bat`.

For the selected project speech, click **Load Official 2014 State of the Union**. The program downloads the official text once and saves the cleaned full speech locally. Later runs reuse the saved local `.txt` file.

You may also use **Browse** to select another State of the Union `.txt` file.

## Calculation definitions

- **Word:** alphabetic sequence that may contain an internal apostrophe
- **Character count:** every character in the local text file, including spaces and punctuation
- **Average word length:** total alphabetic characters divided by total word count
- **Sentence count:** rule-based estimate using `.`, `?`, and `!` sentence-ending punctuation
- **Average sentence length:** total word count divided by sentence count
- **Frequency:** normalized case-insensitive word count and percentage of total words
- **Longest words:** unique normalized words ordered by letter count, with alphabetical tie-breaking

## Error handling

The application checks for missing files, incorrect file types, empty files, unreadable encodings, network/download failures, and unexpected processing errors. User-facing errors are displayed through the GUI instead of allowing the application to fail silently.
