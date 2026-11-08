# highearthorbit.com

Content and code for Andrew Turner's site. See README.md for how content, sync and publishing work.

## Writing

Any prose published as Andrew (posts, talk write-ups, project and album summaries, the About and Now pages) follows `docs/voice/style-guide.md`. Use the `heo-voice` skill (`.claude/skills/heo-voice/SKILL.md`) and check drafts with `python -m scripts.heo.voice_check <file>`. Never invent anecdotes, quotes or numbers; leave `[TK: …]` for Andrew to fill in.

## Checks before a pull request

```sh
python -m scripts.heo.validate
python -m pytest -q
```
