---
name: heo-voice
description: Draft, rewrite or review a highearthorbit.com post, talk write-up or any prose published as Andrew Turner, so it reads in his narrative voice and not like a generated essay. Use for any writing task in this repository or for Notion drafts headed to the blog.
---

# Andrew's voice for highearthorbit.com

Read `docs/voice/style-guide.md` in full before writing. It is measured from his own 141 long posts and his NYGeoCon 2025 keynote, with real examples. This file is the procedure.

## Before writing

1. Collect the facts: Andrew's notes, the Notion page, a talk transcript, linked posts. List the concrete scenes they contain (dates, places, people, what he did or saw). Search `content/_posts/` for his earlier posts on the topic, to link to and to hear how he wrote about it then.
2. Choose one shape from the guide: the field report, the working-through, the long arc, or the personal story that becomes a system.
3. If no real scene exists for the opening, don't invent one. Write `[TK: …]` naming exactly what's needed ("the meeting where this came up: when, who, what was said") and tell Andrew. A post with a `[TK: …]` left in it does not sync from Notion.

## Writing

- Open in a time and place with Andrew in it, or with an old, surprising fact. No thesis line, no "This post…", no one-line set-up paragraph.
- Tell it in order. Paragraphs of 2–6 sentences, sentences around 20 words with natural variation, connectives like "So", "However", "Of course", "Granted", "Now".
- Name people, places, products, versions and numbers that are in the facts. Add one aside in parentheses and at most one dry line, if they fit.
- Praise and criticism go together in the same passage ("a great step, but…"), not in a pros-and-cons section.
- Bullets only for links, specs or step-by-step instructions. Two or three short headings at most; none under 800 words.
- End on the next step, an invitation to the reader, a wry line, or one earned reframe. Never a "Closing thought" heading, a slogan, or "X isn't the scarce resource. Y is."

## Never

- "It's not X. It's Y." / "Not X. Y." reversals, or a one-word paragraph after a claim.
- "Key takeaways", "In conclusion", "Here's the thing", "That's it.", "This post is my attempt", "Let that sink in".
- Invented anecdotes, quotes, numbers, names or feelings. Use `[TK: …]`.
- Corporate voice or press-release tone. Andrew does say "leverage" and "furthermore" sometimes; the problem is the rhythm, not single words.

## Check

Run `python -m scripts.heo.voice_check <file>` on the draft (Markdown, HTML or text). Fix every FAIL. The thresholds are set so his own posts pass. Then read the draft aloud in your head as a talk: if it sounds like a slide deck, rewrite it as the story.

When reviewing a draft rather than writing one, report what the checker found, quote the two or three sentences that sound least like him, and show a rewrite of the opening paragraph.
