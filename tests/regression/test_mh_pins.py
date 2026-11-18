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
        "a6feb5383d66a0e64af8b01cbe803108e284603cac457e3366c6d2b9a23738c7",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow": (
        "1408331d49d8094038d03dbcbe93f5e37dbb85880ec2a61232c1a130ca3436c4",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/slow": (
        "d129d740726bf8769b3cc13f14a7868d3524e3c72bb9ce10c65bf50d89d316bb",
        "4d455965979b705ad9af8136e4fd229c7b5374635e1786d07b8cab7636861b9d",
    ),
    "steady/fly_in_cascade/base": (
        "31a95f6b4fcf5f65ad448c4f65a6e89ebc88758a437c1c4345afc70f6453fd3e",
        "ffdfb044c11edf3040dd81744d17558a2d46c21181071367cca5f752a8413b0d",
    ),
    "steady/fly_in_cascade/narrow": (
        "7927121f7fcad8ad1d68eb785e51b076a530075f4d897520fafccdb04b80351f",
        "0280d85aaf1e832fc23b428e311b24ccb67dac720116f25f71d147261f88f310",
    ),
    "steady/fly_in_cascade/slow": (
        "620544f026df96a4e508499a5bdc768d0688f6b3f70a1985f5a8cc046ef7f726",
        "dd49563a5956e1e52f4a2c01e8f005a64a297ff28f9155f3eb05d10a29312433",
    ),
    "steady/fly_out_cascade/base": (
        "f6ebf9bcc5bb5e1ec856d236072fbce6b5e75e46fb94336a4c5fe44f0a847c87",
        "4235e01012dddfdae05f050fa904a9efa2e8eb4cf4f3b7e2ddd06b23951c733e",
    ),
    "steady/fly_out_cascade/narrow": (
        "1fab4d8cc6b18006c9cd26ad46206fed01221a38424992a33cd687c267588ed1",
        "150edd82e9273731bd9ab781ab5c6caf420cf5d1129cddb637915687dab01a88",
    ),
    "steady/fly_out_cascade/slow": (
        "5605311b0e2f54e3cace26e25edbdd7502103621601240a0543597eeaaf32201",
        "c7e91342cab3b42a868f59ab824961da433ac89db0c5646f1fd41e29b0444a70",
    ),
    "steady/masked_wheel_flick/base": (
        "1a79e78ee2be9f87d2a42ba98a4adc0efdf89e62b850acab3201979cda3454c1",
        "08ce9090980dbfefa79b6d78c90ef0f0b0c8ef3a19bb47d193d9af34805cd2de",
    ),
    "steady/masked_wheel_flick/narrow": (
        "4b148540ff97d4729c3756a8187bff8ecbd6cfd481134cbf8cd8f26a81e0bd0c",
        "2537e7e6cf39dad19aadb07a271b223f83c2af7fbbe52b4732f6416cee5993ad",
    ),
    "steady/masked_wheel_flick/slow": (
        "52d95b87ba6b75e726b79f11a75f571b5fbb279a1f9dd2378c7af29d0280b94e",
        "56a758e57a37773c558bff6f8134843cf45c76d005021a6e882374d16d96431a",
    ),
    "steady/mirror_wings/base": (
        "4c42e8386f9cdbf3b25b3e60809e1624e50aaef39083bab0523e68c0701d4a2f",
        "8e3cb9be3de61f968b065d8d0442ac5551becdbbf4624afb76b13a58e0f000fd",
    ),
    "steady/mirror_wings/narrow": (
        "c3fa795792954cc5a9383d884b60499ab9e50ce42727a16799323fabf4f7cd30",
        "d83a23f4fea33e3e6f1b2bbfabdc0b5c26f605b673861c0021a1cc1c8bd36a1b",
    ),
    "steady/mirror_wings/slow": (
        "cb7d3f79efab17f1be30eabb7311153488116ec04f18b91c5cef912033bf50c9",
        "bbcdbab3564fa3d0a7f107562326940ef92fa3f38130a37ac9d8b43f68bdd3b6",
    ),
    "steady/target_orbit/base": (
        "f5f2ea6d92dd8678ce0b9f3a89a6a33e576743111a1ef869b32b8cab9aa38ba0",
        "78d35ed327d359ca0cc456a151ae19f800a20b80ac1cc040ea4448be4d014ed1",
    ),
    "steady/target_orbit/narrow": (
        "53312d3b2fd60b965db6fbc916530cd7f43746ca68057914d42106cf44e7182a",
        "a35e080540356862ecfe8738414c7cef0d781b639b869db97bc27ff0db5f180b",
    ),
    "steady/target_orbit/slow": (
        "f4b20fab7407f6959b27ccf86efebf560c3bf1911ea07be073a8b3a94ee61085",
        "a2eb0bf1f4d04307af57da96941f9d02e8c47ffcc583db3361b0a754975c7d36",
    ),
    "steady/zoom_wave/base": (
        "003ad187c633ae17acfbf71208fd23056f6b0ef9fe27161e3f18c314c6041d81",
        "bfa3f5ef5efd80d8f801f76ab412044d35161bb606288fc35f6fbeaf6970675a",
    ),
    "steady/zoom_wave/narrow": (
        "6dfbd0e366ac0e3c8647863650c894d756c877c79be39f8dd24c49375c4dc559",
        "0ddc62b56b92e1af2deedbc6b9bf47570bbe82663ff559091f3883f32e20169b",
    ),
    "steady/zoom_wave/slow": (
        "680c0bfaf41fb07766b33150478296479c1074f2ee9547628a402eba49d5a970",
        "394aa7ae9fb0cc8e948e2c1b68264b9652edbddd44bcefd9d5ac0dea8e5cdb2c",
    ),
    "variable/finite_snap_hold/base": (
        "2b1039174a2c2cf2be48209311320da7728f88f5f5666d92f33319040cc1aed2",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow": (
        "3b6baf566f55d5290ddd836ede2ec42398bc64da087f2a349efb8023320f5200",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/slow": (
        "4ab011ffd6d814aea96ee50a3caf416fd8f328c6d4ccb15ace2ab3d54a3aada5",
        "e4f7f3d9a0863c4f423dae91e481e8874d5971308aa2196a93e6fca84a6d8930",
    ),
    "variable/fly_in_cascade/base": (
        "2b97b9ff4a2a0e4734e8cccda9c9079d5fc72b678d985c0b7100f18edf5a5594",
        "34f9987fa593584b7894352d13944905315dd6c260035971de447db3c121fd7a",
    ),
    "variable/fly_in_cascade/narrow": (
        "3ea51a0eb275ffb3a9692f8700e88e8fb66b482da68f6d657354dff250ff450d",
        "f2d02f0c7cdbcda887bcd350188338a8bfe0ae583b2b5e092c64b921985f1a9e",
    ),
    "variable/fly_in_cascade/slow": (
        "b2a26ba886bce2d1a871787a388a8616feddd2889263f78695bafd459ae61aac",
        "49c484a8585d159fc61d0989eef1cc2a35fc22a5e46cf202f789736c8dd37ebe",
    ),
    "variable/fly_out_cascade/base": (
        "38b179a6b5172fbedad86b74acb17e6c420395b4651710457761c88095747191",
        "36f29b21188085c76c462a8cfd73f3e10f21f7adfdbca525a674c4960aca28d2",
    ),
    "variable/fly_out_cascade/narrow": (
        "3c89e725363dd967ded87122e6bead278d32711295ae79d908bd405a490e9971",
        "c773f3be51097dd3ec2c309f6149f76e6c3bb7f6d1ea24416aba4662a10cb420",
    ),
    "variable/fly_out_cascade/slow": (
        "79e57f70ebcf9b9824be0029ef0abe5f26e6094e46447d996c594c316eae000b",
        "de6e5fb69f6beeeb43df051367101bd88d3d75b61e811bab2ac3e69d2edd499a",
    ),
    "variable/masked_wheel_flick/base": (
        "cbdf5661fa59dac7a9e46e45ee50502ef93df301cc754512b73a5311fe4e2785",
        "a628fb0ca672aba2a7c36e3ecfafcf1003b8d9c8a06adc5edcf0840004981f3f",
    ),
    "variable/masked_wheel_flick/narrow": (
        "9064932611d686aac7b1a2d116a7b5b353e855019f14ce33e15f88dea5def7a9",
        "a8b2c6b2cf905f657c6993dca020c6aa14bbfacc10f89bfb97491860bc81a6c3",
    ),
    "variable/masked_wheel_flick/slow": (
        "c120fdd3f73c17e8fb7e442804a4e87a9a433368fa511502f837847454f8381f",
        "058ed1d9cbdde981fa5213dd23654d42fc86a9ebd6150fc50b089e07f85825f8",
    ),
    "variable/mirror_wings/base": (
        "c2df7ec5d5e34aa4d7c93a31e9363fa31f523baa613d033ee4e1e1c0289d1c9c",
        "a59b343515d159c1603c1a0ed576afa3b6721178a643ad1c5fbc02d6bb706dde",
    ),
    "variable/mirror_wings/narrow": (
        "b85328b178092b32e4490b0de31afd96f0699a3ae76f63ae0403aa9bb2235172",
        "4d326471bc6af0e6f429bd8e5d5b7e374587d3f545a2fe3d2ad3ef908ab6f801",
    ),
    "variable/mirror_wings/slow": (
        "27ca7531e4ff7e7d87b5912d57157748a447289452cd2de9143acbd07d9e6c69",
        "cee179ea21422e5e6f268664dd79981055afedfd98c5849c5dbfd44f5b80904e",
    ),
    "variable/target_orbit/base": (
        "65346b1577db97c15f3334c073e702899f41da245a8cb8d6412b2666edd7791f",
        "2bfe8b5bd75f0097dd6fb8011e38a11578764984050474ddf0ee402ae3c85fa1",
    ),
    "variable/target_orbit/narrow": (
        "7427a3e3d2d27c79a839e77dbe9cfaf5b2ce24176cc8b91a21d03215d0940aef",
        "9f453dce2badb89d745c808896a8fe6d3b9feafacf5d122371d75d0a6377b4a6",
    ),
    "variable/target_orbit/slow": (
        "4b050b4bc9f0a0c99025a654b7ac8d6d005f23df2032c9ce734e5e2dd5e19c03",
        "ac930585ef5e3f15f79cc7267d407f586e99f71923c67b287415b69ec32365c5",
    ),
    "variable/zoom_wave/base": (
        "e34880d4c25894c32be3456cc605b2c7d8540bbcfe2fa683333cdc97d4d19a86",
        "0020b12393f7dd4cf89bb4c4bbf3cd942ed5aa0de2abde665b3caffefdc751a7",
    ),
    "variable/zoom_wave/narrow": (
        "418997aaf4f71ea7f5da209dfc62f6967aa63df27803427c5d959f760036bccd",
        "a39df6ddbe83086edd4664152946711a1b5a24a927837fd366218594215ce44a",
    ),
    "variable/zoom_wave/slow": (
        "af339cc38c280c7d004cde689490b9a3a4e61d4f9970511523a83dba527c04f0",
        "503a36b0d6d9b85cfa6e5518367e787f835571fbc02f9f44e09f96f2c6689561",
    ),
    "steady/finite_snap_hold/fast": (
        "b10e599abfd79487ca9b960addc5fb7065f4a817fff8739060ba4c315bfc5860",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow+fast": (
        "87a882c406f2bd365960b14efdf759c0c9bf62b83d95c9d02eda63a4d5b55d1b",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/narrow+slow": (
        "69fc73e7c6fe74cd5565accd6f8892c8efeaaaa45f4e061e430272e99bb578d0",
        "84296f1bd1d0c1616da22afeecacfd8e2653b25a47e68272bba162023e8ed304",
    ),
    "steady/finite_snap_hold/wide": (
        "a35e8f8b4b1382fac0a07807fe8d0defd4803f925f5b2048b8fc036b3250a096",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+fast": (
        "d156256f8867d3dd92bcb1ab5ae7b31a5fc19d091715bca975422cca96070977",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+slow": (
        "98af81a4a13789df97237c32c12c4025c4e2baf2c8de2c8661c540c1394e61e0",
        "9f9ddc3e26639bc1c0d79680d8363004b5817b974d67286d8edca8e459848bce",
    ),
    "steady/fly_in_cascade/fast": (
        "723d14895d68ed594f02143746905325be004ece3746a7071bdd6b40804f42b2",
        "1a39008b463ea6e6e8aaae5119af1676e82017712e0ecec42606e526fd9db2d4",
    ),
    "steady/fly_in_cascade/narrow+fast": (
        "398d54c29a1029ffc6f5385786ba2ea60175c34f68adee5ede59185fd1e21d7c",
        "bef2eadb974023db7f86422e5dc581fdb3eb86a9f391ae5c569949528763b568",
    ),
    "steady/fly_in_cascade/narrow+slow": (
        "e19c223ce4d25a7d1f11e4d827f25506d572aa285fe8a1ec6dfeddaf0bfda5b2",
        "f3d783b88c9fc99c3c06cbf2d0e540fe69cc923428f37294400a6beb3d3bb589",
    ),
    "steady/fly_in_cascade/wide": (
        "fe914200c2134f17dee498920033270bd1c8240c18d42aae051f99fa71ff44f8",
        "8d4615bd8a8f8267488e4f32055abc94facf5c38404bb1aa295c5e31b6a05a48",
    ),
    "steady/fly_in_cascade/wide+fast": (
        "d7e5ae49b15b9b41e9d174d39fd6a04077ade3d889476f391dea0b1e5fe5a9aa",
        "2a29a810de1938502c6c9d8c1450f4b7902f587de543129aa538f419c5d908f9",
    ),
    "steady/fly_in_cascade/wide+slow": (
        "446342ce27709b56ce3eb09d48b2637a59c873258b267bbc1245b24e425c82cc",
        "ce3a2cd0bbe40c0eb7037219459d5201beb4914ae7a06bbd7f2a7f4c6df79343",
    ),
    "steady/fly_out_cascade/fast": (
        "c6517d3e0ead13d68951fe00380772c29f797fe37dda2e3b34518c14ea61c8bf",
        "9bd7bbc96f5edea525cfaaa0b3671dff06056e8f96934baac3128d3c277bc437",
    ),
    "steady/fly_out_cascade/narrow+fast": (
        "f4873c7925385e3aaeae565e263ae7106e6554a2fd00095fe5e3402f51b3d2ef",
        "ea055d37932acdc69bd56640b74050741cfec611d3caffb4e5df24044879f1e1",
    ),
    "steady/fly_out_cascade/narrow+slow": (
        "9ee01c0e589570d3c89d95bac7d56b25fb0aeaed3a258d78dc78593f349641ad",
        "ac661a02d9502c30de8e04fd79afc6546368a6ce41a0e8a3855007e49ddee553",
    ),
    "steady/fly_out_cascade/wide": (
        "cc46b3fb263a960260b09755a9a9994f84e600deedb44c4c5dcd8b525d713ecd",
        "5dea8d5716164cafab9c6f2ae54ec7c3854f8737b927936edf50d32059134379",
    ),
    "steady/fly_out_cascade/wide+fast": (
        "c7134df90d4060f6020e8e3e528ccc3c374362cb8eb8a66c518652ac2d49c54f",
        "9eac67a83c21237ea0d41f09d90d3ce1174c6ba4fd0c237292cbc07e9b5a072a",
    ),
    "steady/fly_out_cascade/wide+slow": (
        "b85966738739ba807698c6188b8007349ab641d4de525d53ec5c51ae2bf7f721",
        "fb9d420703dc0f52f8e319bd479a35063bd40e49fedf2ee61503ed95991251fb",
    ),
    "steady/masked_wheel_flick/fast": (
        "0d1d2941505e6f22c142260cf67ac849b4a79e3e1250c325d979cd180d6063dc",
        "e82432d2c5316dd24833f6459d703aee946e7519bf58f946df24373c9a0db2e9",
    ),
    "steady/masked_wheel_flick/narrow+fast": (
        "8e080e7f322a2d63c65d882e2b5bb4e0f8116c3ca2d5f2b79cb3ff37717cf129",
        "63c6c553c067cd8dab2602fd548017803c24076bcf3f7549a022d7dfc9c73436",
    ),
    "steady/masked_wheel_flick/narrow+slow": (
        "42f3081c9776c4aab62b2e1dcff66f7aac8043e7a51c378c2b9e3c088389cbd9",
        "982bff05eba5994eedec53718c022f3e126434825fa025087858e2320024b876",
    ),
    "steady/masked_wheel_flick/wide": (
        "e1bb62321ec52374e7adbedd6f6061e3c9ba18c606d6b37189e04fe1e76a3e01",
        "fe80354759a79a46b1b35cb901462e17f2693848d5adef051175a83708b32e35",
    ),
    "steady/masked_wheel_flick/wide+fast": (
        "4ee3c377ef714abfc7f32090325a7de3350bd7fa366fbcb77f2022a25f07542f",
        "dec3fbafa55e95e2957605f6c7ff2d32b1e21c3225486c8ed89a0b4a6f6c174c",
    ),
    "steady/masked_wheel_flick/wide+slow": (
        "a404b7fa21395ef9c805ffa25e9a4960ceac9b0a96347d88cb25f837c274b63e",
        "6fc8bfd1a4a336e340b34c323846f611ec217d96912ebcfabc3fe3a057422291",
    ),
    "steady/mirror_wings/fast": (
        "9f83bcd901d987180a962e96ea926149c4572e3521c5fba9d020ba21f38b1386",
        "b04447e6c2f1ee6e28ccd6a41ce4d75bcfc1b4675d8e58a508e8c37b0f5467ab",
    ),
    "steady/mirror_wings/narrow+fast": (
        "32ec023bab825f2456519032d9d031e3b7e6faecac045e5ec4171b0d26966c23",
        "858e7e61fec8a862058908f825f260ef85587958215b86174038e33708f45c34",
    ),
    "steady/mirror_wings/narrow+slow": (
        "ee8d1bebafb0b5ddd30cefbae7f63feba95b08456352fef1113f7ca8137a5323",
        "c9c80c5d0cfce4410311235ba71e84d526dcae441b6f54135cbb56f513a86807",
    ),
    "steady/mirror_wings/wide": (
        "3a829b0da26e0eb15cb298e6da0f7bc74f1c95f50d62aa69f0e58504f8ebbb0a",
        "9715d9199effed4b15e204f2f27cf3aec8ebf5c245c3e5b8b5f2ceef2f2117b5",
    ),
    "steady/mirror_wings/wide+fast": (
        "cfe7e2451692c55cf55336f079dddafb9edd510cc58c5146d399305997099758",
        "0ef196bb7d93b11450f7a536bdc5f073377ba4533f8d79c5ff2ab6a06c476932",
    ),
    "steady/mirror_wings/wide+slow": (
        "c787f2d2289abf666db0f367504e250a244b7796016719f88380d70519743afe",
        "99431146cf259e92d77022165a8323836dd37c9885d714fcafb95da7e86d7274",
    ),
    "steady/target_orbit/fast": (
        "98879a2fc5996599546d1ef233a2931d0aa43aadebae3066763232bbc7b83e98",
        "43588bfac383601c9088ef39031958fd8e025b5e847e631def2ab0f1e0e5772e",
    ),
    "steady/target_orbit/narrow+fast": (
        "05f833f0a91ee77d15523482a0284c278967aae6b82156a629835332d128dec0",
        "1308c094876095344e7b83a646161634527d693d0bbffd072694b8ac2bac6ec9",
    ),
    "steady/target_orbit/narrow+slow": (
        "04e691f48f9466315780dbc1593e1364a3149e8bb109c99b1d777e06db15f97e",
        "d241150b19082d05439a15e5450c356734efff2b4b69be935feb1c4eacaeca1c",
    ),
    "steady/target_orbit/wide": (
        "4472e1527dd49ec6f5a9f1fb14852aa161b86b5421d43daf5cef8e039ed93452",
        "f97441a2cc0a824180f87a72bc39c631079d3fe6a85297d8938a2b79561024e4",
    ),
    "steady/target_orbit/wide+fast": (
        "2eaa6972046dfb550ae9dd88824dc6ba75cee95b24b1364dfddfc65174a90c44",
        "31d0923d2ad78ee5cbb7d7d13b000ce03ab70bea35be0b36610d62318a4eec2f",
    ),
    "steady/target_orbit/wide+slow": (
        "c47191728314f94a38832dfbb74a1cfe0c80f16ba2e39b1d9f9c4b6067a23fb3",
        "a1773507c0ac1e2e78a45c45bf2b812a6a11d592d8a0a374d5e55bd604cf5aa4",
    ),
    "steady/zoom_wave/fast": (
        "6798b8063b4126556c9aeecbcb7b81e43bff25f2f94bfa85bae41af18be5748e",
        "decd2e1c306dde507b609e631fb0a5113000ca10f54b215128dd27ca088d83c9",
    ),
    "steady/zoom_wave/narrow+fast": (
        "6487e7bfaf2c8608887b08cfb319825768abb19b48e3c6039a9a7eeea29d6db3",
        "bf283a730211e848435d061c5091566c0cfa10885a0db9154e1a459eb86907af",
    ),
    "steady/zoom_wave/narrow+slow": (
        "5b99729537118e036f9b520105fa3667d696c339749fa6556357c9224b709ac8",
        "aeb0df9cfc651c31a1ce6d8dbf26b9c9ebd409e5b20b10f333ea4148b7bee8e6",
    ),
    "steady/zoom_wave/wide": (
        "0cd1b5c93270efe0abdb8510999643fbdec0db30a84258b2e7afcb4c02ddb725",
        "15b4fc9c3700a8fc3bfafa975bd4500d7a01d5564b668a6565057ff5295e1300",
    ),
    "steady/zoom_wave/wide+fast": (
        "508089bb3f3ddb37be18ef8923bf4033022de4239644e83c33e7366cd93a8b45",
        "f8f6fac7d49fd2434e88c82185793d11d43984ca97c1529c7082f03467c2b093",
    ),
    "steady/zoom_wave/wide+slow": (
        "dc619831e701250e348640cee6191dfb54b66e338a741a6a3f42f5638f893f23",
        "f7db8dacdd1e40012fabf8fdf188d11cc159381d49d2c3b4c0e1f4d7877bf6bc",
    ),
    "variable/finite_snap_hold/fast": (
        "cbfe0cde4d951228f81208f9d03e164872a74c937733afe47ad2514f99fb5a33",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow+fast": (
        "e29b2f45f6e1dd3e0e5850a67081202bb627efea3d7a444de990b2f49cc6ccd3",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/narrow+slow": (
        "09c2ea99dfdb00c74999e8578f053d5afb584bffca1cc62c4aafbed9c69cfcf9",
        "b9c51691943843d96703ad5935a75c5d3db1532f5cf571a576a5f77c68460612",
    ),
    "variable/finite_snap_hold/wide": (
        "371ce2f252266f4a4f77f4d2ff2ac5de4e12bb19d39f8b39b92ebc361554b958",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+fast": (
        "bd3d8b102db22d4e3942f30ddfcb62f3fec5ecac047cbfaaab3b776e02eaac7d",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+slow": (
        "be888a31baeb8c5a9c6522c89bd4c1bfc433e0720c5de2b3c9d9ebd856271175",
        "230a61f4658fbe9efa21fbfc2acd10ab752aa33ae469105972e92dbc4ddaccef",
    ),
    "variable/fly_in_cascade/fast": (
        "da89b1a5097dfbce3ad7c035f41bf533c63c70db6dd019dde8553ecc1b29bc85",
        "270cb0b2b42c0b2ed0728b508ba0d03a491fbac14fe6dd585698a5057285c8f6",
    ),
    "variable/fly_in_cascade/narrow+fast": (
        "c3a530b6e92120d99b7aa9ad34c785f4e211fafc1d6551f878230530f251920d",
        "d04ca61a22765b4e997b2ba55df0b672926e2bbf36225e98e905448f6f3526e5",
    ),
    "variable/fly_in_cascade/narrow+slow": (
        "b47fc4070df6e8f7a5e720452d4ff43be2d30692066cc4f1de24e5ee95921344",
        "cfaa353d2cdb1dede0a7b89aa16994d656281f1275beb55d206f438ba72b2e56",
    ),
    "variable/fly_in_cascade/wide": (
        "567d1f98d7c45aaf64c9e3e017b873ba826e2515c5e2b0c93f422a7e4d71fec9",
        "52ac24a651637610dcef0daac29221b6066598a5b7b4dcb300471f60d1cfcb10",
    ),
    "variable/fly_in_cascade/wide+fast": (
        "f469a1d5dae0ec1b428dda65755ac141fd987fcab88ecf8c22e80bb530c21152",
        "7df58fab43506bab5845c90743ee60ef88fa5c8b950b08fa35dc7cf31c9b4ae8",
    ),
    "variable/fly_in_cascade/wide+slow": (
        "f3b917181a48a9ffcab2372dfcd4d018f89fc9052ce83d6eedceeddee2aec91c",
        "ac07ebd59cc17d574998d69c3e821d770ea7887e00b6dec324530aeed2f2b366",
    ),
    "variable/fly_out_cascade/fast": (
        "9ed1660d14cb5aa66ed0c9de878217383f8b850ac31a2eec01e1dcd8411935e2",
        "819b97846f0da31760ebc1a5541ded84a2d53945af1c835795fac312bb3f8b7e",
    ),
    "variable/fly_out_cascade/narrow+fast": (
        "4b9803bb48be8d1fe63fac8b5b2223796bbf1d7ad90067ee67f77b4dbc54703e",
        "cc3dfd601cae5e3312b7c10c8a3a663e13b2dba186e85d76d6199b627adc244f",
    ),
    "variable/fly_out_cascade/narrow+slow": (
        "109afcb98f182459dcd4181570f6c159ae69dd846a4f65dbcc1c74c28739d2fb",
        "dd5792077b9c4c1d1886dcb96fc5865342d1453f2e5406dba700371a582ad577",
    ),
    "variable/fly_out_cascade/wide": (
        "fede0ccdc0dc3f723cd5de647f909258b2e46ff88d20e0e2f4cd322eb5bf8208",
        "9074c99a5b6e8df580e9305a95fa13b29d8559440b6f70fb65478514b1c75040",
    ),
    "variable/fly_out_cascade/wide+fast": (
        "6810508271298f321a4523dc19f9f52cfc70451f8862a7366b2f2d57fcdff7da",
        "8b87e9c7b9aefac1611dc66d2a69ad6e4b2344f89e8f5c31baf668a64aeede3e",
    ),
    "variable/fly_out_cascade/wide+slow": (
        "b1cde428815cf047517cc7678754c320922bc4c2a1ecbcea9b2b3d37337ced29",
        "2a8894551edf58b38e9cd52fdbe3c9a4acca8eecb1156889072b186cf4671fa1",
    ),
    "variable/masked_wheel_flick/fast": (
        "a026426502b4af49802c8460e04af06cefa84173e49f3a47ced5a2d896e852fa",
        "d8e2e72bd956b89e026ada2c23bb85281000edf3ed1eba36a60d0c0aecf52515",
    ),
    "variable/masked_wheel_flick/narrow+fast": (
        "286587d568f4512f74f600815ed8c596af4346dfc62ed311d8cec26f08b9805d",
        "c1a3c12f6acd24a15aa1a9ba5d74bd28bee5810ffd3f5e0f3b1559ed2f174dfc",
    ),
    "variable/masked_wheel_flick/narrow+slow": (
        "c89ccdbaa74ba3f9567d00d45f3c058d69a16476a6d210fea84b91ff5686c13c",
        "2558a430925d7ad6d6842e3c9af969bffb27906fdedbd947c0ca9d1b453e0fc2",
    ),
    "variable/masked_wheel_flick/wide": (
        "9c73de533422b66801d3d950401bb25bff86ec14c0ec6d4335825ca9c6665a87",
        "535e039c6c26d6f78ab95f01c1aaac2c5fb26afec1e94cd2418fc546449cb7f9",
    ),
    "variable/masked_wheel_flick/wide+fast": (
        "9fa9f23037efda067fe40fe1a4ba510d41441beb6d4466df9fc9963949876758",
        "346cfecaf2cb0c70ec1ec1cc0e73130a509ef456f106ee2cf0129a68af1dd906",
    ),
    "variable/masked_wheel_flick/wide+slow": (
        "b2022859bece7661ac878a14b40ba7deb813429b3ba3ec2e2f356497e06dca64",
        "2e85d5e91e07f289299a27c49b9431ddb807008575a1309bc51bd627489f48d7",
    ),
    "variable/mirror_wings/fast": (
        "d9eac3188048d74391578ec987c273de9f2b1de8036cd94a0aad1e95339f6620",
        "97dfa43672eb9ff20f2499d975f7711f18f97076aac6e263b66ce50dc6a39014",
    ),
    "variable/mirror_wings/narrow+fast": (
        "c6d9f8cb19a1ee02ebaf0c4adb99aa7317473afcd322ae3f23851d639167d6aa",
        "788bb43aad21501da2d566fb34d09de7f8d69ff7a3103ed6a857c7576a11ad1e",
    ),
    "variable/mirror_wings/narrow+slow": (
        "08ee7f3b24a7c3d27da4b4fe29ac99352284ddcd441053e35fd2b89e3d59d73f",
        "0a557bade4807bf080b296be1a3fe68625c154163ffeeff55f3137fdb64d970a",
    ),
    "variable/mirror_wings/wide": (
        "132d7fe7baeb050459b70f34886482f6736e80c746fa4851221ff5c234c4facc",
        "cc1afd21c39ab3aed598b1d7f469200f0c8cfff2a9a1441a3147a8b72ee10286",
    ),
    "variable/mirror_wings/wide+fast": (
        "7e295da99d942319ab78262fcf3068d0552ac026eb8516341df5a8276915f5dd",
        "19c35fa78f034db31d16242220fd0d6009008896b3ca2b11e462d6448b277152",
    ),
    "variable/mirror_wings/wide+slow": (
        "1655730ed71a2caca83afa794ff3476b28aca096c4b23c9b96f2dd90a910ffd4",
        "d42e353647063d8e8ad3c4936fcbbd5e3c21a242ecff2363dfdf13dd776b50c1",
    ),
    "variable/target_orbit/fast": (
        "ff1f6e9060d4bf4db51c90c2654e78ed0adf9757b68b56296b150ad0abd772af",
        "7f4ca6832f012f0540590242a81b24d1f94a762d0bc68e84c0260edaf9ebb3a7",
    ),
    "variable/target_orbit/narrow+fast": (
        "31710a85c9d3f699e51d27ad71c415e44dc0f73118bdbfe543ed680ae306fa5b",
        "96e54669a020381c11c0b080af9364f6e61101f3150eb47121b92e32d83c0e88",
    ),
    "variable/target_orbit/narrow+slow": (
        "8bc85094187b16c5d2797f232595be5ff45c0ec428e1e9fdf7121b1d698942cc",
        "c76a442fcfab75c97fe5b7a9369922c33b4227b1df12cb88fbc2ed10e406a12b",
    ),
    "variable/target_orbit/wide": (
        "146cbca60d0266a74a5b987e5e02a36f04f26c2ebe049da75b0a9130619611b2",
        "7e7221916d9f8fbf90b3f66e11b9a5b0d4f3545944923b916fa6c341e0b13134",
    ),
    "variable/target_orbit/wide+fast": (
        "ea2a6d58881b90953259f166a2b6ab6142b9b7a6b11250bcdd05c595aa8538ce",
        "da81376c87f194cf1e7249511f0788411854efc51526f87f923dbac9c9ebf193",
    ),
    "variable/target_orbit/wide+slow": (
        "92367b9404f4a8dda618c70beb3065e2ffd6a06c13ba649709531d392dfe1a27",
        "42ea5df862fc884a4442023a9b798ed5d367d0dd85db6492817d0733292ee9f6",
    ),
    "variable/zoom_wave/fast": (
        "ef0d12b1685038b61c80b10901741230d4aadc007baedff0556b840238842461",
        "fb4a81f1a672cf767191b3a674323caa60ac7c4ab08d4ef138dbe410a91d0bad",
    ),
    "variable/zoom_wave/narrow+fast": (
        "3b1123c081ea5a94b97fedccc95a577b29b2ccca4188c50937dbb6aba8039ac4",
        "4667c2393e6bde7ba73ccc8427d6501ddf975f675d4af3e065322ad18f2640ca",
    ),
    "variable/zoom_wave/narrow+slow": (
        "bb12684aee79bb0bdc29c8a18d7569d619be7c284cd745d7a41939a207515844",
        "e35eec0d1c0b3554429c7b42e71740016941caff8cb3513d68973c55a583df52",
    ),
    "variable/zoom_wave/wide": (
        "6d3adb375c83b75007ba6bd39e20be995d15364dce5ecf29fa821c8ffc7a18d9",
        "d1df17aa71942784b4715d6038237f6e5e36cadde3cfd06f39731140b8d90e9d",
    ),
    "variable/zoom_wave/wide+fast": (
        "79ea0fda2f08e6ee18e7a1c2977943f4b2c95c19a1a59300eb7dc9f69f4be507",
        "34eef86923bb6fa37a5ab762cf1375a203ad0bb931dcc75d94e72af86477945e",
    ),
    "variable/zoom_wave/wide+slow": (
        "96bc551f6a6b12c16eb47d2ac69424db7654bd758ffabcaf528f8ab3d10a666a",
        "f16960235d17895270e5fd05bd8b0bd6ab2abd81292bec177b0a68cf9443764b",
    ),
}
"""`grid/template/variant`: (render fingerprint, SHA-256 of the encoded frames)."""

MULTI_PIN = (
    "be7260ddad2a930d0fa84a4b426313aecf9b21fcc6cae2c64549503c56606b4e",
    "3ea6b3fca42f7ea4bbed6068c580331ce3649c6ef4c49f77f7b23fff7599fba7",
    "9ef5b7a162ca49079bb1a5261223b9ebcd399f8b7bb48463942ba4271861c6fb",
)
"""The multi-section plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256)."""

MULTI_SECTIONS = ("mirror_wings", "target_orbit", "finite_snap_hold", "fly_in_cascade")

GATED_PIN = (
    "af1c774c512b02e8186ca8f2f7607a7a4351f1b55b08370017bdec9a7bb1e091",
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
    "7566b4a040f4c05a984a296c4f347a25e43728d0c0d6b6d376bece714dd4d63a",
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
    "9fc34eeb3b29cb6f98a8e9a10fe17520789ba255ca9314f5f0621161398a3582",
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
        "b29300b55b02406726e813718382fad9c7adab94c6839cf082f1b25926aca5ef",
        "448dd5edb8649aa4e4a1d31725c6de92a9e1d8d3be740297a0de11dd76a8c57a",
    ),
    "headroom/intensity_half_hold/DRAMATIC": (
        "ce0b427c51b6efdb1c28e4bc817003d0be9cded4831d11572dcae2c3627a485c",
        "13d0f907cfcf370c2e250c959632c3a7ce26d446b11afad12082f1748bc10e0d",
    ),
    "authored_pulse/intensity_authored_pulse/INTENSE": (
        "6a2a2b42d2091d866afe8777de6fb0f20aff3dd66d3125c3f41430ffb7f1fd00",
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
        "5327dae57099228422782c33153ae3eb84d3eb6728c63282c4c0477ba36795b9",
        "325f3945dfca1082d2d52dda9e22aad57330cd50c15123fc97663683dfc89358",
        "2607e56ef3f1883d9da4c136e05dcfbf9ce3fc8ee46480c0fc75edf6aa623a9d",
    ),
    "tagged_strobe": (
        "1e1dcf5369d4b26cd36e57e3b5b9ed265ec69daada6b53fd1bc522d901da09f9",
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
        "a78939e9808fcdadb7adb15ad596e091d21ed81eff3355b25e895895a6faeb53",
        "48a5bc7d737f3495c8cbf9a50fa9e29cad900a814d499da01e4bbca09787c371",
        "5650779eacdca88b2594039ce5888d1cb86d78916501f81793329ff24b02af54",
    ),
    "lit": (
        "e9fdc606fdf503e63ebc49b8c6cad153c02736f8672e181d05b892530c6e1176",
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
