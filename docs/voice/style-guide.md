# Writing in Andrew's voice

This guide is for anyone drafting or editing posts for highearthorbit.com as Andrew Turner, including Claude, through `.claude/skills/heo-voice/`. It describes how Andrew actually writes, measured from his own work:

- **141 hand-written posts of 400+ words**, 2004–2024, in `content/_posts/` (about 96,000 words).
- **The NYGeoCon 2025 keynote transcript** (Notion, *05-nygeocon-2025-keynote-transcript*), his spoken voice.
- His two earlier style prompts in Notion (*Andrew Writing style*, *Writing Style*). They describe the voice from the outside; this guide adds what the samples show.

`scripts/heo/voice_check.py` measures a draft against the same numbers. It passes 134 of those 142 posts and fails the generated drafts in Notion on seven counts.

## What goes wrong in generated drafts

Generated drafts read alike because they share a rhythm: **statement, inflection, resolve.**

> I'm increasingly convinced the most interesting form factor for AI isn't another screen.
>
> It's the opposite: a computer you don't touch.
>
> …
>
> A pendant is not a phone replacement. It's not a smart speaker. It's not a wearable version of a chatbot.
>
> …
>
> ## Closing thought
>
> …we're entering an era where the scarce resource isn't information.
>
> It's continuity.

The pattern is a claim, then a one-line reversal ("It's not X. It's Y."), a stack of headings, the argument in bullets, and a slogan at the end. Two different drafts ("AI Pendants" and "Stop Renaming the Thing") end on the same line: *the scarce resource isn't X. It's Y.*

Andrew doesn't write this way. In his posts:

| | Andrew's posts | Generated drafts |
| --- | --- | --- |
| Sentence length (mean per post) | about 20 words, mixing short and 40+ | about 11 |
| Sentences under 6 words | about 4% | about 25% |
| Paragraphs that are one short line | about 12% | about 80% |
| Names (people, places, products) per 1,000 words | about 29 | about 17 |
| "It's not X. It's Y." | 0 in 127 of 142 posts; never twice | three or more per post |
| Argument in bullets | almost never; bullets list links, specs or steps | most sections |
| Ending | the next step, an invitation, a wry line, or one reframe | "Closing thought" plus a slogan |

He tells what happened, in order, from where he was standing.

## How his posts move

Most of his posts use one of four shapes. Pick one before writing.

**1. The field report: "I was there."** It opens on a dated, situated event, with Andrew in it. It moves through what happened and who said what, and ends on what he'll do next or what he wants to see.

> Last week I immersed myself deep in the culture and community of map design. … It was my first time with little awareness or expectation of the community, one that throughout the week I both enjoyed but also some consternation. (*International Cartographic Association*, 2013)

> Baltimore hosted the 2023 Free + Open Source Software for Geospatial (FOSS4G) North America conference, a geeky tech gathering focused on mapping technology and an even more eclectic community. … It was particularly delightful to ride the MARC train from DC Union Station to Camden Yards – city-to-city in under an hour for $9! (*Back to Baltimore for FOSS4G*, 2023)

**2. The working-through: "Here's the problem someone brought me."** A real request or obstacle starts it. He tries something, notes what's wrong with it, tries the next thing, and the reader learns the system along the way. Asides are allowed ("Anyways, RESTful OGC services are a bigger discussion").

> This weekend I was pinged by Todd Huffman regarding a colleague that is deploying to Jos, Nigeria and in search of some good remote imagery to take along. There were several issues he quickly ran into. … So my next suggestion was to look for some other source of data … So I began investigating the underlying datasource. (*Taking remote imagery offline to Nigeria*, 2009)

**3. The long arc: history, then now.** It opens on an origin story, often centuries back, and walks forward to the present question.

> The wristwatch was an invention of convenience for extreme conditions. … pilots wanted precise time measurements without getting in the way. So ingeniously they strapped the watch to their wrist in order to free the hands to fly the plane yet still provide quick access to time. (*Apple Watch – Internet of Humans*, 2015)

> In 1784, Benjamin Franklin suggested that Parisians change their sleep schedules to save candles and lamp oil. (*The Hidden Costs of Daylight Saving Time*, 2023)

**4. The personal story that becomes a system.** A moment from his own life or career leads to the frustration it revealed, then to what he did about it, then to where it led. This is how he talks on stage:

> So, this was a spacecraft I worked on in the early 2000s. Uh does anyone know what it is? … Now, what I found frustrating were two aspects … when I asked, cool, can I go play with the data? said, you can't play with the data. … So that motivated me to … think about how technology can … [make] data more accessible for people to make their own decisions. (NYGeoCon 2025 keynote)

> This is me at a local DC Department of Transportation hackathon … with my newborn son because I had daycare that day … And now … he and I bike to school every day along the routes that he helped build hacks to have the government change those streets. (NYGeoCon 2025 keynote)

The fourth shape is the one the generated drafts most need. Every abstract claim in them ("pendants capture micro-decisions") has a concrete scene behind it in Andrew's life. Find that scene and lead with it.

## Openings

He starts in time and place, with himself in it, or with a fact old enough to surprise:

- "Last week I attended and presented at the North Carolina GIS Conference in Raleigh, NC."
- "Tonight I joined a copious amount of art students at the Michigan Theater to hear Rachel Greene speak…"
- "A little more than a year ago, a small group of volunteers coordinated to host the first CrisisCamp in Washington, DC."
- "Ten years ago, I joined Esri when GeoIQ was acquired."
- "Most people across the U.S. lost an hour of sleep last weekend."
- "Signed by President Abraham Lincoln in 1863, the National Academy of Sciences was formed to…"

He doesn't open with a thesis, with "I'm increasingly convinced", with "This post is about…", or with a one-line paragraph that sets up a reversal.

## Endings

He ends by looking forward, inviting the reader in, or with a wry line. At most once in a while, he lands one reframe:

- "This is still just a draft specification, so if you have thoughts, ideas, suggestions, now is the time to chime in…"
- "I'm very interested to see the general developer reaction to this change."
- "If you just have a computer and internet connection you can help."
- "If only they could put us in hibernation at the end of the trip so we just 'showed up' at home, all exuberant and vibrant…"
- "The future is not an internet of things, it's an Internet of Humans." (*the reframe; once, and earned by 1,100 words*)

A heading called "Closing thought" or "Conclusion" never appears in his posts, and the last line is never a slogan followed by a one-word paragraph.

## Sentences and paragraphs

- **Sentence length:** his sentences run long and carry clauses: "However, obviously the above solution is bending the terms of service. Probably not a large concern when you're deploying to the middle of Nigeria – but all the same, DigitalGlobe probably wouldn't be too happy if you started sharing this imagery." A short sentence lands after a long one. A fragment is a punchline, used once, not as a rhythm.
- **Paragraphs:** paragraphs of 2–6 sentences, each a step in the story. One-line paragraphs are rare.
- **Connectives:** he moves with spoken connectives. "So", "However", "Of course", "Granted", "Now", "Anyways", "By contrast", "Obviously". In talks, "right?" and "okay?".
- **Person:** he uses the first person about ten times per 1,000 words, "you" about six. He addresses the reader directly when inviting them to try something.
- **Parentheses:** five or so per 1,000 words, used for asides, jokes and disclosures. "(or would ethercommute be more appropriate?)", "(well, in certain circles)", "(Disclaimer: one of the authors is my spouse, so you can imagine the geekiness of our family conversations.)"
- **Contractions:** used, about eleven per 1,000 words.

## Texture

- **Names:** people, products, places, versions and file paths. "Todd Huffman", "Steve Chilton and Ken Field", "the MARC train from DC Union Station to Camden Yards", "/Users/ajturner/Library/Caches/Google Earth", "0.002 meters of accuracy", "17 [DVDs] … every two years". Name the specific thing.
- **Numbers:** a number anchors a claim, then the story moves on.
- **Balanced verdicts:** "a really great step … however there should just a tiny bit more effort", "Not bad – but many new gears and prone to be difficult to maintain", "I both enjoyed but also some consternation". He praises and criticizes in the same breath, not in separate sections.
- **Humor:** dry humor in passing. "I like my coffee relatively root free." "Who needs pants?" "Ha, jokes on them." "trigger warning… bare images of the earth". The humor never carries the argument.
- **His own part:** he says what he did, including small or accidental things. "on a whim I registered crisiscommons.org, installed MediaWiki and Mikel provided a logo."
- **Headings:** a few, short, often playful: "Who needs pants?", "Fashionable Cyborgs", "Peek under the covers", "Let's do the 'right' thing", "DST is like a bad Product Manager". Not "Why this is suddenly possible" or "The use cases that actually matter". A post under 800 words usually needs none.
- **Bullets:** for link lists, resources, specs and step-by-step instructions. Never as the argument.

## Never

| Instead of | Write |
| --- | --- |
| "It's not X. It's Y." / "Not X. Y." | What happened that showed it was Y. |
| One-line paragraph, then a one-word paragraph | A paragraph that says it with the example. |
| "Closing thought", "Key takeaways", "In conclusion" | No heading; end on the next step, the invitation, or the reframe. |
| "The scarce resource isn't X. It's Y." | Don't. |
| "This post is my attempt to…", "In this post I…" | Start with the scene. |
| "Here's the thing", "That's it.", "That's the tax." | Cut. |
| A section of bullets that makes an argument | Sentences, in the order things happened. |
| Invented anecdotes, quotes or numbers | `[TK: the moment this happened — when, where, who]` for Andrew to fill in. |

## Revising a draft into his voice

1. **Find the scene.** Ask when this actually happened to Andrew: a meeting, a trip, a talk, something his kids said, a bug. If the draft or notes don't say, insert a `[TK: …]` placeholder rather than invent one.
2. **Pick a shape** from the four above, usually the personal story or the field report.
3. **Put Andrew in the first paragraph,** with a time and a place.
4. **Turn bullets into sentences,** ordered by what happened or what he tried, with the reason each mattered.
5. **Replace every reversal** with the evidence that made the point.
6. **Add the texture the facts allow:** names, numbers, one aside, one dry line. Don't add facts.
7. **Cut headings to two or three short ones,** or none.
8. **End on the next step, an invitation, or one earned reframe.**
9. **Run** `python -m scripts.heo.voice_check <file>`. Fix every FAIL; read the notes.

## Example: the AI pendant draft, opening

The draft:

> I'm increasingly convinced the most interesting form factor for AI isn't another screen.
>
> It's the opposite: a computer you don't touch.

In his voice. The facts come from Notion: the NYGeoCon 2025 lunch keynote (October 9, 2025, about forty minutes) was transcribed from his Limitless pendant, errors included. Anything in brackets is for Andrew to supply; the rewrite doesn't invent it.

> In October 2025 I gave the lunch keynote at NYGeoCon, and the record of it I ended up with came from the Limitless pendant I'd been wearing [TK: for how long, and why I started]. I read back forty minutes of my own talk, transcription errors and all. The GOCE spacecraft became "Gochi", HIFLD became "Highfield", and the Marshall Islands stick charts became "meadow charts". [TK: what struck me reading it: what I actually said on stage compared with what I meant to say.]

The facts are the same as the draft's. What's added is a time, a place, Andrew in it, a specific failure that's funny, and the story told before the claim.

## Corrections

His older posts have typos and run-on grammar ("there should just a tiny bit more effort"). Keep the voice and fix the errors: long sentences, yes; broken sentences, no.
