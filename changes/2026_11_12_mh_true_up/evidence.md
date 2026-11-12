---
type: review
status: complete
area: reference
created: 2026-11-12
updated: 2026-11-12
---

# Research evidence

This is a dated research/check record, not a human taste verdict or real-fixture acceptance.
The authoritative synthesis is [report.md](report.md).

## Source retrieval and pins

Public xLights source was fetched through the GitHub connector, pinned to
`fe78fdddb7524cea71ee4c2ac4c22e20c16d478f`. The official `2026.19` release metadata
reports publication at `2026-10-23T17:36:19Z` and explicitly announces the generator.
The following SHA-256 hashes identify the retrieved UTF-8 source in the scratch copies
used for inspection and compilation:

| File | SHA-256 of scratch copy |
|---|---|
| `src-core/effects/MovingHeadSongGenerator.cpp` | `50967cf457e39545529c49bdfb7cf546525b18633d6bb058fffc84683abb44e3` |
| `src-core/effects/MovingHeadSongGenerator.h` | `8f7cda2c0938b37413aac0c9cef0000266e7eff46877cb5e669eec2f4c3e8821` |
| `src-ui-wx/sequencer/MovingHeadSongDialog.cpp` | `d43d364e323e0f4125426af0da661ad87cbfaff8ef2b1207b3ad4e1bd6ff9aba` |
| `src-core/effects/MovingHeadEffect.cpp` | `36fbc4fefe1c732762bea508c46bc295a5a8bd1d7fa6e2452e99b8371b6d8f07` |

The generator `.cpp`, dialog `.cpp`, and effect `.cpp` were independently fetched at
`2026.19`; comparing connector-returned content strings to pinned-master content
returned equality for all three. This cross-check does not claim every other xLights
file is identical between versions.

Twinklr source inspection began at `ab1e1457c8b524706f9ebaa55e65af2b743bfb07` and finished
at `2d1af61d69a0acc1b5dd877dd64459d9fbfb0f3f` after another session advanced the shared
branch. The audit reviewed that intervening correction. This research made no Git
commit and did not change application code.

A later independently authored `9c55c2e72c4bfea30a5ab7ae197579e4feb74485` commit
regenerated 11 golden-output files only. `git diff --stat 2d1af61..HEAD` confirmed no
application-source change at that point, so the capability audit remains pinned to
`2d1af61`.

## Isolated generator probe

Compiled the unmodified upstream `MovingHeadSongGenerator.cpp` with a temporary C++
probe, using only synthetic bars/section/head data. Exact command executed successfully:

```sh
c++ -std=c++17 -Wall -Wextra -pedantic /tmp/twinklr-xlights-research/probe.cpp /tmp/twinklr-xlights-research/src-core/effects/MovingHeadSongGenerator.cpp -o /tmp/twinklr-xlights-research/probe && /tmp/twinklr-xlights-research/probe
```

Exit status: **0**. Output:

```text
no sections: lit=24 dark=4 bursts=0
peak without chorus: lit=24 dark=4 bursts=0
chorus and peak: lit=44 dark=36 bursts=8
partial regeneration equals filtered full result: PASS
slow fixture can retain insufficient travel time: CONFIRMED
```

Burst records are a subset of lit records, identified by the current burst point-list
length. These results confirm returned data only. No GUI, DMX frame rendering, real
motor, optical output, or subjective acceptance was exercised.

To reproduce, retrieve the pinned generator header/source into the paths above and
save the following original research probe as `probe.cpp` (or adjust the command's
scratch path). No probe file is installed into Twinklr source or tests.

```cpp
#include "src-core/effects/MovingHeadSongGenerator.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <vector>
int main() {
    using namespace MovingHeadSong;
    std::vector<long> bars;
    for (int i=0;i<=12;++i) bars.push_back(i*2000);
    auto count=[](const std::vector<HeadEffect>& v) {
        int lit=0,dark=0,burst=0;
        for(auto& e:v) { if(e.linked) ++dark; else ++lit; if(e.dimmer.size()==16) ++burst; }
        std::cout << "lit="<<lit<<" dark="<<dark<<" bursts="<<burst<<"\n";
    };
    auto pool=Generate(bars,{},4);
    std::cout<<"no sections: "; count(pool);
    auto peakOnly=Generate(bars,{{0,24000,false,true}},4);
    std::cout<<"peak without chorus: "; count(peakOnly);
    for(auto& e:peakOnly) assert(e.dimmer.size()!=16);
    auto chorus=Generate(bars,{{0,8000,false,false},{8000,24000,true,true}},4);
    std::cout<<"chorus and peak: "; count(chorus);
    auto partial=Generate(bars,{{0,8000,false,false},{8000,24000,true,true}},4,Params{}, {0,3});
    size_t j=0;
    for(auto& e:chorus) if(e.head==0||e.head==3) {
        auto& p=partial.at(j++);
        assert(e.head==p.head && e.startMS==p.startMS && e.endMS==p.endMS && e.tilt0==p.tilt0 && e.tilt1==p.tilt1 && e.linked==p.linked && e.dimmer==p.dimmer);
    }
    assert(j==partial.size());
    std::cout<<"partial regeneration equals filtered full result: PASS\n";
    bool shortMove=false;
    Params slow; slow.tiltSlewDegPerSec={1,1,1,1};
    auto infeasible=Generate(bars,{{0,8000,false,false},{8000,24000,true,true}},4,slow);
    for(size_t i=1;i+1<infeasible.size();++i) {
        auto& e=infeasible[i]; auto& prev=infeasible[i-1]; auto& next=infeasible[i+1];
        if(e.linked && !prev.linked && !next.linked && prev.head==e.head && next.head==e.head) {
            double need=std::abs(next.tilt0-prev.tilt1)*1000*1.15+50;
            if(e.endMS-e.startMS<need) shortMove=true;
        }
    }
    assert(shortMove);
    std::cout<<"slow fixture can retain insufficient travel time: CONFIRMED\n";
}
```

## Repository checks and omissions

- Initial `git status --short --branch`: clean branch `chore/knowledge-optimization`.
- Source-reference existence check: all 32 local report reference targets existed.
- An initial reference-resolution check found the missing `XWiki` reference definition;
  the definition was added before the final rerun.
- Final local-link/reference/fence/placeholder checks passed for all five Markdown
  files. New-file `git diff --no-index --check` output contained no whitespace diagnostics.
  An initial wrapper's incorrect exit-zero expectation was corrected; no file fix was needed.
- Independent [review](review.md) approved the research with no material findings,
  reproduced the existing probe executable's results, and checked critical source claims.
- License-name scan: `git ls-files '*LICENSE*' '*License*' '*license*'` returned no tracked matches.
- A public GNU license-page fetch timed out; license identification instead uses the
  successfully retrieved pinned xLights `License.txt`. No legal compatibility verdict.
- Full repository `make validate`: **not run**. This research-only task did not authorize
  application changes; that gate requires a clean committed tree and rewrites files.
  No existing gate result is presented as a fresh validation result for this session.
- No live providers, owner-local data, xLights show changes, or external messages.

Final document checks and independent review outcomes are recorded in [handoff.md](handoff.md).
