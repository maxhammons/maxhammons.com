# Brief: alt text + copy cleanup for maxhammons.com pages

You are auditing pages of Max Hammons' design portfolio (maxhammons.com) for two things: (1) descriptive alt text for every image, and (2) light copy cleanup of the page text. Work only from files on disk. Do not edit any HTML. Your only output is one JSON file per page.

For each page slug you were given:

PAGE MANIFEST (read it first): /Users/maxhammons/Documents/Professional/Marketing/Website/content/manifest/<slug>.json
VOICE REFERENCE (read both once; they are Max's resumes and show his voice, facts, and how he names things):
- /Users/maxhammons/Documents/Professional/Marketing/Website/content/voice/resume-designer.txt
- /Users/maxhammons/Documents/Professional/Marketing/Website/content/voice/resume-art-director.txt

The manifest has:
- "texts": every text block on the page in order. "html" is the verbatim inner HTML; "plain" is the same with tags stripped. "kind" says what it is (title, description, text_module, cover_title, footer, masthead, masthead_button, button).
- "images": every image in order. "file" is a local 600px copy you MUST open with the Read tool and actually look at. "preceding_text" is the nearest text above it, for context. "cover_link" is set when the image is a project cover on a gallery page (home or sandbox); then the alt text should start with the project name from the matching cover_title and describe the cover art, e.g. "TCWGlobal Digital Rebrand cover: laptop showing the redesigned portal homepage".

TASK 1, alt text. For every image: open the file with Read, look at it, and write alt text.
- 8 to 20 words. Describe what is literally shown and, when obvious, what it is for (e.g. "Ambition Angels brand guidelines page showing the logo, color palette, and type specimens").
- No "image of", "picture of", "screenshot of". Start with the subject.
- Name the project or client when it helps. Do not invent details you cannot see. If an image is decorative (a plain color block, a divider), write a short literal description anyway.
- Plain sentence case, no trailing period needed.

TASK 2, copy cleanup. Read every text block. Fix only obvious errors: typos, misspellings, missing or doubled words, stray double spaces, broken punctuation, inconsistent capitalization of the same product or brand name within the page, and clear grammar mistakes. Do NOT rewrite for style, do not shorten, do not change voice, do not change numbers or claims, do not add content. Max writes in first person ("I defined…") and that stays. If you are unsure whether something is an error or a stylistic choice, leave it and add a note in "questions".
- Each edit is an exact find/replace on the "html" string of one text block. "find" must be a verbatim substring copied from that block's "html" value (a short phrase is fine, not the whole block). "replace" is the corrected substring. Keep any HTML tags inside the substring unchanged.
- Give a one-line "reason" per edit.

OUTPUT. Write exactly this JSON to /Users/maxhammons/Documents/Professional/Marketing/Website/content/pages/<slug>.json with the Write tool:
{
  "slug": "<slug>",
  "alt": { "<image id from manifest>": "<alt text>", ... },
  "copy": [ { "kind": "<kind>", "find": "<verbatim substring of html>", "replace": "<corrected>", "reason": "<why>" }, ... ],
  "questions": [ "<anything you were unsure about, or an error you saw but did not fix, one string each>" ]
}
Every image id in the manifest must appear in "alt". "copy" and "questions" may be empty arrays. Valid JSON only, no comments. A page with zero images still gets a file (empty "alt").

When all your pages are done, reply with one line per page: slug, image count, edit count, question count.
