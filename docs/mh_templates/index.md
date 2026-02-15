---
title: "Inside the Template Engine: How Moving Heads Learn to Dance"
layout: default
---

# Inside the Template Engine: How Moving Heads Learn to Dance

### Part 0: [The LLM Clocked Out. The Math Punched In.](00_overview.md)

> The planner says “use sweep_lr_chevron_breathe.” Cool. Now we have to turn that sentence into 0–255 DMX values that make real motors move without blasting the neighbor’s driveway.

### Part 1: [One Python Function, 40 Decisions: Dissecting a Template Without Crying](01_template_anatomy.md)

> Templates look like tidy Python objects until you realize they encode geometry, motion, dimmer, timing, repeats, and fixture roles—all in one return statement. We’ll unpack sweep_lr_chevron_breathe line-by-line, and yes, we’ll judge some of our own choices.

### Part 2: [Point the Beams in a V, They Said. It’ll Be Easy, They Said.](02_geometry.md)

> Before a single curve wiggles, we have to decide where every fixture points. CHEVRON_V sounds like a vibe. It’s actually role math, pose anchors, and tiny tilt biases that somehow matter a lot.

### Part 3: [Waveforms: Because ‘Wiggle It’ Isn’t a Compiler Option](03_curves_generation.md)

> Every sweep, pulse, and ‘breathe’ is just a curve: normalized time, normalized value. We’ll build the actual waveforms twinklr uses—sine, triangle, musical accents, easing, noise—and show why the first version looked like a possessed desk fan.

### Part 4: [Curve Semantics: The Part Where 0.5 Means ‘Don’t Move’ (And 0.5 Also Means ‘Half Bright’)](04_curves_semantics.md)

> A sine wave is innocent until you interpret it. For pan/tilt, 0.5 means “stay on the base pose.” For dimmer, 0.5 means “half bright.” We’ll cover centering, loop readiness, phase shifting, simplification, and the exact math that turns curves into DMX.

### Part 5: [Movement: How to Sweep Without Slamming the Pan Into 0 Like a Roomba](05_movement.md)

> Geometry gives you a base pose. Curves give you motion. Movement handlers glue them together—then clamp the result so your OUTER_LEFT fixture doesn’t try to sweep past the physical limit and ‘flatline’ against DMX 0.

### Part 6: [Dimmer: Teaching LEDs to Breathe Instead of Blink](06_dimmer.md)

> Movement sells the choreography. Dimmer sells the emotion. We’ll build the PULSE ‘breathe’ curve for sweep_lr_chevron_breathe, including the two-stage scaling that makes it feel alive instead of like a broken porch light.

### Part 7: [Timing & Phase: Making Four Fixtures Stop Acting Like One Big Nervous Fixture](07_timing_phase.md)

> Four fixtures in perfect sync is fine. Four fixtures with staggered phase is choreography. We’ll cover BeatGrid time, repeat scheduling, chase orders, wrap behavior, and the real cost: once you phase-shift, you can’t group effects anymore.

### Part 8: [Transitions: Hiding the Crime Scene Between Two Templates](08_transitions.md)

> A template boundary is where glitches go to be seen. Pan/tilt can’t snap, dimmer crossfades can reveal repositioning, and discrete channels absolutely must snap. We’ll build per-channel blending strategies so handoffs look intentional instead of broken.

### Part 9: [Compilation Day: Following One Template All the Way to an .xsq File](09_compilation.md)

> This is the payoff. We’ll trace sweep_lr_chevron_breathe through the actual compiler: preset application, repeat scheduling, geometry, movement, dimmer, phase offsets, segment IR, DMX conversion, and finally the xLights value curve strings that make the whole thing real.

### Part 10: [We’ve Got Pan/Tilt/Dimmer. The Fixture Has Six Channels. Uh Oh.](10_whats_next.md)

> The template engine works—and it’s deterministic, testable, and weirdly fun. But we’re only driving three channels. Next up: shutter, color, gobo, and the slightly unhinged idea of generating moving-head choreography that complements an existing xLights sequence.
