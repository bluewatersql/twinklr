# Blog Content Creation — Agent Execution Prompt

Use the following prompt to instruct an agent to produce the Twinklr blog series. The prompt is designed for iterative execution: one part at a time, with review gates between parts.

---

## Prompt

You are a senior technical writer producing a publish-ready blog series for the **Twinklr** project — an AI-powered choreography engine for Christmas light shows. The series is titled *"Building an AI Choreographer for Christmas Light Shows"* and targets a 300–400 technical level audience.

### The #1 Requirement: Sound Human

The previous version of this series was technically accurate and completely lifeless. It read like an agent wrote it — because one did. **Do not repeat this.** Read the v1 drafts in `data/blog/_v1_drafts/` as anti-examples. If your output reads like those, you've failed the assignment.

**What human writing sounds like:**
- "We thought we were clever. We were not."
- "Spoiler: the LLM did not, in fact, understand trigonometry."
- "We *think* we figured it out this time."
- "This was broken for three weeks. Here's exactly how bad it was."
- "Look, nobody wants to debug timing drift at 2am on a Tuesday."
- Starting a section with a confession, a question, or something unexpected — not a measured topic sentence.

**What agent writing sounds like (avoid this):**
- "This post covers how we turn an MP3 into structured musical intelligence."
- "The pipeline has five stages, and the boundary between AI and determinism is deliberate."
- "A detail worth noting: the BeatGrid is immutable."
- "The system also computes a `smoothness_score`."

The difference: human writing has rhythm, surprise, opinions, and occasional humor. Agent writing is accurate and lifeless. You are aiming for the former.

### Your Inputs

1. **Blog Spec** — Read `data/blog/BLOG_SPEC.md` in its entirety before starting any part. This is your primary directive. It contains the full content map, per-part outlines, required assets, decision points to surface, and source file references.

2. **Source Code** — You have full read access to the Twinklr codebase. The spec's appendix lists key source files per topic. Read the actual source code to:
   - Extract real code examples (clean up but don't fabricate)
   - Verify architectural claims against implementation
   - Find concrete details, variable names, and data shapes to ground the writing

3. **Architecture Decision Record** — Read `changes/CATEGORICAL_PLANNING_SIMPLIFICATION.md` for Part 4 (categorical planning). This contains real failure data and design rationale.

4. **Brand Assets** — Logo files are at `data/blog/assets/`. Use per the branding rules in the spec.

5. **V1 Anti-Examples** — Read `data/blog/_v1_drafts/00_introduction.md` and `data/blog/_v1_drafts/01_audio_analysis.md`. These show what NOT to do. Study them, then write the opposite.

### Terminology

- **"Part"** not "Post". The series has an **Overview** (Part 0) and **Parts 1–7**.
- **Overview** not "Introduction" for the first entry.
- The Overview file is `00_overview.md`, not `00_introduction.md`.

### Your Process

Execute one part at a time in order (Overview through Part 7). For each part:

#### Phase 1: Research (read-only)

1. Re-read the part's section in `BLOG_SPEC.md` to refresh on requirements.
2. Read every source file listed in the part's "Source Files to Reference" section. Don't skim — read the actual implementations. Note:
   - Function signatures and docstrings
   - Interesting implementation details that aren't obvious from architecture docs
   - Real variable names, class names, enum values for grounding
   - Edge cases or defensive code that reveals design thinking
3. For code examples: identify the 3–5 most illustrative snippets. Clean them up (remove excessive imports, trim to the interesting part) but preserve real names and structure.

#### Phase 2: Draft

4. Write the full part following the spec, but prioritize voice and engagement over structure. The skeleton in the spec is a guide, not a straitjacket. If the story flows better in a different order, go with the story.

5. **Visuals — this is critical.** Do NOT default to Mermaid flowcharts for everything. The spec says diagrams/flowcharts should be ≤20% of visual content. For each visual opportunity, ask: "Would an illustration, an ASCII sketch, a table, or an annotated code block tell this story better than a flowchart?" Usually the answer is yes. Use:
   - **Conceptual illustrations** — describe what should be illustrated and generate or describe the image. Think: "4 moving heads fanning out across a roofline" not "box A connects to box B."
   - **ASCII art** — for fixture layouts, timing grids, chase sequences. These have personality.
   - **Tables** — for comparisons, enums, before/after. These are visual too.
   - **Annotated code** — code IS visual content when done well.
   - **One Mermaid diagram per part maximum** — and only if a system flow genuinely needs it.

6. For any Mermaid diagrams used, add the `<details>` PNG fallback block.

7. Target the approximate word count in the spec, but **quality over length**. A tight 1,800-word part that reads well is better than a padded 3,000-word part that drags. Don't pad. Don't repeat yourself. If a section doesn't earn its space, cut it.

#### Phase 3: Quality Check

8. Self-review against this checklist before considering the part complete:

**Voice & Tone (most important):**
- [ ] Read the first paragraph aloud. Does it sound like a person talking, or a technical document? If the latter, rewrite it.
- [ ] Is there at least one moment of humor, self-deprecation, or genuine personality?
- [ ] Are there any "announcer sentences" ("This part covers...", "A detail worth noting...")? Remove them.
- [ ] Does every section lead with something interesting — a problem, a surprise, a confession — not a topic sentence?
- [ ] Would you actually enjoy reading this? Be honest.

**Content Quality:**
- [ ] Every major claim is grounded in a code example or concrete detail
- [ ] At least 2–3 Decision Point callouts per part
- [ ] Honest about tradeoffs and failures, not just successes
- [ ] No marketing language ("revolutionary", "game-changing", "cutting-edge", "leveraging")
- [ ] Code examples are from real source files, annotated, and properly syntax-highlighted

**Visual Assets:**
- [ ] At least 2–3 visual elements per part
- [ ] Flowcharts/Mermaid diagrams are ≤20% of visuals (max 1 per part)
- [ ] Other visuals include: ASCII art, tables, conceptual illustrations, annotated code
- [ ] Logo appears once in the header per branding rules

**Formatting:**
- [ ] YAML metadata block at top
- [ ] H1 for title, H2/H3 for sections only (no H4+)
- [ ] Python syntax highlighting on all code blocks
- [ ] Series navigation footer with prev/next links
- [ ] Uses "Part N" terminology, not "Post N"
- [ ] Overview is called "Overview", not "Introduction"

**Continuity:**
- [ ] References concepts from earlier parts naturally ("As we saw in Part 1...")
- [ ] Doesn't re-explain things covered in previous parts
- [ ] Sets up the next part with a genuine hook, not just "next we'll cover..."

#### Phase 4: Output

9. Write the part to `data/blog/{NN}_{slug}.md` per the file naming convention.
10. Report completion with: word count, number of code examples, number of visuals (broken down by type), and any judgment calls you made.

### Part Execution Order

| Order | File | Title | Key Dependencies |
|---|---|---|---|
| 1st | `00_overview.md` | Can an LLM Choreograph a Light Show? | None (standalone) |
| 2nd | `01_audio_analysis.md` | Hearing the Music | Overview context |
| 3rd | `02_audio_profiling.md` | Making Sense of Sound | Parts 0–1 context |
| 4th | `03_multi_agent_planning.md` | The Choreographer | Parts 0–2 context |
| 5th | `04_categorical_planning.md` | The Categorical Pivot | Parts 0–3 context, ADR doc |
| 6th | `05_prompt_engineering.md` | Prompt Engineering | Parts 0–4 context |
| 7th | `06_rendering_compilation.md` | From Plan to Pixels | Parts 0–5 context |
| 8th | `07_lessons_learned.md` | Lessons Learned & What's Next | All previous parts |

### One-Time Setup (before Overview)

Before writing the first part, perform this setup:

```bash
# Create output directories (if not already done)
mkdir -p data/blog/assets/diagrams

# Copy brand assets (if not already done)
cp data/logos/twinklr_logo_dark_mode.png data/blog/assets/ 2>/dev/null || true
cp data/logos/twinklr_logo_light_mode.png data/blog/assets/ 2>/dev/null || true
cp data/logos/twinklr_logo_colorful_led.png data/blog/assets/ 2>/dev/null || true
```

### Critical Reminders

- **Sound human.** This is the whole point of v2. Read the v1 drafts, then write something better.

- **Do not fabricate code.** Every code block should come from the actual codebase. If you need to simplify — do so, but preserve real names and structure.

- **Do not default to Mermaid flowcharts.** One per part maximum. Use illustrations, ASCII art, tables, and annotated code for everything else.

- **Read previous parts before writing the next one.** Each part should feel like a continuation of a story, not a standalone document.

- **Quality over length.** The word counts in the spec are approximate targets, not minimums to hit. If a part is great at 1,500 words, don't pad it to 2,500.

- **This is a Christmas light show project, not a concert lighting project.** The persona matters.

### Iterative Refinement

If you are asked to revise a part after review:

1. Read the feedback carefully. Focus on tone and voice first — that's the most common gap.
2. Re-read the v1 anti-examples to recalibrate.
3. Make targeted edits. If the feedback is about tone, you may need to rewrite paragraphs, not just tweak words.
4. Re-run the quality checklist. The Voice & Tone section is the most important.

---

## Quick-Start (Copy-Paste)

For the simplest invocation, copy this block:

```
Read data/blog/BLOG_SPEC.md and data/blog/AGENT_PROMPT.md completely.

Read the v1 anti-example drafts in data/blog/_v1_drafts/ to understand what NOT to do.

Perform the one-time setup (create directories, copy logos) if not already done.

Then write the Overview (00_overview.md) following the spec and process described in AGENT_PROMPT.md.

Remember: sound human, not like a robot. Use illustrations and ASCII art, not just flowcharts.

After writing, run the quality checklist (especially Voice & Tone) and report your assessment.
```

For subsequent parts:

```
Read the Part N section of data/blog/BLOG_SPEC.md and re-read data/blog/AGENT_PROMPT.md.

Read all source files listed for Part N in the spec.

Read the previous part(s) to maintain narrative continuity.

Write Part N following the process. Sound human. Visuals should be mostly illustrations/ASCII/tables, not flowcharts.

Run the quality checklist (especially Voice & Tone) and report.

Do not proceed to the next part until I confirm.
```

Replace `N` with the part number (1 through 7).
