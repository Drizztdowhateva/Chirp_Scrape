**Healthy Input/Output**

**Purpose**: Concise rules for providing clean, safe inputs and expected outputs when using the `rolling_code` tools in this repository.

**Accepted Input:**
- **Clean text:** UTF-8 strings without embedded secrets, passwords, or private personal data.
- **Hashtags:** Comma-separated tags or a single tag. Tags are normalized (leading `#` added, trimmed, uppercased).
- **Key file:** Path to a local key file used only by the program (keep this file private).
- **Options:** Numeric parameters (`--interval`, `--digits`, `--rounds`, `--throttle-min`, `--throttle-max`) as non-negative integers.

**Disallowed Input:**
- Private keys, API tokens, or passwords pasted directly into inputs or committed to the repo.
- Unredacted personal data or protected health information (PHI).
- Any content that promotes illegal activities, hate, or harassment.

**Sanitization Rules Applied by Tools:**
- Trimming whitespace and removing empty tokens.
- Adding a leading `#` if missing and converting tags to uppercase.
- Enforcing tag length limits and rejecting invalid tags.

**Output Format (clean & machine-friendly):**
- Each tag produces a single line: `#TAG: 123456`
- Example:

```
#TEST: 533627
#AI: 237959
```

If you need machine-readable output, pipe or redirect the program output and parse lines of the form `^#([A-Z0-9_]+):\s*(\d+)$`.

**Privacy & Safety Notes:**
- Keep `key.secret` and other keys out of version control. Do not upload secret key files to public repositories.
- Only process images or documents that you have the right to share and that contain no sensitive data.

**Quick Example:**

```
./rolling_code -k key.secret --hashtags test,dev --digits 6 --throttle-min 0 --throttle-max 0
```

File: README.md
