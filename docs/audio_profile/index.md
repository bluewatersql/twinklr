---
title: "From Sound to Show: How Audio Intelligence Drives AI Choreography"
layout: default
---

# From Sound to Show: How Audio Intelligence Drives AI Choreography

### Part 0: [Giving the Robot Ears Before It Touches the Lights](00_overview.md)

> You can’t ask an AI to choreograph a Christmas song if all it sees is a pile of sample values. This opener sets up the real problem: turning raw audio into musical facts an LLM can actually reason about without making the show look like the roofline is having a crisis.

### Part 1: [The Pulse: When the Beat Tracker Hears 126 BPM and the Song Swears It’s 63](01_the_pulse.md)

> Rhythm extraction sounds easy right up until the algorithm confidently hears half-time as double-time and starts gaslighting your whole pipeline. This part gets into tempo, beat tracking, downbeats, time signatures, and the BeatGrid that keeps everything from drifting into chaos.

### Part 2: [The Dynamics: Loud Isn’t the Same as Intense, and the Audio Pipeline Learned That the Hard Way](02_the_dynamics.md)

> A song can be loud without feeling big, and quiet without feeling small. This part gets into multiscale energy, spectral features, build/drop detection, and the awkward journey from measuring amplitude to measuring felt intensity.

### Part 3: [The Architecture: Section Detection, or How We Stopped Letting the Chorus Start in the Wrong Universe](03_the_architecture.md)

> Beat errors are annoying. Section errors are disastrous. This part gets into the hardest audio problem in the stack: figuring out where verses, choruses, bridges, and intros actually begin so the planner doesn’t blow the big reveal four bars early.

### Part 4: [The Translation: How We Stuffed 100KB of Audio Facts Into 10KB Without Making the LLM Useless](04_the_translation.md)

> Raw audio features are rich, detailed, and borderline toxic to an LLM if you dump them in wholesale. This part is the bridge between deterministic analysis and creative interpretation: context shaping, 8-point curve compression, semantic labels, and the audio profiling agent that turns data into usable musical intelligence.

### Part 5: [The Words: Lyrics, Phonemes, and the Five-Layer Fallback Chain We Built Because Reality Was Rude](05_the_words.md)

> Lyrics can turn a synchronized light show into one that actually means something—assuming you can find the lyrics, time them, trust them, and survive five different failure modes along the way. This part covers the lyrics pipeline, phoneme timing, and why the system treats lyrical intelligence as optional but incredibly valuable.

### Part 6: [The Thread: Following One Audio Decision All the Way to the Lights on the Roof](06_the_thread.md)

> By this point the audio pipeline isn’t just analysis—it’s the thread running through the whole system. This part traces exactly how beats, sections, energy, and lyrics propagate through profiling, planning, judging, and rendering until they become actual timed lighting effects.

### Part 7: [The Playbook: Things We’d Tell Past Us Before We Let an LLM Choreograph Christmas Lights Again](07_the_playbook.md)

> After building the whole audio intelligence stack, a few patterns kept proving themselves and a few mistakes kept coming back to haunt us. This closer distills what worked, what surprised us, what we’d redo, and which lessons generalize far beyond holiday lighting.
