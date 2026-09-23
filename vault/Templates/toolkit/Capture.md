<%*
const title = (await tp.system.prompt("What is this capture about?")) || "Untitled";
const slug = title.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "");
await tp.file.move("01_Capture/Note-" + slug);
-%>
---
via: clip
saved_at: <% tp.date.now("YYYY-MM-DDTHH:mm:ss") %>
source: 
---

# <% title %>

<% tp.file.cursor() %>
