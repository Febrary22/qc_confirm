# Relay

Relay is the team's Slack replacement for use inside the office network,
where slack.com is blocked but `claude.ai` is reachable. It runs as a
[Claude Artifact](https://claude.ai/code/artifact/411b3c7f-2246-4b28-89d1-4b350eb428cc)
(a hosted page on claude.ai), not as an app deployed from this repo — the
live app is always at that link, updated by republishing from a Claude
Code session.

`relay.html` in this folder is a **read-only mirror of the page's source**,
committed here so it's reviewable through git like the rest of the
project. Editing this file does **not** change the live app — changes
only take effect once someone republishes it from a Claude session.

## What it does

- **Home** — a short usage guide, shown first.
- **채팅 (Chat)** — team chat. `/ask <question>` gets an immediate answer
  from Claude. `/github <request>` queues a task card that a Claude Code
  session picks up on request (see below) and works on in this repo.
- **보드 (Board)** — a shared checklist. Anyone can add, check off, edit,
  or delete an item.
- **달력 (Calendar)** — a shared month calendar. Single-day items show as
  a dot; picking an end date turns an entry into a colored bar spanning
  the days it covers. Color and text are editable after creation.
- **Presence** — the sidebar shows who's online right now (via the
  `room` capability) and, from a small `roster` collection this page
  writes to, who's known but currently offline, each with a "last seen"
  time. A 💬 button opens a lightweight 1:1 DM thread with any teammate.

## How the GitHub hookup works

Artifacts can't make outbound network calls (CSP), so there's no real
webhook from the page to GitHub. Instead: a `/github` message just writes
a `status: "pending"` task document to the artifact's shared database.
A Claude Code session with access to this repo checks that queue **when
asked** ("Relay 확인해줘") — it is not on an unattended timer — reads the
pending tasks, does the requested GitHub work, and writes the result back
onto the task card so everyone sees it in Relay.

## Data

Everything (`messages`, `board_items`, `events`, `roster`, `dms/*`) lives
in the artifact's own database, scoped to this one Claude Artifact — it's
shared by everyone who opens the link, not stored in this repo. DMs are
routed by a hash of each person's display name, not a real per-account
identity, so treat them as team-internal rather than truly private.
