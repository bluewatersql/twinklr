---
title: "The Feature Engineering Pipeline: Teaching Machines to Read Light Shows"
layout: default
---

# The Feature Engineering Pipeline: Teaching Machines to Read Light Shows

### Part 0: [The Choreography Was Hiding in the XML the Whole Time](00_overview.md)

> We start with the weirdest premise in the stack: hundreds of human-made Christmas light shows already contain choreographic knowledge, but it's trapped in XML and audio files. This post frames feature engineering as the slightly obsessive process of teaching machines to read that hidden score before any planner gets to be clever.

### Part 1: [Know Thy Corpus: XML, Zip Files, and Mildly Hostile Reality](01_profiling_the_raw_material.md)

> Before you can mine patterns from light shows, you have to answer the glamorous first question of every data project: what on earth is in these files? This post walks through how sequence packs get ingested, fingerprinted, enriched with layout context, and turned into something the rest of the pipeline can trust.

### Part 2: [Teaching a WAV File to Admit Where the Chorus Is](02_audio_feature_extraction.md)

> A raw audio file is just a lot of numbers until you bully it—politely, with DSP—into revealing tempo, energy, harmony, structure, and tension. This post digs into the audio side of the pipeline, including the parts that actually worked and the parts that spent weeks hallucinating section boundaries every few seconds.

### Part 3: [Two Timelines Walk Into a Bar: Alignment, Phrases, and Finally Some Signal](03_alignment_and_encoding.md)

> This is the bridge post—the one where raw sequence events finally get attached to musical context and stop being lonely timestamps. We align every effect to the beat grid, annotate it with energy, harmony, and section context, then group those events into phrases that actually mean something.

### Part 4: [Mining for Choreography Gold, Finding Some Fool's Gold Too](04_pattern_mining.md)

> Once you have thousands of aligned phrases, the fun starts: recurring patterns, template families, motifs, and a shared taxonomy begin to emerge. This post is the discovery phase in full—equal parts unsupervised learning, careful thresholds, and refusing to mistake one designer's personal obsession for a universal rule.

### Part 5: [From Patterns to Taste: How the Corpus Learns Style, Flow, and Color Drama](05_knowledge_extraction.md)

> Finding recurring templates is only half the story. This post is about the higher-order stuff: style fingerprints, transition logic, color arcs, propensity scores, and the relational knowledge that helps the planner stop choosing effects like it’s drawing from a festive vending machine.

### Part 6: [Promoted to Production: When a Mined Pattern Earns the Right to Boss the Lights Around](06_from_patterns_to_recipes.md)

> A frequent pattern is just an observation until it survives quality gates and turns into an executable recipe. This post covers the promotion pipeline, recipe synthesis, adapter contracts, and the point where feature engineering stops being an interesting analysis exercise and starts directly shaping real sequences.

### Part 7: [The Feedback Loop That Keeps the Lights From Having an Existential Crisis](07_the_virtuous_loop.md)

> The pipeline only matters if it improves actual plans and rendered shows. This final post closes the loop: how feature artifacts shape planner context, how we evaluate whether they help, and why the most interesting next step might be using the same feature machinery not just to imitate designers—but to help invent new patterns responsibly.
