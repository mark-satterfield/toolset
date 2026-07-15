---
kind: section
name: info-note
page_family: app
aliases: [info footer, disclaimer strip, helper note]
status: stable
shape: note-strip
content_contract:
  link: "present | absent"
theme: default
composition_notes: []
---

# Info note

A small footer strip at the bottom of the Page: an info icon followed by a single helper sentence with an optional embedded link ("ⓘ Usage figures are estimates for analytics purposes. For details, refer to the usage dashboard."). It qualifies the data above it without competing with it. Its layout is the note-strip Shape (`libraries/shapes/note-strip.md`): the info icon fills the icon slot and the helper sentence fills the note slot.
