"""Committed pins of moving-head output, so an unintended change to it fails CI.

Every catalog family, base and each declared preset, renders one 8-bar section on four
heads (the zoom pilot rig for `zoom_wave`, the family rig otherwise) over two synthetic
grids, a steady 500 ms beat and a seeded mix of 430, 500 and 580 ms beats; one
multi-section plan of four families renders over the varied grid and delivers its
`.xsq`; one gated plan renders under a hand-built gate result (an excluded preset and
effective variants), over a dark span, with `reposition_fallback="preserve_aim"`. Each
case pins its render fingerprint and the SHA-256 of its encoded frames
(`_frames_sha256`); the multi-section and gated cases also pin the delivered `.xsq`.

The values were recorded when the old renderer was removed (C1.2), from that tree; the
encoded frames and the `.xsq` are byte-identical to those of the commit before it
(`mh-last-with-legacy-renderer`), whose fingerprints differ only because the render
policy lost its `mode` key. C1.3 re-recorded the fingerprints alone: the template and
rig dumps they hash lost the old renderer's fields; frames and `.xsq` are unchanged.
C1.4 re-recorded them again: the hashed revision string and template keys were renamed;
frames and `.xsq` are unchanged. W2 re-recorded them again: the plan they hash is in the
song-intent planner contract (parts, intent fields); frames and `.xsq` are unchanged. W4
re-recorded them again: `RENDERER_REVISION` 3 (a section's colour and gobo render);
frames and `.xsq` are unchanged, every pinned plan being as authored. W4 also added the
song-intent pin (`INTENT_PIN`): colour and gobo sections on a tagged rig. The W3/W4
review fix round re-recorded every fingerprint once more (revision 4); every frame and
`.xsq` hash, `INTENT_PIN`'s included, is unchanged (its boundaries dip at 120 BPM, as
before). W5 re-recorded every fingerprint again (revision 5: DRAMATIC and INTENSE play on
the dimmer, and a show's focal role adjusts intensity); every frame and `.xsq` hash is
unchanged, no pinned plan setting an intensity, and added the intensity pins
(`INTENSITY_PINS`). The W3/W4 second review re-recorded every fingerprint again
(revision 6: a boundary dip counts and is bounded by the darkness it adds over a dark
span); every frame and `.xsq` hash is unchanged, the gated plan's dark span meeting no
colour change. The W5 review fix round re-recorded every fingerprint again (revision 7:
intensity shaped per lit run); every frame and `.xsq` hash is unchanged but two of the
intensity pins'. W6/W7 re-recorded every fingerprint again (revision 8: the plan's events
play, and the W5 re-review's accent rules); every frame and `.xsq` hash is unchanged, no
pinned plan having events and the pins' steady grid meeting none of those rules, and
added the event pins (`EVENT_PINS`). The W6/W7 fix round re-recorded every fingerprint
again (revision 9: events on the bar grid, hits visible, bounded wheel turns, per-beat
strobe rates); every frame and `.xsq` hash is unchanged but the event pins'. Revision 10
(the W6/W7 second fix round and W8 transitions) re-recorded every fingerprint once more,
every frame and `.xsq` hash unchanged, and added the transition pins (`TRANSITION_PINS`).
Revisions 18 (the arrangement built up from the reference), 19 (a FASTER step's narrower
reach tried), 20 (delayed first flash), 21 (W10d density), and 22 (W10e modifiers)
re-recorded the fingerprints. Revision 23 lets a snap use the outgoing closed hold.
The pinned plans keep their frame and `.xsq` hashes. An
intended output change bumps `RENDERER_REVISION` and re-records these pins in the same
commit, saying why.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
import hashlib
import json
from pathlib import Path
import random

import pytest

from tests.support import moving_heads as m
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline, TemplateAdmission
from twinklr.core.sequencer.moving_heads.song_intent import SectionPalette
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.theming.catalog import get_palette
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")

PINS: dict[str, tuple[str, str]] = {
    "steady/finite_snap_hold/base": (
        "d4085e75ac8b708b60b641395cb522a783f9eae255d6d787a379d74fcd713b3f",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow": (
        "cbafe84a4b6dc84c4d2551bdfdf6ca8d4318176b31e46083dfe1e98745b75656",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/slow": (
        "6231985cd20976ee1c464bceb38f0c3cfa49ab74210f6c05bcc18f86899362e1",
        "4d455965979b705ad9af8136e4fd229c7b5374635e1786d07b8cab7636861b9d",
    ),
    "steady/fly_in_cascade/base": (
        "d4aaf9e06b691e3ad78d5ab8717bdfdb1e597792f1049ce4029d76f29f4d5fad",
        "ffdfb044c11edf3040dd81744d17558a2d46c21181071367cca5f752a8413b0d",
    ),
    "steady/fly_in_cascade/narrow": (
        "f24a131c7e9339958706fc4ee3991a773169b33a3ae96861d8fe74f98e46ca81",
        "0280d85aaf1e832fc23b428e311b24ccb67dac720116f25f71d147261f88f310",
    ),
    "steady/fly_in_cascade/slow": (
        "a35ae146c3c6a7dbe7836c35c83e92d6fa7048fd9ecedecc0f6ba4eb412a937d",
        "dd49563a5956e1e52f4a2c01e8f005a64a297ff28f9155f3eb05d10a29312433",
    ),
    "steady/fly_out_cascade/base": (
        "8f7026da7e40f78817e252e5c90633a938a132c7b2b289df3af5906603fe7607",
        "4235e01012dddfdae05f050fa904a9efa2e8eb4cf4f3b7e2ddd06b23951c733e",
    ),
    "steady/fly_out_cascade/narrow": (
        "5fbe681670918ddc81c51f202b356e27fbd21fdf541626f67e0d33a706c0c455",
        "150edd82e9273731bd9ab781ab5c6caf420cf5d1129cddb637915687dab01a88",
    ),
    "steady/fly_out_cascade/slow": (
        "a92f4a5eadc3321c1b16a7cdc87ae0c212f2e1833dc0fd2f1fbeab8d7b44d7e5",
        "c7e91342cab3b42a868f59ab824961da433ac89db0c5646f1fd41e29b0444a70",
    ),
    "steady/masked_wheel_flick/base": (
        "691a7d723f6f33d00dda56c1c2ce0ae79b42944bf9555401d52ab1e72a8c84b1",
        "08ce9090980dbfefa79b6d78c90ef0f0b0c8ef3a19bb47d193d9af34805cd2de",
    ),
    "steady/masked_wheel_flick/narrow": (
        "37960f4b7170457ae0c768ed6314dd4cdd0d637fd3cafbfe1f1f69ac4ed709dc",
        "2537e7e6cf39dad19aadb07a271b223f83c2af7fbbe52b4732f6416cee5993ad",
    ),
    "steady/masked_wheel_flick/slow": (
        "4c53c70a3e2a4ccd7591e34d4153ae282a6598b9c4783030b96811eae6bad67e",
        "56a758e57a37773c558bff6f8134843cf45c76d005021a6e882374d16d96431a",
    ),
    "steady/mirror_wings/base": (
        "aa4f470d4be0e00c83578bae5c0c626d5e06f4dfdd1ce6f6ffd0398e7344a318",
        "8e3cb9be3de61f968b065d8d0442ac5551becdbbf4624afb76b13a58e0f000fd",
    ),
    "steady/mirror_wings/narrow": (
        "f96e2dc2bd4d7e567e89f370651a43e179c6dbece109af082449439b2f9977b0",
        "d83a23f4fea33e3e6f1b2bbfabdc0b5c26f605b673861c0021a1cc1c8bd36a1b",
    ),
    "steady/mirror_wings/slow": (
        "351b891347edba45ac65ffcade9dd468378d5de563f402dc2ec846eec6a92200",
        "bbcdbab3564fa3d0a7f107562326940ef92fa3f38130a37ac9d8b43f68bdd3b6",
    ),
    "steady/target_orbit/base": (
        "c7c609ac00c5b5116a46fe7f2e9bb433473b47741869611b0664d8a25d0043ce",
        "78d35ed327d359ca0cc456a151ae19f800a20b80ac1cc040ea4448be4d014ed1",
    ),
    "steady/target_orbit/narrow": (
        "8f480d85c61fd515d7b0b4906df407dc24f0b013055c6ce5b8109ecadbd033b6",
        "a35e080540356862ecfe8738414c7cef0d781b639b869db97bc27ff0db5f180b",
    ),
    "steady/target_orbit/slow": (
        "153d0b1d0ff2695bda7e280dcb7d951f62f17452a79c0f43e3229b4b552eb21c",
        "a2eb0bf1f4d04307af57da96941f9d02e8c47ffcc583db3361b0a754975c7d36",
    ),
    "steady/zoom_wave/base": (
        "25fc6f971287607a5a9112ba7dd2fd93053ef819f24a64babc281aee949656d8",
        "bfa3f5ef5efd80d8f801f76ab412044d35161bb606288fc35f6fbeaf6970675a",
    ),
    "steady/zoom_wave/narrow": (
        "89c9f3f0bc9fe368f7881b9986e96177eadb3a01f4d603a311200bbb405fef82",
        "0ddc62b56b92e1af2deedbc6b9bf47570bbe82663ff559091f3883f32e20169b",
    ),
    "steady/zoom_wave/slow": (
        "dc90ff4b916fc3277eecb2cd0356904a12b68bf91d7192d95d3e0d478966b2e7",
        "394aa7ae9fb0cc8e948e2c1b68264b9652edbddd44bcefd9d5ac0dea8e5cdb2c",
    ),
    "variable/finite_snap_hold/base": (
        "95e86b434216f359fe268f2d449f1995380cca9db2dca5ebe627877ff118a544",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow": (
        "370e62d84857542d0bf306eb2a1af7a8c864319f857913a3ad7ac397d0a21f6c",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/slow": (
        "f16a6104d2985578aec10159618ee35526ced181622dc60e97ac100a7fe10ad8",
        "e4f7f3d9a0863c4f423dae91e481e8874d5971308aa2196a93e6fca84a6d8930",
    ),
    "variable/fly_in_cascade/base": (
        "2554e2d20e1b33ee14efb155579a3beafe13822e513e7d9fe673907620d91241",
        "34f9987fa593584b7894352d13944905315dd6c260035971de447db3c121fd7a",
    ),
    "variable/fly_in_cascade/narrow": (
        "fe34c4b8d7cbc14aaeed0585347463a8aa8f58f3b57aefc98db2026af4cc8ae3",
        "f2d02f0c7cdbcda887bcd350188338a8bfe0ae583b2b5e092c64b921985f1a9e",
    ),
    "variable/fly_in_cascade/slow": (
        "a57f77c37bfc54aebcbf5169fb401b1466f25275323a8692a487d597687e2e34",
        "49c484a8585d159fc61d0989eef1cc2a35fc22a5e46cf202f789736c8dd37ebe",
    ),
    "variable/fly_out_cascade/base": (
        "cbb9cceab13bee376fece65d757d7ed8ad694af646a5a354a634f7ec0e1ecce3",
        "36f29b21188085c76c462a8cfd73f3e10f21f7adfdbca525a674c4960aca28d2",
    ),
    "variable/fly_out_cascade/narrow": (
        "2fe9f991be11f90a66b4578d6a9d1e170b9dc3f348870099f4f3d2cbd750e4ed",
        "c773f3be51097dd3ec2c309f6149f76e6c3bb7f6d1ea24416aba4662a10cb420",
    ),
    "variable/fly_out_cascade/slow": (
        "96798092431860c569ffa809ca21257fc01b19a861f92994023a1af879978c77",
        "de6e5fb69f6beeeb43df051367101bd88d3d75b61e811bab2ac3e69d2edd499a",
    ),
    "variable/masked_wheel_flick/base": (
        "ce08d9d45d4d5061c6b75ae53365acd7fde6e8218968716acdd9d4d1248e549a",
        "a628fb0ca672aba2a7c36e3ecfafcf1003b8d9c8a06adc5edcf0840004981f3f",
    ),
    "variable/masked_wheel_flick/narrow": (
        "f1510903d61bd03ec8eea87cc3a31b33760c21cd21515a6843454f44626dd579",
        "a8b2c6b2cf905f657c6993dca020c6aa14bbfacc10f89bfb97491860bc81a6c3",
    ),
    "variable/masked_wheel_flick/slow": (
        "9c80139d50d8f472945b3fe3cbc304e93e39d20b3d1661568c2f91119dba2362",
        "058ed1d9cbdde981fa5213dd23654d42fc86a9ebd6150fc50b089e07f85825f8",
    ),
    "variable/mirror_wings/base": (
        "cdcad732ee86c2ef891e63ebbef02be758f9e91a55a720b693795f956e37d3ce",
        "a59b343515d159c1603c1a0ed576afa3b6721178a643ad1c5fbc02d6bb706dde",
    ),
    "variable/mirror_wings/narrow": (
        "d597a5d181b92e50f26430445e1f90698f903db1bce240030b0193d839135914",
        "4d326471bc6af0e6f429bd8e5d5b7e374587d3f545a2fe3d2ad3ef908ab6f801",
    ),
    "variable/mirror_wings/slow": (
        "954b5e3e7508db12e383e9e5e8217d6218b66cb126038ac4b3b7bf3df398e681",
        "cee179ea21422e5e6f268664dd79981055afedfd98c5849c5dbfd44f5b80904e",
    ),
    "variable/target_orbit/base": (
        "7e7afaa1eb2b119f6d08251702c4743767b46bf0c037c52f2a074dda8016362c",
        "2bfe8b5bd75f0097dd6fb8011e38a11578764984050474ddf0ee402ae3c85fa1",
    ),
    "variable/target_orbit/narrow": (
        "23162ad76070998d1c94ca26a1cf00540c57684dd412ccb97ae5e16c1f1a6c0f",
        "9f453dce2badb89d745c808896a8fe6d3b9feafacf5d122371d75d0a6377b4a6",
    ),
    "variable/target_orbit/slow": (
        "0e966415a0467f78fe142b8862fb6b9f6f15e7ac01c2b09586e1ebd8be55dce9",
        "ac930585ef5e3f15f79cc7267d407f586e99f71923c67b287415b69ec32365c5",
    ),
    "variable/zoom_wave/base": (
        "c8de4068b03750e3876ae013275ee6a981700f2fcc093a2faeac8d204f0861d3",
        "0020b12393f7dd4cf89bb4c4bbf3cd942ed5aa0de2abde665b3caffefdc751a7",
    ),
    "variable/zoom_wave/narrow": (
        "f50028499afede198c5494409fa65e3cca1955607cbc9ae0c79193722c8690b5",
        "a39df6ddbe83086edd4664152946711a1b5a24a927837fd366218594215ce44a",
    ),
    "variable/zoom_wave/slow": (
        "6a17279e3b2a571be13be7b882f2369155e703c38c145c6a91aca8558f5986b3",
        "503a36b0d6d9b85cfa6e5518367e787f835571fbc02f9f44e09f96f2c6689561",
    ),
    "steady/finite_snap_hold/fast": (
        "a689959f3922b1667d8cd8dbe376afc372af37c54e6f7268769d3e5e1be8087a",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow+fast": (
        "a0dbc33be9f8f760fbe5ef188ca0203b4964c254c0f5b6c7eb26d65c1bcd8277",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/narrow+slow": (
        "79276d52e9071eaf68b4485e82e7fa0d8e69463e8e5f456273d2cf17788e020b",
        "84296f1bd1d0c1616da22afeecacfd8e2653b25a47e68272bba162023e8ed304",
    ),
    "steady/finite_snap_hold/wide": (
        "972d5b0bf9ee21f1a9cca70b989b360e7bb3f5a628627aab476211b3d30b6430",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+fast": (
        "2f4f3b0dd71811ed4cfc2d6e6dcd7fb0e00cd3abaf8281e047f0df431967d453",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+slow": (
        "49893d6f59c183e2bba2fa235e9584791dd17e43acb192ac16e242806d4b77c8",
        "9f9ddc3e26639bc1c0d79680d8363004b5817b974d67286d8edca8e459848bce",
    ),
    "steady/fly_in_cascade/fast": (
        "fa6e8dafdb75a923a216848fbfe270a95fd1d7fd38e0788e04c328d985a32013",
        "1a39008b463ea6e6e8aaae5119af1676e82017712e0ecec42606e526fd9db2d4",
    ),
    "steady/fly_in_cascade/narrow+fast": (
        "4ed7feffa3e6f3b5500411a8374deba8ce6351f8e172e4b00654300d9d301da4",
        "bef2eadb974023db7f86422e5dc581fdb3eb86a9f391ae5c569949528763b568",
    ),
    "steady/fly_in_cascade/narrow+slow": (
        "eb821d3cf212249752608738eb42f80bce78d3aef8e307c5750b5a00995c4e46",
        "f3d783b88c9fc99c3c06cbf2d0e540fe69cc923428f37294400a6beb3d3bb589",
    ),
    "steady/fly_in_cascade/wide": (
        "a63ad636b3122f182f490b92cd3cedeba6aeb3dc653c75e0c840c2e600180e90",
        "8d4615bd8a8f8267488e4f32055abc94facf5c38404bb1aa295c5e31b6a05a48",
    ),
    "steady/fly_in_cascade/wide+fast": (
        "f6c30ef4819fea0e4a22a358164ece1844b6c986dea60cf3d7924c11d7748000",
        "2a29a810de1938502c6c9d8c1450f4b7902f587de543129aa538f419c5d908f9",
    ),
    "steady/fly_in_cascade/wide+slow": (
        "c72fc6727de05879a6f05ed5c4d13050013fb237bc5871f182e81cc38bdc5507",
        "ce3a2cd0bbe40c0eb7037219459d5201beb4914ae7a06bbd7f2a7f4c6df79343",
    ),
    "steady/fly_out_cascade/fast": (
        "f0f70efbb9d3ae735531fe9fe0358a8f9956f16f2f05c5db4b77c9dc0a032a58",
        "9bd7bbc96f5edea525cfaaa0b3671dff06056e8f96934baac3128d3c277bc437",
    ),
    "steady/fly_out_cascade/narrow+fast": (
        "5d181d5db5f1570351847fc3b58c2a40cc8de95d8c35b9556db8a11556ed9d60",
        "ea055d37932acdc69bd56640b74050741cfec611d3caffb4e5df24044879f1e1",
    ),
    "steady/fly_out_cascade/narrow+slow": (
        "ffc28bfdd46ddb87e522932fb8d73c5718feb9872a27e49a67898bd6c6278b9b",
        "ac661a02d9502c30de8e04fd79afc6546368a6ce41a0e8a3855007e49ddee553",
    ),
    "steady/fly_out_cascade/wide": (
        "9ef6fab1bbc16949df6a3bc0ca8d670a09a88bea02e032b9fb965d2a626e0f46",
        "5dea8d5716164cafab9c6f2ae54ec7c3854f8737b927936edf50d32059134379",
    ),
    "steady/fly_out_cascade/wide+fast": (
        "0e2e6c53badbd748681c1762a62c4c80e2f77020d8c1535f869ebef3a98cd2d0",
        "9eac67a83c21237ea0d41f09d90d3ce1174c6ba4fd0c237292cbc07e9b5a072a",
    ),
    "steady/fly_out_cascade/wide+slow": (
        "939bfd83a07ea604f77679d5590fc637113e4521021eb9f54ccc2756dee43009",
        "fb9d420703dc0f52f8e319bd479a35063bd40e49fedf2ee61503ed95991251fb",
    ),
    "steady/masked_wheel_flick/fast": (
        "ef982eddeefb7794b28e41a3a287befcc7126d490a981dce079ae878665df4aa",
        "e82432d2c5316dd24833f6459d703aee946e7519bf58f946df24373c9a0db2e9",
    ),
    "steady/masked_wheel_flick/narrow+fast": (
        "2b5bdc157da122113bf9de5e8b0e5b2ed7d1e4145a3cb09ec72dc787275e33b4",
        "63c6c553c067cd8dab2602fd548017803c24076bcf3f7549a022d7dfc9c73436",
    ),
    "steady/masked_wheel_flick/narrow+slow": (
        "dd7835b775245486de247f85ce1ba0fd5aa0e7c68c75f9cca27ce182515ac942",
        "982bff05eba5994eedec53718c022f3e126434825fa025087858e2320024b876",
    ),
    "steady/masked_wheel_flick/wide": (
        "03de910024464aa89a784565b4ed65bb795c8a6c9723fa7428869c1083c8e4b3",
        "fe80354759a79a46b1b35cb901462e17f2693848d5adef051175a83708b32e35",
    ),
    "steady/masked_wheel_flick/wide+fast": (
        "8a48ab1375ccaaeaf0faecca6a46f133dbc4f366b2f21cb210e396a002c1363e",
        "dec3fbafa55e95e2957605f6c7ff2d32b1e21c3225486c8ed89a0b4a6f6c174c",
    ),
    "steady/masked_wheel_flick/wide+slow": (
        "1a3576559d4fcb7b776a64ad60863d933fd8619c0c702cd380ea849f5845a66b",
        "6fc8bfd1a4a336e340b34c323846f611ec217d96912ebcfabc3fe3a057422291",
    ),
    "steady/mirror_wings/fast": (
        "f9e8b8749858f6548506b3a28b81859168a37bcd87bce8f904be1c2226b16805",
        "b04447e6c2f1ee6e28ccd6a41ce4d75bcfc1b4675d8e58a508e8c37b0f5467ab",
    ),
    "steady/mirror_wings/narrow+fast": (
        "de461cd0f1e6dcae6cf265ad1cb6161339d4ba3f6c767bdbc890ec3e1eeede4a",
        "858e7e61fec8a862058908f825f260ef85587958215b86174038e33708f45c34",
    ),
    "steady/mirror_wings/narrow+slow": (
        "2c364c16b72c5297c53dcc7e0db43b76a584c3261d0f93afe02c3268f21c51a9",
        "c9c80c5d0cfce4410311235ba71e84d526dcae441b6f54135cbb56f513a86807",
    ),
    "steady/mirror_wings/wide": (
        "af38bc7c16a8bf4fd31fb5fd56fddc40fd7e028a6dc9e01cebcd2a62a175ad0e",
        "9715d9199effed4b15e204f2f27cf3aec8ebf5c245c3e5b8b5f2ceef2f2117b5",
    ),
    "steady/mirror_wings/wide+fast": (
        "9c8f62f35ced08b3b5a07da576c0bedf99ffde4185c60737441d215f4c1fe2cb",
        "0ef196bb7d93b11450f7a536bdc5f073377ba4533f8d79c5ff2ab6a06c476932",
    ),
    "steady/mirror_wings/wide+slow": (
        "e035a4ce64015c73db5f0cfd0f5c719913c730be6501c8e0d9324566c3a72e59",
        "99431146cf259e92d77022165a8323836dd37c9885d714fcafb95da7e86d7274",
    ),
    "steady/target_orbit/fast": (
        "3331c1b79a3fdcfb24b657a993c482daec30accb76cf8b19fc706d5e2811ebc4",
        "43588bfac383601c9088ef39031958fd8e025b5e847e631def2ab0f1e0e5772e",
    ),
    "steady/target_orbit/narrow+fast": (
        "53bfce3950906659bb64e5dcb8b4c464c80269c1f7925fc60655a484bb5b3035",
        "1308c094876095344e7b83a646161634527d693d0bbffd072694b8ac2bac6ec9",
    ),
    "steady/target_orbit/narrow+slow": (
        "2e4f582d4e239af905777c2be30877e6a787eb51ac8dc56e0f216585c0ccaaae",
        "d241150b19082d05439a15e5450c356734efff2b4b69be935feb1c4eacaeca1c",
    ),
    "steady/target_orbit/wide": (
        "839b5fe51a2749543310e69f37b1bed03d280310b0dccebec5fca768a10c7650",
        "f97441a2cc0a824180f87a72bc39c631079d3fe6a85297d8938a2b79561024e4",
    ),
    "steady/target_orbit/wide+fast": (
        "1de1b7f7b8b78ed0395c82c14996c833fc0605cc3849ccaf106ca003d5c6da7e",
        "31d0923d2ad78ee5cbb7d7d13b000ce03ab70bea35be0b36610d62318a4eec2f",
    ),
    "steady/target_orbit/wide+slow": (
        "e6fe2e5eee0f31f7e80140bbb3e299ef18bbfe020a2517e119f58f39c54a833a",
        "a1773507c0ac1e2e78a45c45bf2b812a6a11d592d8a0a374d5e55bd604cf5aa4",
    ),
    "steady/zoom_wave/fast": (
        "117a8b35830d10d88081ed9c2f06b0e5f96512b820aa5d2a17616a67058a66ee",
        "decd2e1c306dde507b609e631fb0a5113000ca10f54b215128dd27ca088d83c9",
    ),
    "steady/zoom_wave/narrow+fast": (
        "4e4e61097b90b443ab03ed11a5091c22dfd8d1fd9ec1ea45f8506c9b321b6e65",
        "bf283a730211e848435d061c5091566c0cfa10885a0db9154e1a459eb86907af",
    ),
    "steady/zoom_wave/narrow+slow": (
        "fbce069a0362f582cec7ef839ed01cc55fcf1f76c43dc5077251a29f9f7203f9",
        "aeb0df9cfc651c31a1ce6d8dbf26b9c9ebd409e5b20b10f333ea4148b7bee8e6",
    ),
    "steady/zoom_wave/wide": (
        "56867c6cf4f4250b6e0d18df8710b83bf6e2b879d1cbd2af73e522401e2ca5f9",
        "15b4fc9c3700a8fc3bfafa975bd4500d7a01d5564b668a6565057ff5295e1300",
    ),
    "steady/zoom_wave/wide+fast": (
        "d0d76b83b84ff28566f22d4887ff53ca07e7d2a8b1cfa4250f1cf77490ed0384",
        "f8f6fac7d49fd2434e88c82185793d11d43984ca97c1529c7082f03467c2b093",
    ),
    "steady/zoom_wave/wide+slow": (
        "532a68fb02a138588a5583063a6a84269f21d0b76f8a925f62a0f1d793dbad06",
        "f7db8dacdd1e40012fabf8fdf188d11cc159381d49d2c3b4c0e1f4d7877bf6bc",
    ),
    "variable/finite_snap_hold/fast": (
        "d74594c28803d27de11faa42ec18a8ba4a72f1d73ec62a00c6b84ffe8c991311",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow+fast": (
        "5530fd39f6bcd29d9e5f1242e00acf1c676562d40fcc90b79150561ef5ced49d",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/narrow+slow": (
        "b3b913e622aceea93a10947065e5449bc139beb588e3f510c4bdbfaba76c272d",
        "b9c51691943843d96703ad5935a75c5d3db1532f5cf571a576a5f77c68460612",
    ),
    "variable/finite_snap_hold/wide": (
        "580f37a1b37178767de190dd6a49c370e10bef068c5217e9c4c9afeb65ed6c54",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+fast": (
        "381a7decc2ce973a49f086acef0a0dd552361ff6cf43f1bdf2966e65e06da5cc",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+slow": (
        "d330f8dd7f3f7ddbbad37b28992c2df019b3b12b46dc50ad2d071ed08494e5e9",
        "230a61f4658fbe9efa21fbfc2acd10ab752aa33ae469105972e92dbc4ddaccef",
    ),
    "variable/fly_in_cascade/fast": (
        "d25d5d193f0a91d6d29408604ba4b9e0b15d85149599c4efbde3606c24ba8261",
        "270cb0b2b42c0b2ed0728b508ba0d03a491fbac14fe6dd585698a5057285c8f6",
    ),
    "variable/fly_in_cascade/narrow+fast": (
        "5de28e27c8a9e62ab9f6e780d0fba242850883a05f0107b3f16dc72e6db59b74",
        "d04ca61a22765b4e997b2ba55df0b672926e2bbf36225e98e905448f6f3526e5",
    ),
    "variable/fly_in_cascade/narrow+slow": (
        "cba190e6325dd76ef87bf9dbb9e0b2df1afbce9ddf2fb8e75fb7f45184420bf9",
        "cfaa353d2cdb1dede0a7b89aa16994d656281f1275beb55d206f438ba72b2e56",
    ),
    "variable/fly_in_cascade/wide": (
        "e5a9cb90a67d73e2e7eb91e3c07dfe2249aacad2fe86897904cd4b15622dd05c",
        "52ac24a651637610dcef0daac29221b6066598a5b7b4dcb300471f60d1cfcb10",
    ),
    "variable/fly_in_cascade/wide+fast": (
        "4015950730f0f0f3d30271d59ec4330cd5738377eac9cf4a88b292999c448f31",
        "7df58fab43506bab5845c90743ee60ef88fa5c8b950b08fa35dc7cf31c9b4ae8",
    ),
    "variable/fly_in_cascade/wide+slow": (
        "9f5e0860019ca7460fda285d4fd6134a3620460c7aff827207339d6a38fde1b2",
        "ac07ebd59cc17d574998d69c3e821d770ea7887e00b6dec324530aeed2f2b366",
    ),
    "variable/fly_out_cascade/fast": (
        "7234523f0f7a53a42bed5a139a675fd20ba0231e1552e132d4126090dcfcf612",
        "819b97846f0da31760ebc1a5541ded84a2d53945af1c835795fac312bb3f8b7e",
    ),
    "variable/fly_out_cascade/narrow+fast": (
        "df41c7807a9b9b652b97ecb3b47ce0ac320a6f3c16b4fd591cc59718d5c23887",
        "cc3dfd601cae5e3312b7c10c8a3a663e13b2dba186e85d76d6199b627adc244f",
    ),
    "variable/fly_out_cascade/narrow+slow": (
        "2512252900bbb00c4af169deae2ef340c3a3a264c782669cfd14222b94877481",
        "dd5792077b9c4c1d1886dcb96fc5865342d1453f2e5406dba700371a582ad577",
    ),
    "variable/fly_out_cascade/wide": (
        "30e6ba3f8b7a7edf0fc6394aae2e7a11a01b3a8cf5f062ee42927b05d5fbd607",
        "9074c99a5b6e8df580e9305a95fa13b29d8559440b6f70fb65478514b1c75040",
    ),
    "variable/fly_out_cascade/wide+fast": (
        "a544b5fae241a6aaa07ed7e50f36b727d660e5a297b59d90b17de54799b50b74",
        "8b87e9c7b9aefac1611dc66d2a69ad6e4b2344f89e8f5c31baf668a64aeede3e",
    ),
    "variable/fly_out_cascade/wide+slow": (
        "41589127a3e0de58e054d44fd05dbab9a88bc41a7d9c8ef6b8f01cedce21ce5d",
        "2a8894551edf58b38e9cd52fdbe3c9a4acca8eecb1156889072b186cf4671fa1",
    ),
    "variable/masked_wheel_flick/fast": (
        "24bfb3a06f79ba4d6e545516c3fd4188940fc12831fa2918b9e58b6e6912bf20",
        "d8e2e72bd956b89e026ada2c23bb85281000edf3ed1eba36a60d0c0aecf52515",
    ),
    "variable/masked_wheel_flick/narrow+fast": (
        "0d1ecc93bbb308675b5d2300c725a5aa2b2bcd668f9038e495640950bedf240c",
        "c1a3c12f6acd24a15aa1a9ba5d74bd28bee5810ffd3f5e0f3b1559ed2f174dfc",
    ),
    "variable/masked_wheel_flick/narrow+slow": (
        "a085e1158fce0b1e80a30f875049d4e5a8a2386fea8df9d644939acb00933aa7",
        "2558a430925d7ad6d6842e3c9af969bffb27906fdedbd947c0ca9d1b453e0fc2",
    ),
    "variable/masked_wheel_flick/wide": (
        "766d1c60a3c62a9fa4f5e0a734d197e536fb54afc935ec8c5c6c812ab619ed0d",
        "535e039c6c26d6f78ab95f01c1aaac2c5fb26afec1e94cd2418fc546449cb7f9",
    ),
    "variable/masked_wheel_flick/wide+fast": (
        "405d62ccf1aa0cfd9dff46e3bae4212adbad7d59bd17d5b029b76233ac442c13",
        "346cfecaf2cb0c70ec1ec1cc0e73130a509ef456f106ee2cf0129a68af1dd906",
    ),
    "variable/masked_wheel_flick/wide+slow": (
        "12b0dcfdc713b5a1adfba0be0d2ed0c43153b4ef53ada5184c522c0493fc1810",
        "2e85d5e91e07f289299a27c49b9431ddb807008575a1309bc51bd627489f48d7",
    ),
    "variable/mirror_wings/fast": (
        "851a75a9916951321b9f739987e19c7cf6e695f9738ddde4d7a6f788791881b9",
        "97dfa43672eb9ff20f2499d975f7711f18f97076aac6e263b66ce50dc6a39014",
    ),
    "variable/mirror_wings/narrow+fast": (
        "d8e651b4f3f225a679187e859a938e3472dd5ad93f08fb7a574c2705097edc61",
        "788bb43aad21501da2d566fb34d09de7f8d69ff7a3103ed6a857c7576a11ad1e",
    ),
    "variable/mirror_wings/narrow+slow": (
        "128391c51a26dc44217a30ed2864d5179f6b157b72dab47f48c5af0b96b771d0",
        "0a557bade4807bf080b296be1a3fe68625c154163ffeeff55f3137fdb64d970a",
    ),
    "variable/mirror_wings/wide": (
        "8767c18edd7dc94bce9d4dd1f24e0fe3469551c39b07f0aaf42f6ebecde32e03",
        "cc1afd21c39ab3aed598b1d7f469200f0c8cfff2a9a1441a3147a8b72ee10286",
    ),
    "variable/mirror_wings/wide+fast": (
        "102ff0371f6162e00555fb4a0e9522696d6703f9fe3e41bf74819e9e517470dc",
        "19c35fa78f034db31d16242220fd0d6009008896b3ca2b11e462d6448b277152",
    ),
    "variable/mirror_wings/wide+slow": (
        "15b2919ee68028d2efbcbc860fb77c34db5e925c511912fb03cf6117b25212b7",
        "d42e353647063d8e8ad3c4936fcbbd5e3c21a242ecff2363dfdf13dd776b50c1",
    ),
    "variable/target_orbit/fast": (
        "383a1a8ba39b9c3d832349efcaa3c869366ae70b5f56005c93b74cc733b925e0",
        "7f4ca6832f012f0540590242a81b24d1f94a762d0bc68e84c0260edaf9ebb3a7",
    ),
    "variable/target_orbit/narrow+fast": (
        "1c3b99070a334c93d2423c260398f1ef95755a1c6a791f35621e1c3f257972f6",
        "96e54669a020381c11c0b080af9364f6e61101f3150eb47121b92e32d83c0e88",
    ),
    "variable/target_orbit/narrow+slow": (
        "9520f0b4db3f3a41c3c4d022a5915897435906a89c2d4d65fb487ea9729afa34",
        "c76a442fcfab75c97fe5b7a9369922c33b4227b1df12cb88fbc2ed10e406a12b",
    ),
    "variable/target_orbit/wide": (
        "7c536aa9796515b096862ce5b3cd99d45dfc254f7fc728e71cfb6da2b3ade9c9",
        "7e7221916d9f8fbf90b3f66e11b9a5b0d4f3545944923b916fa6c341e0b13134",
    ),
    "variable/target_orbit/wide+fast": (
        "6a6b2ca1fb53443657a37be0a022c4065491888254f97e775b8ffaf4eff45a5b",
        "da81376c87f194cf1e7249511f0788411854efc51526f87f923dbac9c9ebf193",
    ),
    "variable/target_orbit/wide+slow": (
        "9f0d46391d1ec8889327a166ff3b63d40b43714e1016c314ae77817efc1e5728",
        "42ea5df862fc884a4442023a9b798ed5d367d0dd85db6492817d0733292ee9f6",
    ),
    "variable/zoom_wave/fast": (
        "d25365f6b2513340671de90c4fd0ee71229232e1be8474f5530d6fbfffc1410c",
        "fb4a81f1a672cf767191b3a674323caa60ac7c4ab08d4ef138dbe410a91d0bad",
    ),
    "variable/zoom_wave/narrow+fast": (
        "c4fde8ff82014782c83653882393670b95d70d9a2628eaf07cdc66eb4afff2bb",
        "4667c2393e6bde7ba73ccc8427d6501ddf975f675d4af3e065322ad18f2640ca",
    ),
    "variable/zoom_wave/narrow+slow": (
        "1ca8c6356605b645e9534a59433b6cec154f6cd60e7572b4e3330d835e21f01e",
        "e35eec0d1c0b3554429c7b42e71740016941caff8cb3513d68973c55a583df52",
    ),
    "variable/zoom_wave/wide": (
        "8fcfeb7536849e3156f27c0511095c04ce67e9efa3a9421ab6ce5dfcf72cf025",
        "d1df17aa71942784b4715d6038237f6e5e36cadde3cfd06f39731140b8d90e9d",
    ),
    "variable/zoom_wave/wide+fast": (
        "d6df2466d5652344717ff0d61619fd8ffc52e91317b3e674d218045af142f2b5",
        "34eef86923bb6fa37a5ab762cf1375a203ad0bb931dcc75d94e72af86477945e",
    ),
    "variable/zoom_wave/wide+slow": (
        "6d135a65df5d0cb0814f277795d083a081aabd200684c6194fa3a36820dde982",
        "f16960235d17895270e5fd05bd8b0bd6ab2abd81292bec177b0a68cf9443764b",
    ),
}
"""`grid/template/variant`: (render fingerprint, SHA-256 of the encoded frames)."""

MULTI_PIN = (
    "db4378f098f8a8306e9a1dd692cf2cdc59bbd9ce142f164d32f5d5367188b5b2",
    "3ea6b3fca42f7ea4bbed6068c580331ce3649c6ef4c49f77f7b23fff7599fba7",
    "9ef5b7a162ca49079bb1a5261223b9ebcd399f8b7bb48463942ba4271861c6fb",
)
"""The multi-section plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256)."""

MULTI_SECTIONS = ("mirror_wings", "target_orbit", "finite_snap_hold", "fly_in_cascade")

GATED_PIN = (
    "79daf7105e509db36f6449b2ce58f33ad6272f2fcf5e39f34b58720241d1a454",
    "b971080b47c7c7b20e2466c76bfa187b6bb1872a5ec4ac6c316b9d0c614c96bd",
    "7f2d1e3bf22d121835f2c586bdea34718958dc234d6c2577fed66900fc4be14d",
)
"""The gated plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256). The
frames and `.xsq` hashes were rendered from `mh-last-with-legacy-renderer` (its job
carrying `mode: physical_v2`); the fingerprint is this tree's (re-recorded in C1.3, C1.4,
W2, W4 and its fix round)."""

GATED_ADMISSION = TemplateAdmission(
    admitted=("mirror_wings", "target_orbit", "fly_in_cascade", "finite_snap_hold"),
    admitted_presets={
        "mirror_wings": ("slow",),
        "target_orbit": ("narrow", "slow"),
        "fly_in_cascade": ("narrow", "slow"),
        "finite_snap_hold": ("narrow", "slow"),
    },
    effective_preset={
        "mirror_wings": "slow",
        "target_orbit": "narrow",
        "fly_in_cascade": None,
        "finite_snap_hold": None,
    },
    exclusions=(),
    preset_exclusions=(
        {"template_id": "mirror_wings", "preset_id": "narrow", "reason": "pinned exclusion"},
    ),
    entry_dips={},
    offer=m.untagged_offer(),
)
"""A gate result in which `mirror_wings`' `narrow` is not admitted and two templates
play a preset as their effective variant."""


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def _grid(name: str) -> BeatGrid:
    if name == "steady":
        return m.bars_grid(*([500.0] * 8))
    rng = random.Random(11)
    return m.bars_grid(*[rng.choice([430.0, 500.0, 580.0]) for _ in range(8)])


def _frames_sha256(frames: Sequence[EncodedFixtureFrame]) -> str:
    payload = [[f.fixture_id, f.time_ms, [list(c) for c in f.channels]] for f in frames]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def _render(
    sections: Sequence[tuple[str, int, int]],
    preset: str | None,
    grid: BeatGrid,
    output_path: Path | None = None,
) -> RenderingPipeline:
    zoom = any(template_id == "zoom_wave" for template_id, _, _ in sections)
    plan = m.sections_plan(*sections)
    if preset is not None:
        plan = plan.model_copy(
            update={"sections": [m.with_preset(s, preset) for s in plan.sections]}
        )
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=grid,
        fixture_group=(m.zoom_rig if zoom else m.family_rig)(HEADS),
        job_config=(m.zoom_job if zoom else m.family_job)(HEADS),
        output_path=output_path,
        media_file="silence.wav",
    )
    pipeline.render()
    return pipeline


def test_every_family_variant_is_pinned_on_both_grids() -> None:
    expected = {
        f"{grid}/{template_id}/{preset or 'base'}"
        for grid in ("steady", "variable")
        for template_id in m.CATALOG_IDS
        for preset in (None, *(p.preset_id for p in get_template(template_id).presets))
    }
    assert set(PINS) == expected


@pytest.mark.parametrize("case", sorted(PINS))
def test_family_variant_output_is_pinned(case: str) -> None:
    grid, template_id, variant = case.split("/")
    pipeline = _render([(template_id, 1, 8)], None if variant == "base" else variant, _grid(grid))

    assert (pipeline.fingerprint(), _frames_sha256(pipeline.frames)) == PINS[case]


def test_multi_section_output_and_delivered_xsq_are_pinned(tmp_path: Path) -> None:
    output_path = tmp_path / "song.xsq"
    pipeline = _render(
        [(template_id, 2 * i + 1, 2 * i + 2) for i, template_id in enumerate(MULTI_SECTIONS)],
        None,
        _grid("variable"),
        output_path,
    )

    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == MULTI_PIN


def test_gated_render_with_dark_spans_and_a_fallback_is_pinned(tmp_path: Path) -> None:
    """A render under a gate result, over a dark span, with `reposition_fallback` set: a
    section naming a preset the gate left out, and one naming none, play their
    template's effective variant."""
    output_path = tmp_path / "song.xsq"
    plan = m.sections_plan(
        ("mirror_wings", 1, 2),
        ("target_orbit", 3, 4),
        ("fly_in_cascade", 5, 6),
        ("finite_snap_hold", 7, 8),
    )
    plan = plan.model_copy(
        update={
            "sections": [
                m.with_preset(plan.sections[0], "narrow"),
                *plan.sections[1:],
            ]
        }
    )
    job = m.family_job(HEADS)
    job = job.model_copy(
        update={
            "moving_heads": job.moving_heads.model_copy(
                update={"reposition_fallback": "preserve_aim"}
            )
        }
    )
    pipeline = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=_grid("variable"),
        fixture_group=m.family_rig(HEADS),
        job_config=job,
        output_path=output_path,
        media_file="silence.wav",
        admission=GATED_ADMISSION,
        dark_spans=((6000, 7500),),
    )
    pipeline.render()

    assert pipeline.render_record is not None
    assert pipeline.render_record["admission_effective_presets"] == {
        "mirror_wings": "slow",
        "target_orbit": "narrow",
    }
    assert pipeline.render_record["dark_spans"] == [[6000, 7500]]
    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == GATED_PIN


INTENT_PIN = (
    "9da35b439faf79a4d2444785f571fbe480a5c9e00f0236153fc9572000fdf6ee",
    "ad91f4f2da8e0fc5bca0e07a7a9d9003d7880d59dee2499b30389be403e36d3b",
    "9968e9a4b0d5892d7891177fbdab9a0dca7d300d09998a946a5b908a51c17c46",
)
"""The song-intent plan on a tagged rig: (render fingerprint, frames SHA-256, delivered
`.xsq` SHA-256). Recorded in W4 (2026-11-17), when a section's colour and gobo started to
render; no earlier tree renders them, so these guard the new behaviour from here on."""


def test_section_colour_and_gobo_on_a_tagged_rig_are_pinned(tmp_path: Path) -> None:
    """Four sections on the steady grid and the tagged family rig: an explicit colour, a
    colour and a gobo, a palette role through a supplied macro palette over the overlay
    family, and an as-authored section after it; colour changes at lit boundaries dip
    dark before the section, where one fits."""
    output_path = tmp_path / "song.xsq"
    sections = [
        m.plan_section("s1", 1, 2, "mirror_wings", color="red"),
        m.plan_section("s2", 3, 4, "finite_snap_hold", color="blue", gobo="stars"),
        m.plan_section("s3", 5, 6, "masked_wheel_flick", color="PALETTE_PRIMARY"),
        m.plan_section("s4", 7, 8, "mirror_wings"),
    ]
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=_grid("steady"),
        fixture_group=m.tagged_family_rig(HEADS),
        job_config=m.family_job(HEADS),
        output_path=output_path,
        media_file="silence.wav",
        palettes={"s3": section_palettes_of("spec.cosmic_night")},
    )
    pipeline.render()

    assert pipeline.render_record is not None
    assert [look["section_id"] for look in pipeline.render_record["section_looks"]] == [
        "s1",
        "s2",
        "s3",
        "s4",
    ]
    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == INTENT_PIN


def section_palettes_of(palette_id: str) -> SectionPalette:
    return SectionPalette(
        palette_id=palette_id,
        stops=tuple(stop.hex[:7].upper() for stop in get_palette(palette_id).stops),
    )


FAST_INTENT_PIN = (
    "84f4496c0103153c44de995ab847b3b919457343afddd3c26edb122fe99bad0f",
    "2785d278f4341c611a0aaf60b9e22ee2e6e1accc8f70252442f7402bfd308a54",
)
"""The fast song-intent plan: (render fingerprint, frames SHA-256). Recorded in the W3/W4
review fix round, when a colour change that cannot dip before a lit boundary started to
turn in the section's first dark window, or else to keep the previous colour."""


def test_colour_changes_that_cannot_dip_at_170_bpm_are_pinned() -> None:
    """170 BPM on owner-like timings (close latency 20 ms, every wheel state settling in
    150 ms: a 180 ms change, more than half a beat): red, then blue over the overlay
    family (turned in its first mask), then red over `mirror_wings` (no dark moment: the
    heads keep blue), then white over `finite_snap_hold` (it enters dark, so the wheel
    turns in its entry and no boundary is recorded)."""
    payload = m.tagged_family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        profile["visibility"]["close_latency_ms"] = 20
        for channel in ("color", "gobo"):
            for state in profile["discrete"][channel]["states"].values():
                state["settle_ms"] = 150
    sections = [
        m.plan_section("s1", 1, 4, "mirror_wings", color="red"),
        m.plan_section("s2", 5, 8, "masked_wheel_flick", color="blue"),
        m.plan_section("s3", 9, 12, "mirror_wings", color="red"),
        m.plan_section("s4", 13, 16, "finite_snap_hold", color="white"),
    ]
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=m.bars_grid(*([60_000 / 170] * 16)),
        fixture_group=FixtureGroup.model_validate(payload),
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
    )
    pipeline.render()

    assert pipeline.render_record is not None
    outcomes = [
        sorted(
            {
                next(k for k in ("dark_dip", "deferred", "kept_previous") if k in b)
                for b in look.get("boundaries", [])
            }
        )
        for look in pipeline.render_record["section_looks"]
    ]
    assert outcomes == [[], ["deferred"], ["kept_previous"], []]
    assert (pipeline.fingerprint(), _frames_sha256(pipeline.frames)) == FAST_INTENT_PIN


INTENSITY_PINS: dict[str, tuple[str, str]] = {
    "full/mirror_wings/INTENSE": (
        "2938b502f25d50426807a6d1fbd56b877f4595c1b3e65d44711ccb031b441faf",
        "448dd5edb8649aa4e4a1d31725c6de92a9e1d8d3be740297a0de11dd76a8c57a",
    ),
    "headroom/intensity_half_hold/DRAMATIC": (
        "09cd8d5d75b41b0f55a7f43dc1a827ff9c019c38e0771d4fb12beaffd7da7678",
        "13d0f907cfcf370c2e250c959632c3a7ce26d446b11afad12082f1748bc10e0d",
    ),
    "authored_pulse/intensity_authored_pulse/INTENSE": (
        "ee530128f5565e76ffdae7a19094482762d53d965a745a3c36c59515fa4b120e",
        "906a48806b8986bd1c2d0d72401d9838a2f46d5b910df9aed6064b169ba28ceb",
    ),
}
"""`shape/template/intensity`: (render fingerprint, frames SHA-256) of one 8-bar section
on the steady grid. Recorded in W5 (2026-11-17), when DRAMATIC and INTENSE started to play
on the dimmer: a dip-and-return on a family that holds the dimmer full, a pulse over a
held half level, and an accent on a template's own 0.3/0.8 pulse. The W5 review fix round
re-recorded the latter two's frames: the half level's first lit run after its entry window
now starts on an accent, and the 0.3/0.8 pulse's gains are capped so its peak reaches full
(the full family's frames are unchanged)."""


@pytest.mark.parametrize("case", sorted(INTENSITY_PINS))
def test_intensity_on_each_kind_of_authored_level_is_pinned(case: str) -> None:
    _, template_id, intensity = case.split("/")
    half = m.hold_step(
        "hold", 10.0, dimmer={"period_beats": 4.0, "duty_cycle": 1.0, "low": 0.0, "high": 0.5}
    )
    pulse = m.hold_step(
        "pulse", 10.0, dimmer={"period_beats": 2.0, "duty_cycle": 0.5, "low": 0.3, "high": 0.8}
    )
    with m.registered_templates(
        m.loop_template_doc("intensity_half_hold", [half]),
        m.loop_template_doc("intensity_authored_pulse", [pulse]),
    ):
        pipeline = RenderingPipeline(
            choreography_plan=ChoreographyPlan(
                sections=[m.plan_section("s1", 1, 8, template_id, intensity=intensity)],
                overall_strategy="",
            ),
            beat_grid=_grid("steady"),
            fixture_group=m.family_rig(HEADS),
            job_config=m.family_job(HEADS),
            media_file="silence.wav",
        )
        pipeline.render()
        assert (pipeline.fingerprint(), _frames_sha256(pipeline.frames)) == INTENSITY_PINS[case]


EVENT_PINS: dict[str, tuple[str, str, str]] = {
    "dimmer_strobe": (
        "bc9a51a262728b8646b05be3028a14f70232cbb33f7656b60547e93f80a37730",
        "325f3945dfca1082d2d52dda9e22aad57330cd50c15123fc97663683dfc89358",
        "2607e56ef3f1883d9da4c136e05dcfbf9ce3fc8ee46480c0fc75edf6aa623a9d",
    ),
    "tagged_strobe": (
        "0c302eebd029099556b8d661f7bd3f6f357d4f50be618a06b67708e62476c62d",
        "19c59ccc365752f6dc6ce5ca9da155f4071daa723d22bf75f71d4f6d9fdb3ebb",
        "31b093ee23b354df754e7c78f863148b9f3d446ec53dbebc833e1c2d423c798a",
    ),
}
"""`rig`: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256) of the event-rich
plan (`test_events_on_a_tagged_rig_are_pinned`) on the tagged family rig without strobe
states (the strobe plays on the dimmer) and with a state tagged for each speed (the
fixture strobes itself). Recorded in W6/W7 (2026-11-17), when the plan's events started
to play; no earlier tree renders them, so these guard the new behaviour from here on."""


def _event(bar: int, beat: int, action: str, **fields: object) -> dict[str, object]:
    return {
        "bar": bar,
        "beat": beat,
        "moment_cue_id": None,
        "action": action,
        "color": None,
        "gobo": None,
        **fields,
    }


@pytest.mark.parametrize("case", sorted(EVENT_PINS))
def test_events_on_a_tagged_rig_are_pinned(case: str, tmp_path: Path) -> None:
    """Two sections on the steady grid: over `mirror_wings` a hit bound to a HIGH lyric
    cue, a colour event, a gobo event, a fast strobe ended by `open`; over
    `masked_wheel_flick` at INTENSE a hit, a pulse and a closed event the section ends
    in."""
    payload = m.tagged_family_rig(HEADS).model_dump(mode="json")
    if case == "tagged_strobe":
        for fixture in payload["fixtures"]:
            states = fixture["config"]["physical_profile"]["discrete"]["shutter"]["states"]
            for speed, low in (("slow", 100), ("medium", 140), ("fast", 180)):
                states[f"strobe_{speed}"] = {
                    "range_min": low,
                    "range_max": low + 39,
                    "value": low + 10,
                    "settle_ms": 0,
                    "strobe": speed,
                }
    output_path = tmp_path / "song.xsq"
    sections = [
        m.plan_section(
            "s1",
            1,
            4,
            "mirror_wings",
            moment_cues=["hook"],
            events=[
                _event(1, 3, "hit", moment_cue_id="hook", cue_emphasis="HIGH"),
                _event(2, 1, "color", color="red"),
                _event(2, 3, "gobo", gobo="dots"),
                _event(3, 1, "strobe_fast"),
                _event(3, 3, "open"),
            ],
        ),
        m.plan_section(
            "s2",
            5,
            8,
            "masked_wheel_flick",
            intensity="INTENSE",
            events=[_event(6, 1, "hit"), _event(7, 1, "pulse"), _event(8, 1, "closed")],
        ),
    ]
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=_grid("steady"),
        fixture_group=FixtureGroup.model_validate(payload),
        job_config=m.family_job(HEADS),
        output_path=output_path,
        media_file="silence.wav",
    )
    pipeline.render()

    assert pipeline.render_record is not None
    assert [len(look["events"]) for look in pipeline.render_record["section_looks"]] == [5, 3]
    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == EVENT_PINS[case]


TRANSITION_PINS: dict[str, tuple[str, str, str]] = {
    "dark": (
        "c4a903739d65cb25f295c472d01c01db3de02f576f933a5a035c061ff35e4c89",
        "48a5bc7d737f3495c8cbf9a50fa9e29cad900a814d499da01e4bbca09787c371",
        "5650779eacdca88b2594039ce5888d1cb86d78916501f81793329ff24b02af54",
    ),
    "lit": (
        "2068d7b625608ee93ac71b30660dfa5cd132ae3bc62f0080e9cb0f642afd1001",
        "7ada8aa1cf9d7e77d8f7d9cf300d9ba37de0db12c883e25ea891e9de00829d03",
        "4d923c860e185b0be8c686c219339aa26ba59323e5ef828a6a45a86ade852ac0",
    ),
}
"""`case`: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256) of the
transition plan (`test_transitions_on_a_tagged_rig_are_pinned`): the lit modes on the
steady grid, the dark modes on the variable one. Recorded in W8 (2026-11-17), when the
plan's transitions started to play; no earlier tree renders them, so these guard the new
behaviour from here on."""


def _transition(edge: str, mode: str, length: str, **fields: object) -> dict[str, object]:
    return {
        "edge": edge,
        "mode": mode,
        "length": length,
        "curve": "linear",
        "split": "HALF",
        "channels": [],
        **fields,
    }


@pytest.mark.parametrize("case", sorted(TRANSITION_PINS))
def test_transitions_on_a_tagged_rig_are_pinned(case: str, tmp_path: Path) -> None:
    """Four two-bar sections, each with an ENTRY and the last with an EXIT, across a colour
    change (red into blue) and a gobo change: `lit` plays crossfade, morph, sweep (one with
    a per-channel dimmer crossfade) and a closing morph; `dark` plays snap, fade_via_black,
    blackout (one with a shutter `sequence`) and a closing fade_via_black."""
    lit = case == "lit"
    modes = (
        ("crossfade", "morph", "sweep", "crossfade", "morph")
        if lit
        else ("fade_via_black", "snap", "blackout", "fade_via_black", "fade_via_black")
    )
    output_path = tmp_path / "song.xsq"
    sections = [
        m.plan_section(
            "s1",
            1,
            2,
            "finite_snap_hold",
            color="red",
            transitions=[_transition("ENTRY", modes[0], "HALF_BAR")],
        ),
        m.plan_section(
            "s2",
            3,
            4,
            "mirror_wings",
            color="blue",
            transitions=[
                _transition("ENTRY", modes[1], "BAR", curve="ease_in_out_sine", split="THIRD")
            ],
        ),
        m.plan_section(
            "s3",
            5,
            6,
            "masked_wheel_flick",
            gobo="dots",
            transitions=[
                _transition(
                    "ENTRY",
                    modes[2],
                    "BAR",
                    curve="ease_out_quad",
                    channels=[
                        {"channel": "dimmer", "strategy": "crossfade" if lit else "sequence"}
                    ],
                )
            ],
        ),
        m.plan_section(
            "s4",
            7,
            8,
            "target_orbit",
            transitions=[
                _transition("ENTRY", modes[3], "HALF_BAR", split="QUARTER"),
                _transition("EXIT", modes[4], "BAR"),
            ],
        ),
    ]
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=_grid("steady" if lit else "variable"),
        fixture_group=m.tagged_family_rig(HEADS),
        job_config=m.family_job(HEADS),
        output_path=output_path,
        media_file="silence.wav",
    )
    pipeline.render()

    assert pipeline.render_record is not None
    traced = [
        t["mode"]
        for look in pipeline.render_record["section_looks"]
        for t in look.get("transitions", [])
    ]
    assert traced == list(modes)
    assert (
        pipeline.fingerprint(),
        _frames_sha256(pipeline.frames),
        hashlib.sha256(output_path.read_bytes()).hexdigest(),
    ) == TRANSITION_PINS[case]
