<%*
const title = (await tp.system.prompt("The insight, in a few words")) || "Untitled";
const slug = title.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "");
await tp.file.move("01_Capture/Insight-" + slug);
-%>
---
via: clip
saved_at: <% tp.date.now("YYYY-MM-DDTHH:mm:ss") %>
source: own insight, <% tp.date.now("YYYY-MM-DD") %>
---

# <% title %>

## The insight

<% tp.file.cursor() %>

## Why it matters

## What it connects to

