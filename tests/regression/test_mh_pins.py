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
An intended
output change bumps `RENDERER_REVISION` and re-records these pins in the same commit,
saying why.
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
        "61ebb5c8f5c1c2f0923a25470e4e43f85f42186323410285b7b13e001940d5a5",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow": (
        "2ba0f94a4c0b6de575e518b569e357dcd28cf5a9fab0ba3e5db27a2f2d352fa5",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/slow": (
        "d8ed0d51b4b538583466183b26e197cd33f6ee1d7086712910f5651e5400f472",
        "4d455965979b705ad9af8136e4fd229c7b5374635e1786d07b8cab7636861b9d",
    ),
    "steady/fly_in_cascade/base": (
        "c5a9653a61936ec97c0963beb9118650619e6df763f0d71f671b0bdae122f388",
        "ffdfb044c11edf3040dd81744d17558a2d46c21181071367cca5f752a8413b0d",
    ),
    "steady/fly_in_cascade/narrow": (
        "8d382475a2b46003d60358873f7e04550444c028e41d571f8d2d4c04ea5102fe",
        "0280d85aaf1e832fc23b428e311b24ccb67dac720116f25f71d147261f88f310",
    ),
    "steady/fly_in_cascade/slow": (
        "0a54e6161dea38eebe4d8c1f98e4ea53172f3e850e5e9bcb5c20511b86ac2cde",
        "dd49563a5956e1e52f4a2c01e8f005a64a297ff28f9155f3eb05d10a29312433",
    ),
    "steady/fly_out_cascade/base": (
        "41a72a29f8438a9ab8dbde9f924f8df0aa29efd37cc0a91f7f0fadc023d2e2be",
        "4235e01012dddfdae05f050fa904a9efa2e8eb4cf4f3b7e2ddd06b23951c733e",
    ),
    "steady/fly_out_cascade/narrow": (
        "f06f315ca9556b9b42a01cdce66d2c2c66b55df9f158b090db8281dadead5013",
        "150edd82e9273731bd9ab781ab5c6caf420cf5d1129cddb637915687dab01a88",
    ),
    "steady/fly_out_cascade/slow": (
        "8baee1eef2e8ec10d79035c00ccc08fbffe43e5cf2c9d105d1517c0812584e94",
        "c7e91342cab3b42a868f59ab824961da433ac89db0c5646f1fd41e29b0444a70",
    ),
    "steady/masked_wheel_flick/base": (
        "f31909f9fb0ac494a49f2d257abab9e5f8fea2a4a9c28d930b63af10c08f71f6",
        "08ce9090980dbfefa79b6d78c90ef0f0b0c8ef3a19bb47d193d9af34805cd2de",
    ),
    "steady/masked_wheel_flick/narrow": (
        "14f78958265b970e5e5e6ab4ad4810548cfff31664519ac7f8c72312badd0bfe",
        "2537e7e6cf39dad19aadb07a271b223f83c2af7fbbe52b4732f6416cee5993ad",
    ),
    "steady/masked_wheel_flick/slow": (
        "a14c8ac4d8de3c5adf2af997bbf6cf41668eb3c83ca9c90fdbc40a64911c20e6",
        "56a758e57a37773c558bff6f8134843cf45c76d005021a6e882374d16d96431a",
    ),
    "steady/mirror_wings/base": (
        "15f5bf98cf782c386697a7357dd5ae0d6cd903c2e889f1acedf89bdc7fc4a3b2",
        "8e3cb9be3de61f968b065d8d0442ac5551becdbbf4624afb76b13a58e0f000fd",
    ),
    "steady/mirror_wings/narrow": (
        "3bb6417f0d1651b684ef36284203b40726383df25fa8824d5795fa5c89d60b82",
        "d83a23f4fea33e3e6f1b2bbfabdc0b5c26f605b673861c0021a1cc1c8bd36a1b",
    ),
    "steady/mirror_wings/slow": (
        "869fac36887a72338277fdd69af4fc2ac132b65dadeb335eecb947baf69be350",
        "bbcdbab3564fa3d0a7f107562326940ef92fa3f38130a37ac9d8b43f68bdd3b6",
    ),
    "steady/target_orbit/base": (
        "a57df717bb910b9bfc36ecb53f1bde09df6435bc015e76589c4a87bc6e85e170",
        "78d35ed327d359ca0cc456a151ae19f800a20b80ac1cc040ea4448be4d014ed1",
    ),
    "steady/target_orbit/narrow": (
        "e09629f45697ec6f516e4d082fbc26fe11f98558cbff78ee1ec0658b5951d40e",
        "a35e080540356862ecfe8738414c7cef0d781b639b869db97bc27ff0db5f180b",
    ),
    "steady/target_orbit/slow": (
        "b1d806b048e4f9f79fb6a95cdda813849f039d670cb0beb98b87c3d2dcafab01",
        "a2eb0bf1f4d04307af57da96941f9d02e8c47ffcc583db3361b0a754975c7d36",
    ),
    "steady/zoom_wave/base": (
        "7951e8a3f940e04071162a93c30586d2451d60f90baf569103e0e14d70fb880c",
        "bfa3f5ef5efd80d8f801f76ab412044d35161bb606288fc35f6fbeaf6970675a",
    ),
    "steady/zoom_wave/narrow": (
        "817ad75bb6687d34bb8f1c7d437d098b0462bd20f90de6266aa25e5fba48f716",
        "0ddc62b56b92e1af2deedbc6b9bf47570bbe82663ff559091f3883f32e20169b",
    ),
    "steady/zoom_wave/slow": (
        "5d926bd28a979664ea2b38741d97949ef75efda1923c93af0e6faabe67beaf52",
        "394aa7ae9fb0cc8e948e2c1b68264b9652edbddd44bcefd9d5ac0dea8e5cdb2c",
    ),
    "variable/finite_snap_hold/base": (
        "aa869353a6d86a4588027ca29890b3a3457507b757f64a6e2b7ead81fde7c212",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow": (
        "f18fe0cb6e1cc5972725dd48df05833e26a23f69617cc023b7ab62593d962186",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/slow": (
        "eb4b1e9135a3fc6fa9033836eaec9597bf0b3e476f26e066c45136e8994159c3",
        "e4f7f3d9a0863c4f423dae91e481e8874d5971308aa2196a93e6fca84a6d8930",
    ),
    "variable/fly_in_cascade/base": (
        "7a906b9ce84c50b2b03b8d30de4abf18cdaaf51c939e0dce0179d6ddfb189763",
        "34f9987fa593584b7894352d13944905315dd6c260035971de447db3c121fd7a",
    ),
    "variable/fly_in_cascade/narrow": (
        "b23a3bebc98e31d27b40162b93e5f2717fc0eca684ab1591d4e249a8ffca0bc3",
        "f2d02f0c7cdbcda887bcd350188338a8bfe0ae583b2b5e092c64b921985f1a9e",
    ),
    "variable/fly_in_cascade/slow": (
        "e7a0d74fa06f49660a1965a5c807616ceba1e8c259e3217e656a5e2fd752e4e5",
        "49c484a8585d159fc61d0989eef1cc2a35fc22a5e46cf202f789736c8dd37ebe",
    ),
    "variable/fly_out_cascade/base": (
        "fc33608597ee5973e63f332e95ee2ea67315385d5c16a314986ebe0680919a9c",
        "36f29b21188085c76c462a8cfd73f3e10f21f7adfdbca525a674c4960aca28d2",
    ),
    "variable/fly_out_cascade/narrow": (
        "18dbd2b8d4fd7c7be85f41ff5e028a6fd13f2bfc4991f64f62dde2b66c19be3e",
        "c773f3be51097dd3ec2c309f6149f76e6c3bb7f6d1ea24416aba4662a10cb420",
    ),
    "variable/fly_out_cascade/slow": (
        "705b72da1e4b5c1b521f8f781b60ef46ea78cf91a54714341abeb35ca74c4e8c",
        "de6e5fb69f6beeeb43df051367101bd88d3d75b61e811bab2ac3e69d2edd499a",
    ),
    "variable/masked_wheel_flick/base": (
        "93ee0cd0bba9514b9290bbb9f0fe7957e7ef31b0aebb7e719838dba0cd86a078",
        "a628fb0ca672aba2a7c36e3ecfafcf1003b8d9c8a06adc5edcf0840004981f3f",
    ),
    "variable/masked_wheel_flick/narrow": (
        "0515a4553450662456462881a1eed6c358d3b1698c102fac834aec2604237fd3",
        "a8b2c6b2cf905f657c6993dca020c6aa14bbfacc10f89bfb97491860bc81a6c3",
    ),
    "variable/masked_wheel_flick/slow": (
        "b4687aef047bc8bdf960065aebc1274bd00d54c5feb5c67552fa9989e6927a5d",
        "058ed1d9cbdde981fa5213dd23654d42fc86a9ebd6150fc50b089e07f85825f8",
    ),
    "variable/mirror_wings/base": (
        "e70a0b2dfeb4bb3f5250d864a95429437fe1cac8adc11636b143ef1791e79893",
        "a59b343515d159c1603c1a0ed576afa3b6721178a643ad1c5fbc02d6bb706dde",
    ),
    "variable/mirror_wings/narrow": (
        "3dea749822ae3db7cc2d0e17b3388eb3151abfc3423290468b4ae2df937360c8",
        "4d326471bc6af0e6f429bd8e5d5b7e374587d3f545a2fe3d2ad3ef908ab6f801",
    ),
    "variable/mirror_wings/slow": (
        "021c77c21ace2ab2bb391bf18898e5d546eb8dc64b01f0b041ab15f7f63a0408",
        "cee179ea21422e5e6f268664dd79981055afedfd98c5849c5dbfd44f5b80904e",
    ),
    "variable/target_orbit/base": (
        "bce079fdabe6f8126a00fe8a0af4fd0833dea9b36e1b0b8a27e21d7c7b841f4e",
        "2bfe8b5bd75f0097dd6fb8011e38a11578764984050474ddf0ee402ae3c85fa1",
    ),
    "variable/target_orbit/narrow": (
        "f4d500387ce9625f43b97791c3381f322d11528fb6c70a95d563eaabc1c1e5e3",
        "9f453dce2badb89d745c808896a8fe6d3b9feafacf5d122371d75d0a6377b4a6",
    ),
    "variable/target_orbit/slow": (
        "3c796bafcf7224daa03d9de36108e1f8d5af36aad1a450f4764c2752195ba555",
        "ac930585ef5e3f15f79cc7267d407f586e99f71923c67b287415b69ec32365c5",
    ),
    "variable/zoom_wave/base": (
        "d4532f357ed33efb83dca824440f8ebae1287934409fe47b7c2e3ed2fcb06b69",
        "0020b12393f7dd4cf89bb4c4bbf3cd942ed5aa0de2abde665b3caffefdc751a7",
    ),
    "variable/zoom_wave/narrow": (
        "48f64c02fc32d9245ea9d5cff6bc2ad4c586ab74c0775079cb7c5d68a348718e",
        "a39df6ddbe83086edd4664152946711a1b5a24a927837fd366218594215ce44a",
    ),
    "variable/zoom_wave/slow": (
        "c94d754f078a570f2753da0206b4e467e13fedc250ac926b0a8dfab53523beaa",
        "503a36b0d6d9b85cfa6e5518367e787f835571fbc02f9f44e09f96f2c6689561",
    ),
    "steady/finite_snap_hold/fast": (
        "27418af429db3e1e5d9e7a2e2759baee988d8320c77c4f9589ffc450feaa16ba",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow+fast": (
        "1eeda4c301f02316251e0aa10ee6cc2e95a52bba51c0d3e460439845289f8451",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/narrow+slow": (
        "82088982ef1b6d80e4197df9195be68541ebeeca53d99c630efc68d86f22117d",
        "84296f1bd1d0c1616da22afeecacfd8e2653b25a47e68272bba162023e8ed304",
    ),
    "steady/finite_snap_hold/wide": (
        "93f19192921551e5042c25cccb59bc8a86ddc46d996b6437a3e110818c6d0b7b",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+fast": (
        "58418c973a318262d92a1b7ce0b27f582ae85c2abd70bba9506022591b48b402",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+slow": (
        "e7c655f877976c9020c781871365e37a7f553865f0b32d8ea4c87f546b39b4c9",
        "9f9ddc3e26639bc1c0d79680d8363004b5817b974d67286d8edca8e459848bce",
    ),
    "steady/fly_in_cascade/fast": (
        "6ad899814d0339b8b7f0e012b555c44033c6626a0d558c46fdb355cc3027f736",
        "1a39008b463ea6e6e8aaae5119af1676e82017712e0ecec42606e526fd9db2d4",
    ),
    "steady/fly_in_cascade/narrow+fast": (
        "17bcb77faa909594c376a7695e285ea6675896f9e54524a05662bac42ea8594e",
        "bef2eadb974023db7f86422e5dc581fdb3eb86a9f391ae5c569949528763b568",
    ),
    "steady/fly_in_cascade/narrow+slow": (
        "6a22703bf9a9e3df87bfd33100dbdb4041d3690344b7fde37506669f2ea8844b",
        "f3d783b88c9fc99c3c06cbf2d0e540fe69cc923428f37294400a6beb3d3bb589",
    ),
    "steady/fly_in_cascade/wide": (
        "d94f03d259ad22621bf8dbf34c23d904297c1d1743ed5862e34fe3cb5d86607c",
        "8d4615bd8a8f8267488e4f32055abc94facf5c38404bb1aa295c5e31b6a05a48",
    ),
    "steady/fly_in_cascade/wide+fast": (
        "8d3b7e92b55d55be052f8902b1ab70c2cc1e4479f598f4bbdb92c56cfe6af79c",
        "2a29a810de1938502c6c9d8c1450f4b7902f587de543129aa538f419c5d908f9",
    ),
    "steady/fly_in_cascade/wide+slow": (
        "2af5779579763a30a7eb43c7168465e794284d6a159835b4e6aec3e32b60460b",
        "ce3a2cd0bbe40c0eb7037219459d5201beb4914ae7a06bbd7f2a7f4c6df79343",
    ),
    "steady/fly_out_cascade/fast": (
        "c21d82fa9efe2af871327e8d936d24a0332330150de703b5b246cb7432cf2c61",
        "9bd7bbc96f5edea525cfaaa0b3671dff06056e8f96934baac3128d3c277bc437",
    ),
    "steady/fly_out_cascade/narrow+fast": (
        "a83d43fd2b9c056a8934917294438973ed866b9b208c33f37df1b75dd84a3797",
        "ea055d37932acdc69bd56640b74050741cfec611d3caffb4e5df24044879f1e1",
    ),
    "steady/fly_out_cascade/narrow+slow": (
        "29b9f306319e5ae2de2a382e8f24889ffb3d77e4f28faf6bcbfcf59fc4b12e5f",
        "ac661a02d9502c30de8e04fd79afc6546368a6ce41a0e8a3855007e49ddee553",
    ),
    "steady/fly_out_cascade/wide": (
        "542e93aa729f18e04c1fbd58c2f29e00d0b252739211b506bbe7e1469c720587",
        "5dea8d5716164cafab9c6f2ae54ec7c3854f8737b927936edf50d32059134379",
    ),
    "steady/fly_out_cascade/wide+fast": (
        "b0122eab0e8040bb94d0963152849f2586ff77baf88d2912d982ddbf42a2d28b",
        "9eac67a83c21237ea0d41f09d90d3ce1174c6ba4fd0c237292cbc07e9b5a072a",
    ),
    "steady/fly_out_cascade/wide+slow": (
        "9cfa0075010b1050b36309617712768121a6a0d5c239172f894a6a2ec4070307",
        "fb9d420703dc0f52f8e319bd479a35063bd40e49fedf2ee61503ed95991251fb",
    ),
    "steady/masked_wheel_flick/fast": (
        "ab2365a7fd33c3d5284acbe5f4b09df4e6b1301da5a0daf582506c564fb89236",
        "e82432d2c5316dd24833f6459d703aee946e7519bf58f946df24373c9a0db2e9",
    ),
    "steady/masked_wheel_flick/narrow+fast": (
        "5d604e29eef0ab59159cb0624c0269b8a98a8e38e1a303ce8264b78179986299",
        "63c6c553c067cd8dab2602fd548017803c24076bcf3f7549a022d7dfc9c73436",
    ),
    "steady/masked_wheel_flick/narrow+slow": (
        "07fcbd8827e90549fe74f3a78332dd00e969d0780cfffff69ee87865a34cfbf0",
        "982bff05eba5994eedec53718c022f3e126434825fa025087858e2320024b876",
    ),
    "steady/masked_wheel_flick/wide": (
        "1ac9836060f3e1dbadffe0c1f210b951b8e1cb46aa5fa1c77517ffa2df918c14",
        "fe80354759a79a46b1b35cb901462e17f2693848d5adef051175a83708b32e35",
    ),
    "steady/masked_wheel_flick/wide+fast": (
        "1b68bdf69281fa8ce1cc84eb419fee426703ca8b7c8d442a3f12f7e068203948",
        "dec3fbafa55e95e2957605f6c7ff2d32b1e21c3225486c8ed89a0b4a6f6c174c",
    ),
    "steady/masked_wheel_flick/wide+slow": (
        "14f09abfd61353d3ce80525091bf48110d3902a9c8a686a077df16380f5c5647",
        "6fc8bfd1a4a336e340b34c323846f611ec217d96912ebcfabc3fe3a057422291",
    ),
    "steady/mirror_wings/fast": (
        "9e81ee972c183f27e1c402716ff982ae6329854b443340d3c0d3a387998624ad",
        "b04447e6c2f1ee6e28ccd6a41ce4d75bcfc1b4675d8e58a508e8c37b0f5467ab",
    ),
    "steady/mirror_wings/narrow+fast": (
        "970fc9ba96d007104a298136b892c02efeca1b22d218e0a24103ec300611b443",
        "858e7e61fec8a862058908f825f260ef85587958215b86174038e33708f45c34",
    ),
    "steady/mirror_wings/narrow+slow": (
        "f0245e9b50e1f10f9e1872f9818fbd327a74b11fe4d07af3203a163155f74662",
        "c9c80c5d0cfce4410311235ba71e84d526dcae441b6f54135cbb56f513a86807",
    ),
    "steady/mirror_wings/wide": (
        "515cd3ca09f9bcb7925bac59d24a4a60ecd478b383d45d8cf73ddd34d2720854",
        "9715d9199effed4b15e204f2f27cf3aec8ebf5c245c3e5b8b5f2ceef2f2117b5",
    ),
    "steady/mirror_wings/wide+fast": (
        "e7acd4f1e1348d11341e7f4d4068501a83425bcef15debda0f1f1860c01b6bf4",
        "0ef196bb7d93b11450f7a536bdc5f073377ba4533f8d79c5ff2ab6a06c476932",
    ),
    "steady/mirror_wings/wide+slow": (
        "875ff1c46c78e95ac4a6ac9a3b16253627311009177c9a1d0b1044a262b3dc23",
        "99431146cf259e92d77022165a8323836dd37c9885d714fcafb95da7e86d7274",
    ),
    "steady/target_orbit/fast": (
        "c51375989ad1e3dfaa39c8804f49ba68ab95d7e652b052e16c0368befc0cf455",
        "43588bfac383601c9088ef39031958fd8e025b5e847e631def2ab0f1e0e5772e",
    ),
    "steady/target_orbit/narrow+fast": (
        "85c38586e5aae5d4988da6da01edb63280a60d49796dbbe4416db84a33b4625e",
        "1308c094876095344e7b83a646161634527d693d0bbffd072694b8ac2bac6ec9",
    ),
    "steady/target_orbit/narrow+slow": (
        "ad4a02150e255ba4eba32a5d4a1a66067bf16fb539fdb0d2c2a1626d56e6013b",
        "d241150b19082d05439a15e5450c356734efff2b4b69be935feb1c4eacaeca1c",
    ),
    "steady/target_orbit/wide": (
        "76adffb1c8269ac2687d1209adb583692e74dfbf5a416e87f2adff1341ea0c00",
        "f97441a2cc0a824180f87a72bc39c631079d3fe6a85297d8938a2b79561024e4",
    ),
    "steady/target_orbit/wide+fast": (
        "911750dd66388c28ca6ad639aa65432c2720a9a6631336353fc34e80351e47de",
        "31d0923d2ad78ee5cbb7d7d13b000ce03ab70bea35be0b36610d62318a4eec2f",
    ),
    "steady/target_orbit/wide+slow": (
        "05ee727ec6498838979256560107f803fa4ad8394a1b8bb5ee1ebfff525e04d8",
        "a1773507c0ac1e2e78a45c45bf2b812a6a11d592d8a0a374d5e55bd604cf5aa4",
    ),
    "steady/zoom_wave/fast": (
        "4adee7aaed5df4da574aa2b1385549f35a69d7eb9929ece4fdbebbc1de2d804f",
        "decd2e1c306dde507b609e631fb0a5113000ca10f54b215128dd27ca088d83c9",
    ),
    "steady/zoom_wave/narrow+fast": (
        "8409cc189f0f88de4444026f99e6ddea8d767ddad900c2810073ddc4d3a217ab",
        "bf283a730211e848435d061c5091566c0cfa10885a0db9154e1a459eb86907af",
    ),
    "steady/zoom_wave/narrow+slow": (
        "319f8b6b86c414a2da08c15eaebdabfef29975d56227001c2f977fec47409bf3",
        "aeb0df9cfc651c31a1ce6d8dbf26b9c9ebd409e5b20b10f333ea4148b7bee8e6",
    ),
    "steady/zoom_wave/wide": (
        "d3d80e53a947a92a925e81fc1a6e5be3f418de3aa59b4a4de661e4ee64e45e7a",
        "15b4fc9c3700a8fc3bfafa975bd4500d7a01d5564b668a6565057ff5295e1300",
    ),
    "steady/zoom_wave/wide+fast": (
        "e8c54b7aafd541e32c0dd1bf8544232972161c4f44609f22fbb52cab38e0589c",
        "f8f6fac7d49fd2434e88c82185793d11d43984ca97c1529c7082f03467c2b093",
    ),
    "steady/zoom_wave/wide+slow": (
        "2902968462b1fc693e5a4fc898942d6702c82ee8d51e60ec6c80efa91d87b317",
        "f7db8dacdd1e40012fabf8fdf188d11cc159381d49d2c3b4c0e1f4d7877bf6bc",
    ),
    "variable/finite_snap_hold/fast": (
        "14c4d258ce378b141e44cfc02389ba0241cc1f9af85397caa3260ca455be0030",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow+fast": (
        "2fd885bf1743a7c8a9dbb95cd721ab1e79b8935078e83d30cd2672b501ab7157",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/narrow+slow": (
        "3c060964c2a2c7aed4d6859daecb1bf569e9d6d13f171dde93a85b62732debaf",
        "b9c51691943843d96703ad5935a75c5d3db1532f5cf571a576a5f77c68460612",
    ),
    "variable/finite_snap_hold/wide": (
        "f6a1714e0f3b5b278a584cdfe110b26fb44643b31ac97dc40e5e86ce734c38e0",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+fast": (
        "46577ddfe4a56f8368293b2d9351ec450b986df5ee56c0248c3bea7061d40957",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+slow": (
        "e7fc119e5f54c5870a604bb3de44883b73807d8b0b719dbe03916567d0b5aafe",
        "230a61f4658fbe9efa21fbfc2acd10ab752aa33ae469105972e92dbc4ddaccef",
    ),
    "variable/fly_in_cascade/fast": (
        "114ce59fa934493c71374ece6b67df111da8cc5c5f94dfcdffa04f9ff903c286",
        "270cb0b2b42c0b2ed0728b508ba0d03a491fbac14fe6dd585698a5057285c8f6",
    ),
    "variable/fly_in_cascade/narrow+fast": (
        "57e148c8f1dd1515eeedf4358130f60da22e956930ea65df6ff9177281f72290",
        "d04ca61a22765b4e997b2ba55df0b672926e2bbf36225e98e905448f6f3526e5",
    ),
    "variable/fly_in_cascade/narrow+slow": (
        "e9592d948307223ab9dfe1ef79f998effbf0a87e7919359f8987113e9e98ab41",
        "cfaa353d2cdb1dede0a7b89aa16994d656281f1275beb55d206f438ba72b2e56",
    ),
    "variable/fly_in_cascade/wide": (
        "d14fe4c0bb7531646648cfcbb6d2a19a7a0a3601a06223085b4d2a02643506f6",
        "52ac24a651637610dcef0daac29221b6066598a5b7b4dcb300471f60d1cfcb10",
    ),
    "variable/fly_in_cascade/wide+fast": (
        "f2e63cd5754b487eb46f78e49cf23705c7344cbbd1cfa3b878e6506b10b1778a",
        "7df58fab43506bab5845c90743ee60ef88fa5c8b950b08fa35dc7cf31c9b4ae8",
    ),
    "variable/fly_in_cascade/wide+slow": (
        "a387fa0e1712a03329fcf2202765370ad804dfe36ac8bf0609cc0c20c06554cb",
        "ac07ebd59cc17d574998d69c3e821d770ea7887e00b6dec324530aeed2f2b366",
    ),
    "variable/fly_out_cascade/fast": (
        "3efed645bf7ddd9a978410f40838677850562220f00742f3f76aaeb89a5b2e85",
        "819b97846f0da31760ebc1a5541ded84a2d53945af1c835795fac312bb3f8b7e",
    ),
    "variable/fly_out_cascade/narrow+fast": (
        "682b5fb5a499853e03c96bff3ff99c6b0dbe6977c54b84e92d45e3fdf98141ba",
        "cc3dfd601cae5e3312b7c10c8a3a663e13b2dba186e85d76d6199b627adc244f",
    ),
    "variable/fly_out_cascade/narrow+slow": (
        "881c84e3d14eda1f23d6596cba8876ce5fb6def5fd1f6264d98fc98dc6780890",
        "dd5792077b9c4c1d1886dcb96fc5865342d1453f2e5406dba700371a582ad577",
    ),
    "variable/fly_out_cascade/wide": (
        "71ce58fda826097454a36ef56cfd3e25f7cd73954dc1ff5bb684499db2be38f5",
        "9074c99a5b6e8df580e9305a95fa13b29d8559440b6f70fb65478514b1c75040",
    ),
    "variable/fly_out_cascade/wide+fast": (
        "a0faa0ad3bc87565fe367bee7bdb0ae9a6be082eeb69b0caa9c315330da28101",
        "8b87e9c7b9aefac1611dc66d2a69ad6e4b2344f89e8f5c31baf668a64aeede3e",
    ),
    "variable/fly_out_cascade/wide+slow": (
        "c7d3198ffb4d5a80894131553f7657f1858804ef7122d96a69ec70798fa42739",
        "2a8894551edf58b38e9cd52fdbe3c9a4acca8eecb1156889072b186cf4671fa1",
    ),
    "variable/masked_wheel_flick/fast": (
        "0b943172911d74348a3d13d4adc0870e26d825c4d9cbdf9ce505a8c9dbcf44ea",
        "d8e2e72bd956b89e026ada2c23bb85281000edf3ed1eba36a60d0c0aecf52515",
    ),
    "variable/masked_wheel_flick/narrow+fast": (
        "b4ead844b9f42a81e7522aff20a78fbfc7e1e2af123fbbf57b9920e4a2d39959",
        "c1a3c12f6acd24a15aa1a9ba5d74bd28bee5810ffd3f5e0f3b1559ed2f174dfc",
    ),
    "variable/masked_wheel_flick/narrow+slow": (
        "56f7e60aecc4a7118a60af243cfbc4226425e5cdb3ff40819db06f78675e0c3c",
        "2558a430925d7ad6d6842e3c9af969bffb27906fdedbd947c0ca9d1b453e0fc2",
    ),
    "variable/masked_wheel_flick/wide": (
        "1ae14a4c1fe0ada78e2fcce82589ecb7fecdf529ae3a84808c407b9f79a42fe4",
        "535e039c6c26d6f78ab95f01c1aaac2c5fb26afec1e94cd2418fc546449cb7f9",
    ),
    "variable/masked_wheel_flick/wide+fast": (
        "dca3382c931cd1571db24eb62b6618498ef7b83e1fadf416482a64fd460f82f8",
        "346cfecaf2cb0c70ec1ec1cc0e73130a509ef456f106ee2cf0129a68af1dd906",
    ),
    "variable/masked_wheel_flick/wide+slow": (
        "928ce91ba5a36aea4165bf955f5e08d92f128a0c85d3402cd9b060f081b6ead6",
        "2e85d5e91e07f289299a27c49b9431ddb807008575a1309bc51bd627489f48d7",
    ),
    "variable/mirror_wings/fast": (
        "50e41ab65d2b65c506ae2265f41664a9d11f038743aa0da97b945e6ad8228fdc",
        "97dfa43672eb9ff20f2499d975f7711f18f97076aac6e263b66ce50dc6a39014",
    ),
    "variable/mirror_wings/narrow+fast": (
        "ca630651ebd469a2a8f3806918c91d878def3dea34814b40b2c39471e461170c",
        "788bb43aad21501da2d566fb34d09de7f8d69ff7a3103ed6a857c7576a11ad1e",
    ),
    "variable/mirror_wings/narrow+slow": (
        "73b7d8364332993996c0a6bbab8c8fdb17eb121ea8fc54c42a1fb6838e940a31",
        "0a557bade4807bf080b296be1a3fe68625c154163ffeeff55f3137fdb64d970a",
    ),
    "variable/mirror_wings/wide": (
        "3855807b66562617a7d004dc4c630bfac6da04bf7300069ffb602a2c49769ff8",
        "cc1afd21c39ab3aed598b1d7f469200f0c8cfff2a9a1441a3147a8b72ee10286",
    ),
    "variable/mirror_wings/wide+fast": (
        "58c30c8fd306182d21d241596056754bdcedbb0a0a48a973d05751dba90b54dd",
        "19c35fa78f034db31d16242220fd0d6009008896b3ca2b11e462d6448b277152",
    ),
    "variable/mirror_wings/wide+slow": (
        "c67722875f298c8d4d4833d15a121deb4c5521cb398b0f793c9339487af9bdda",
        "d42e353647063d8e8ad3c4936fcbbd5e3c21a242ecff2363dfdf13dd776b50c1",
    ),
    "variable/target_orbit/fast": (
        "b7d38613c09fcbad52cf685c3e2278dfdd2511f59034cd0e3027f26a091398ae",
        "7f4ca6832f012f0540590242a81b24d1f94a762d0bc68e84c0260edaf9ebb3a7",
    ),
    "variable/target_orbit/narrow+fast": (
        "1439f24104c074e4a5ccfbe6bbf3a23cdda614317943149a04244992b4eb1f16",
        "96e54669a020381c11c0b080af9364f6e61101f3150eb47121b92e32d83c0e88",
    ),
    "variable/target_orbit/narrow+slow": (
        "b60871476ce568f7e381a6df56523cdc711384281dbdeb4539a9ee956a3232eb",
        "c76a442fcfab75c97fe5b7a9369922c33b4227b1df12cb88fbc2ed10e406a12b",
    ),
    "variable/target_orbit/wide": (
        "5561385bc067824b1bbb89320581bf947867c349ae0d3f61ea597d88a6d58171",
        "7e7221916d9f8fbf90b3f66e11b9a5b0d4f3545944923b916fa6c341e0b13134",
    ),
    "variable/target_orbit/wide+fast": (
        "074f0356af28d0229ad7e6204201299bb27c6d813a84c2e5c623ec639c308d13",
        "da81376c87f194cf1e7249511f0788411854efc51526f87f923dbac9c9ebf193",
    ),
    "variable/target_orbit/wide+slow": (
        "ae18600b35096c50525a652ed2fc3917738809db04fba32b8f402af4d5a7949b",
        "42ea5df862fc884a4442023a9b798ed5d367d0dd85db6492817d0733292ee9f6",
    ),
    "variable/zoom_wave/fast": (
        "b94e97d6e13b88d5f239d975fa9776f1b8c26191b45aa077feee1f47364af908",
        "fb4a81f1a672cf767191b3a674323caa60ac7c4ab08d4ef138dbe410a91d0bad",
    ),
    "variable/zoom_wave/narrow+fast": (
        "721370162a6fbd4b7ae4290aa3947acd593bbfa63a348356d529851ee6b6572d",
        "4667c2393e6bde7ba73ccc8427d6501ddf975f675d4af3e065322ad18f2640ca",
    ),
    "variable/zoom_wave/narrow+slow": (
        "9d9fbe1386ab0d69f3440dddf94038abf628d3091efcc39e3ea2f3987e720715",
        "e35eec0d1c0b3554429c7b42e71740016941caff8cb3513d68973c55a583df52",
    ),
    "variable/zoom_wave/wide": (
        "9023e94ff9b352e92a8b21fdf6e58e09f60c4e423e52d1d61c7c4f65549368d4",
        "d1df17aa71942784b4715d6038237f6e5e36cadde3cfd06f39731140b8d90e9d",
    ),
    "variable/zoom_wave/wide+fast": (
        "3b481cfe6dce1a4c5b05ac9f458b08d7c79146ffcd03432cedde914b6058b488",
        "34eef86923bb6fa37a5ab762cf1375a203ad0bb931dcc75d94e72af86477945e",
    ),
    "variable/zoom_wave/wide+slow": (
        "41272279b23423ea13c36668cb7aae3978c41728107666f94cdc3f5704a60e2a",
        "f16960235d17895270e5fd05bd8b0bd6ab2abd81292bec177b0a68cf9443764b",
    ),
}
"""`grid/template/variant`: (render fingerprint, SHA-256 of the encoded frames)."""

MULTI_PIN = (
    "2b84c3f6838aa6169bc32a837d2315dfe83d291e3b9373da223d198d155825ee",
    "3ea6b3fca42f7ea4bbed6068c580331ce3649c6ef4c49f77f7b23fff7599fba7",
    "9ef5b7a162ca49079bb1a5261223b9ebcd399f8b7bb48463942ba4271861c6fb",
)
"""The multi-section plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256)."""

MULTI_SECTIONS = ("mirror_wings", "target_orbit", "finite_snap_hold", "fly_in_cascade")

GATED_PIN = (
    "3c4e1078347eb957caa16f7c03b1c838e53885671dfa1cd92044c4012f2234a5",
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
    "64f3d395c2d7d28a239540ce9575827870a9581edad41c7ac696b13a31235656",
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
    "37e3b37edb17e34b12697825760c0514c75e6449489f63cec0a13a908873b912",
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
        "070bc0a985cc8974c4305078a37f2df9347e6e321c51620484c231f8e20ecc2c",
        "448dd5edb8649aa4e4a1d31725c6de92a9e1d8d3be740297a0de11dd76a8c57a",
    ),
    "headroom/intensity_half_hold/DRAMATIC": (
        "2546c550db4d685f5138e1bf57301f35a2d3ba0ae59969743fcbd25fa01cdded",
        "13d0f907cfcf370c2e250c959632c3a7ce26d446b11afad12082f1748bc10e0d",
    ),
    "authored_pulse/intensity_authored_pulse/INTENSE": (
        "cd886b710bcde1111dc362216d716c93221ea315a5b73c4e804555c5d04f25cb",
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
        "d755c838846d9d1199754315181a46e6ff32da808326d7bbf393030b7284b2ac",
        "325f3945dfca1082d2d52dda9e22aad57330cd50c15123fc97663683dfc89358",
        "2607e56ef3f1883d9da4c136e05dcfbf9ce3fc8ee46480c0fc75edf6aa623a9d",
    ),
    "tagged_strobe": (
        "3d235504356c0c670aae590a32bdedc14b9140d241fc1972197f4a7a25b5418f",
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
        "2a42c61941e961aa3c61392726c5f6a29befd58b80518052c898b44ebe19cf86",
        "48a5bc7d737f3495c8cbf9a50fa9e29cad900a814d499da01e4bbca09787c371",
        "5650779eacdca88b2594039ce5888d1cb86d78916501f81793329ff24b02af54",
    ),
    "lit": (
        "c95961a6c76f2f6bd36496293cb87bca757020d0e23fe9150be035334d312694",
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
