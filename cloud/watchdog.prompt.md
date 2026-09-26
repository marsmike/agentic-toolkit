Check the TheVoid pipeline once, then stop. Ask no questions, run no pipeline, edit and commit
nothing, print no environment value.
1. cd into the agentic-toolkit checkout (the directory holding cloud/watchdog.prompt.md) and export
   TOOLKIT_VAULT=<the TheVoid checkout: the directory holding AGENTS.md and 00_Memory/>.
2. Run: uv run --locked --project plugins/obsidian/scripts python3 plugins/obsidian/scripts/watchdog.py --json
3. If "ok" is true: finish with one line, `OK <facts.last_run>: <facts.last_summary>`, and send nothing.
   If "ok" is false: send ONE push notification whose text is the result's `notification` field,
   exactly as printed (the script already cut it to 600 characters), then finish with that text.
   Whenever `weekly_digest` is non-empty (only the Sunday 20:58 UTC check, judged by the clock): send it as a push notification
   of its own, exactly as printed, in addition to the above.
