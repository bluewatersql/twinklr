# Independent artifact review — 2026-11-20

Verdict: APPROVED for movement-inspection delivery. No blocking artifact defects found. This is not owner visual acceptance or hardware calibration. Checks were read-only; only this review record was written.

Independent evidence:
- Exactly 61 unique bases: all 37 historical arrangements plus the prior sampler’s same 24 bases; Zoom Wave excluded. Manifest identifies clean source 577b242c. Separate code review established d4868e87 adds only presets, leaving base objects unchanged.
- 640 seconds, 32,000 frames, 50 fps; native 1280x720, labeled 1280x824. Chapter names and ends all match the manifest. Chapters 2–61 start exactly at case boundaries; MP4 chapter 1 starts at zero and includes the two-second intro, a harmless muxer normalization.
- All 61 active arrays match case caches, and every two-second separator has zero dimmer bytes. Independently reconstructed all 2,048,000 channel bytes from XSQ effect settings and matched frames.npz exactly.
- Production traces confirm full arcs: Build/Drop/Recover at 0/4/8 seconds over 12 seconds; Intro/Main/Outro at 0/4/12 seconds over 16 seconds; Crossfade a,b,b,a at 0/4/8/12 seconds over 16 seconds. Ambient eight-bar cycle gets 16 seconds.
- INNER pendulum keeps outer heads dark while both inner heads move. Scattered wave shows substantial independent pan and tilt travel on all four heads.
- Sixteen exact first/last-frame label checks around the four longer cases pass; maximum header MAE 0.86006. Blackout motion-reveal wording visually inspected.
- ZIP CRC valid. Packaged timeline, layout, network, media, profile, job and README match delivered bytes. Packaged XSQ equals standalone XML after its sole relative media-path change. Synthetic layout assigns four 16-channel heads at starts 1/17/33/49.
- Final video hash matches delivery-verification.json. Native audit records all 61 cases visible, pause beam-region values at most 2/255, zero bright edge pixels at 5 fps. Representative contact sheet visually inspected, including INNER isolation. Integrator’s 122 label comparisons also pass.

Disclosure: new arrangements use neutral white/open optical states in this scratch movement preview, retaining required dark edges. Two authored blackout routines are explicitly labeled as motion revealed. Catalog blue/prism/fast-shutter programs remain authored and source-tested; this preview does not claim light-program parity. README states that distinction accurately. Full source gate remains separate from artifact approval.
