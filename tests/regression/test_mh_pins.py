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
        "746e73af897ee112b947b6a93060d81b11da94d47d88fad92c00e3736515383e",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow": (
        "e29ae9b651ebb77cfa6701659fa8133adf44ebcfefa91b0185ce5e77c3b43735",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/slow": (
        "42d334ca69ab505280b48b89db2dd9612d116377294504c5c6ccf264b8cf061a",
        "4d455965979b705ad9af8136e4fd229c7b5374635e1786d07b8cab7636861b9d",
    ),
    "steady/fly_in_cascade/base": (
        "ec155ba2b26b54703b323c8c72e037683d8be1953721f22d9a86371a9becf8a1",
        "ffdfb044c11edf3040dd81744d17558a2d46c21181071367cca5f752a8413b0d",
    ),
    "steady/fly_in_cascade/narrow": (
        "1ec9bcbf38ebad20c44fba6e8183dcef69b8156e81cd456ebdc9e6ae22fcd51d",
        "0280d85aaf1e832fc23b428e311b24ccb67dac720116f25f71d147261f88f310",
    ),
    "steady/fly_in_cascade/slow": (
        "426dc03488828fecca2bcadf0844a72418902c6b77aefb38d56c665a11829885",
        "dd49563a5956e1e52f4a2c01e8f005a64a297ff28f9155f3eb05d10a29312433",
    ),
    "steady/fly_out_cascade/base": (
        "22ae48c1a90613969b1cf265cb6978bd35e58ea68229d7bc363328163adb0c4e",
        "4235e01012dddfdae05f050fa904a9efa2e8eb4cf4f3b7e2ddd06b23951c733e",
    ),
    "steady/fly_out_cascade/narrow": (
        "96fcd4939d60a3cb0b791ce1a2ed6050ecde14f8ebabb172c8314c30150d46b5",
        "150edd82e9273731bd9ab781ab5c6caf420cf5d1129cddb637915687dab01a88",
    ),
    "steady/fly_out_cascade/slow": (
        "a760ff1cf3a26a9de4abf5df382680f3e1116fc9dcd2607b2a158ace0ec38916",
        "c7e91342cab3b42a868f59ab824961da433ac89db0c5646f1fd41e29b0444a70",
    ),
    "steady/masked_wheel_flick/base": (
        "6f48fa3a640161e8411fdb7799efac9cce625ab0110ff1b92f13e09f51eb6388",
        "08ce9090980dbfefa79b6d78c90ef0f0b0c8ef3a19bb47d193d9af34805cd2de",
    ),
    "steady/masked_wheel_flick/narrow": (
        "cfa9646abcb14ce42f434530a165e501ec0e7f3c714324c17f7e843feb4adb7f",
        "2537e7e6cf39dad19aadb07a271b223f83c2af7fbbe52b4732f6416cee5993ad",
    ),
    "steady/masked_wheel_flick/slow": (
        "5b175f1e49db94457b2136475ef53c653c56cae946d492a8ec9dfaebf9a748e1",
        "56a758e57a37773c558bff6f8134843cf45c76d005021a6e882374d16d96431a",
    ),
    "steady/mirror_wings/base": (
        "d4a50f8db9a268c9c437a0dfe5cafc84907974f1a2d2977913001abdb5ec2f8e",
        "8e3cb9be3de61f968b065d8d0442ac5551becdbbf4624afb76b13a58e0f000fd",
    ),
    "steady/mirror_wings/narrow": (
        "1279fc2084006b059465bc321d3b97ba18ede642f4fff071d5e581843fb8f0a8",
        "d83a23f4fea33e3e6f1b2bbfabdc0b5c26f605b673861c0021a1cc1c8bd36a1b",
    ),
    "steady/mirror_wings/slow": (
        "e290efeca160463cd908602f9c2611c4e1689664bc8e945f366d113f6fbf6599",
        "bbcdbab3564fa3d0a7f107562326940ef92fa3f38130a37ac9d8b43f68bdd3b6",
    ),
    "steady/target_orbit/base": (
        "f10ba2bd96ea6aa226504da47f41e95437b29df6a46551476c770fb49db4bf4b",
        "78d35ed327d359ca0cc456a151ae19f800a20b80ac1cc040ea4448be4d014ed1",
    ),
    "steady/target_orbit/narrow": (
        "de182b879d9eaf7b50bdbef62af4d5cf3fca10dafc28064c9275116181007037",
        "a35e080540356862ecfe8738414c7cef0d781b639b869db97bc27ff0db5f180b",
    ),
    "steady/target_orbit/slow": (
        "5b09092e1284803fb1245c7890aae5357ddfc15a6e77c8372d30f97e5320dea3",
        "a2eb0bf1f4d04307af57da96941f9d02e8c47ffcc583db3361b0a754975c7d36",
    ),
    "steady/zoom_wave/base": (
        "76dc295d6eb1fbbb77eb2764fdcd997c4cfa862f7e4ab05dafe4a266947ba01e",
        "bfa3f5ef5efd80d8f801f76ab412044d35161bb606288fc35f6fbeaf6970675a",
    ),
    "steady/zoom_wave/narrow": (
        "22be2f7a92b75cf192f874f3a0c374e54d5e60f55f226516937d90068ce38611",
        "0ddc62b56b92e1af2deedbc6b9bf47570bbe82663ff559091f3883f32e20169b",
    ),
    "steady/zoom_wave/slow": (
        "1fec0b4daa88aaabfa03130c08ef4ab05ea24a79ca7ce2a4a562892c4dc9c335",
        "394aa7ae9fb0cc8e948e2c1b68264b9652edbddd44bcefd9d5ac0dea8e5cdb2c",
    ),
    "variable/finite_snap_hold/base": (
        "4011cd6b6dfa9c2465dcb164d30b126c59132c63efb00c00ccf76ea7fc1a0679",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow": (
        "ad609fca64cf08fe2dba73cf003761ef02d4a7829b391d0309612affe65566e6",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/slow": (
        "d5321e492173afaff42703bf589a509c3c18ca530f8c81e67ec5bd509629ce93",
        "e4f7f3d9a0863c4f423dae91e481e8874d5971308aa2196a93e6fca84a6d8930",
    ),
    "variable/fly_in_cascade/base": (
        "7ff4fd4a737aef84538205acd9506935437cea09cdfb4949327181b2f974b518",
        "34f9987fa593584b7894352d13944905315dd6c260035971de447db3c121fd7a",
    ),
    "variable/fly_in_cascade/narrow": (
        "3ba7ab6a1f92c9e2e80be012b34028233bfdaf3b9f7aba4e333b7bbc8a34132b",
        "f2d02f0c7cdbcda887bcd350188338a8bfe0ae583b2b5e092c64b921985f1a9e",
    ),
    "variable/fly_in_cascade/slow": (
        "49f02045343bca3b6e051447c8bb28707961df053ea0fbd3dab02c0b4439eb61",
        "49c484a8585d159fc61d0989eef1cc2a35fc22a5e46cf202f789736c8dd37ebe",
    ),
    "variable/fly_out_cascade/base": (
        "d3f2fc100b0482b19162116e62706fd59d2678c68a74f255470e7f4fb8b2695d",
        "36f29b21188085c76c462a8cfd73f3e10f21f7adfdbca525a674c4960aca28d2",
    ),
    "variable/fly_out_cascade/narrow": (
        "16eba5b9536878d4708280e7117882dcd80cdd0c40b8a725922c8537e894ff85",
        "c773f3be51097dd3ec2c309f6149f76e6c3bb7f6d1ea24416aba4662a10cb420",
    ),
    "variable/fly_out_cascade/slow": (
        "338bf09a57fbf100cb97a9b141f6156cdac32883579d77ebe531fc5c1765e0fb",
        "de6e5fb69f6beeeb43df051367101bd88d3d75b61e811bab2ac3e69d2edd499a",
    ),
    "variable/masked_wheel_flick/base": (
        "8b918107da8a6bd215b851ea800d5dae8d42651326f152976cefe56accf6f156",
        "a628fb0ca672aba2a7c36e3ecfafcf1003b8d9c8a06adc5edcf0840004981f3f",
    ),
    "variable/masked_wheel_flick/narrow": (
        "f73e00ef89ad70079576ca326885c7f61b9f50d4cf05219c15c39dd2098b6761",
        "a8b2c6b2cf905f657c6993dca020c6aa14bbfacc10f89bfb97491860bc81a6c3",
    ),
    "variable/masked_wheel_flick/slow": (
        "b524c55d783bb95f4416a68c9db996f13354708504e0e3908d2351b96830ae51",
        "058ed1d9cbdde981fa5213dd23654d42fc86a9ebd6150fc50b089e07f85825f8",
    ),
    "variable/mirror_wings/base": (
        "56a1f5a3f44e9e6cd366802c8119ff821889bd6498b62d60de61545fc0483c19",
        "a59b343515d159c1603c1a0ed576afa3b6721178a643ad1c5fbc02d6bb706dde",
    ),
    "variable/mirror_wings/narrow": (
        "cb96e27d7a45ec61b64ea0c39fa64864d39bbcaf1e51195310d23e87f6cda692",
        "4d326471bc6af0e6f429bd8e5d5b7e374587d3f545a2fe3d2ad3ef908ab6f801",
    ),
    "variable/mirror_wings/slow": (
        "e7ca0df6869239ae15bd496e3b59a47550c68c7e6908e8eb11b0ec108c0e98f1",
        "cee179ea21422e5e6f268664dd79981055afedfd98c5849c5dbfd44f5b80904e",
    ),
    "variable/target_orbit/base": (
        "b701d9c9f1e6fba504bbc6ac2783fff52ecd156c209546933932e9ed95962046",
        "2bfe8b5bd75f0097dd6fb8011e38a11578764984050474ddf0ee402ae3c85fa1",
    ),
    "variable/target_orbit/narrow": (
        "44f2da928d8a0d67003e7cc570c803fe17968dc1f9bd6d1946f920e545ddd2a9",
        "9f453dce2badb89d745c808896a8fe6d3b9feafacf5d122371d75d0a6377b4a6",
    ),
    "variable/target_orbit/slow": (
        "4a0a3bf590fecbbcfb9ead65b6f5ae76467d0c14b31489b292f962e063cb5dc6",
        "ac930585ef5e3f15f79cc7267d407f586e99f71923c67b287415b69ec32365c5",
    ),
    "variable/zoom_wave/base": (
        "9a9de01c098e3bb797d18f709211b0c6cb7797f241b63be134c200fee7dfbc3a",
        "0020b12393f7dd4cf89bb4c4bbf3cd942ed5aa0de2abde665b3caffefdc751a7",
    ),
    "variable/zoom_wave/narrow": (
        "b701522c263d039a3ebe3971192575cc39eac97230cee0ecd4b7339e7ce1e0e0",
        "a39df6ddbe83086edd4664152946711a1b5a24a927837fd366218594215ce44a",
    ),
    "variable/zoom_wave/slow": (
        "d4ed4cce011c5d5297d17482136e03ee86796397ff5ac709fffbbd32a026d141",
        "503a36b0d6d9b85cfa6e5518367e787f835571fbc02f9f44e09f96f2c6689561",
    ),
    "steady/finite_snap_hold/fast": (
        "2778b15ec07e15284404a784a1f431738db0156b66fa0d81f10442e4444069e4",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow+fast": (
        "c7fc9bb4f1ecf162d88fd0ddfd4fac786f71178e2bdb4b616dab5ab1080d33fe",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/narrow+slow": (
        "25e367591a6e83fd395ef004bb8a495c47d8342ec9b73fd6a4151b2687c33fd0",
        "84296f1bd1d0c1616da22afeecacfd8e2653b25a47e68272bba162023e8ed304",
    ),
    "steady/finite_snap_hold/wide": (
        "2afdc48001a7ae3a3f2d52cf5fb982cccbf521e77e3d39649a2e9af6b6d23045",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+fast": (
        "be126f333753f7bf39e8eede13833849ddfdc33e7752fea1b547d3f486c615f7",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+slow": (
        "fd8991a023de251362d6034f53979b03141ec4995d9f2cb537f52d6476142ad2",
        "9f9ddc3e26639bc1c0d79680d8363004b5817b974d67286d8edca8e459848bce",
    ),
    "steady/fly_in_cascade/fast": (
        "0698568131fec1b4536f51ad06924776a34304ec5441f8c60721c17a967458bd",
        "1a39008b463ea6e6e8aaae5119af1676e82017712e0ecec42606e526fd9db2d4",
    ),
    "steady/fly_in_cascade/narrow+fast": (
        "18f7935ac49a78ba97f59b2d345be9180435076d5f3865cc9fba4796adc9b109",
        "bef2eadb974023db7f86422e5dc581fdb3eb86a9f391ae5c569949528763b568",
    ),
    "steady/fly_in_cascade/narrow+slow": (
        "9ac81f225741ef7a8648dcb28182c3e2f2ffaea864994bb798d60e4651b2226c",
        "f3d783b88c9fc99c3c06cbf2d0e540fe69cc923428f37294400a6beb3d3bb589",
    ),
    "steady/fly_in_cascade/wide": (
        "61ddffa5caded65c1ff48d849a31ebec29f38630a1dcb1214b77751dcb0904a7",
        "8d4615bd8a8f8267488e4f32055abc94facf5c38404bb1aa295c5e31b6a05a48",
    ),
    "steady/fly_in_cascade/wide+fast": (
        "677b44c8afc96fcb24322ed3282822c6317b77456fc6231518d6dfdcaf2da976",
        "2a29a810de1938502c6c9d8c1450f4b7902f587de543129aa538f419c5d908f9",
    ),
    "steady/fly_in_cascade/wide+slow": (
        "bce45f726d88097fb907452b45ac67171873fe613fe095a89ae2d8dcc7267124",
        "ce3a2cd0bbe40c0eb7037219459d5201beb4914ae7a06bbd7f2a7f4c6df79343",
    ),
    "steady/fly_out_cascade/fast": (
        "f1ea230222d1766aa1b9b411ae695153a6f41514772a3514c507af359f820975",
        "9bd7bbc96f5edea525cfaaa0b3671dff06056e8f96934baac3128d3c277bc437",
    ),
    "steady/fly_out_cascade/narrow+fast": (
        "819d7188cb2a38bc0aca4e34cf2181b15ed8af774ea74dfa0c4a699375c4cb01",
        "ea055d37932acdc69bd56640b74050741cfec611d3caffb4e5df24044879f1e1",
    ),
    "steady/fly_out_cascade/narrow+slow": (
        "ededdcb107ff6c24c1385b908c187122faea7346132f853c0e0f7b6dfea5a0da",
        "ac661a02d9502c30de8e04fd79afc6546368a6ce41a0e8a3855007e49ddee553",
    ),
    "steady/fly_out_cascade/wide": (
        "4f1b21be0a59ea9f3a12bc8481981a1ebdcc4dfb3f741bbf04ca82827e541d59",
        "5dea8d5716164cafab9c6f2ae54ec7c3854f8737b927936edf50d32059134379",
    ),
    "steady/fly_out_cascade/wide+fast": (
        "b6fb1847fc2c456d1c9adcbaea49afcfcd4bfe760fbbf0816c361a70b0ca5a37",
        "9eac67a83c21237ea0d41f09d90d3ce1174c6ba4fd0c237292cbc07e9b5a072a",
    ),
    "steady/fly_out_cascade/wide+slow": (
        "752ab807eeca7ae4edbdbbd158c01576e94560b77d8217e3fca1e62b1f0bbd00",
        "fb9d420703dc0f52f8e319bd479a35063bd40e49fedf2ee61503ed95991251fb",
    ),
    "steady/masked_wheel_flick/fast": (
        "4ecbac311d4b852b57430f4f84c12b9dd99d1816390da040b58ff8b3bde44c02",
        "e82432d2c5316dd24833f6459d703aee946e7519bf58f946df24373c9a0db2e9",
    ),
    "steady/masked_wheel_flick/narrow+fast": (
        "8db39fc7b88aad2df2b98603a95afaf8625f8b681c424ab83dbeb28d942d435b",
        "63c6c553c067cd8dab2602fd548017803c24076bcf3f7549a022d7dfc9c73436",
    ),
    "steady/masked_wheel_flick/narrow+slow": (
        "30df170a5f91c7c15aed1267aa5536b62c6cbc2105e3e9275f9e3d7947749c70",
        "982bff05eba5994eedec53718c022f3e126434825fa025087858e2320024b876",
    ),
    "steady/masked_wheel_flick/wide": (
        "3f2dcc236c7fad716c42e3f33a02129c152c9cd5e34a5428bd1dca747ff2011d",
        "fe80354759a79a46b1b35cb901462e17f2693848d5adef051175a83708b32e35",
    ),
    "steady/masked_wheel_flick/wide+fast": (
        "2f8f95b5a5fbf517e3da994713b1ae5c31cc7ac06a6d69bc8832a93a4258af5e",
        "dec3fbafa55e95e2957605f6c7ff2d32b1e21c3225486c8ed89a0b4a6f6c174c",
    ),
    "steady/masked_wheel_flick/wide+slow": (
        "85d07b61e868137ae0ee1e3c3ee91cce52c2ba08a45dca8e862f2039197d40c9",
        "6fc8bfd1a4a336e340b34c323846f611ec217d96912ebcfabc3fe3a057422291",
    ),
    "steady/mirror_wings/fast": (
        "d0f2fb8da73832d2da43e0165969e1065f37f0f1000fc1d1fbc8a4083021f9ea",
        "b04447e6c2f1ee6e28ccd6a41ce4d75bcfc1b4675d8e58a508e8c37b0f5467ab",
    ),
    "steady/mirror_wings/narrow+fast": (
        "ab96b1caf97cf986d8bbde01718d66c5539cfa73edd2324d39e9764d198fb480",
        "858e7e61fec8a862058908f825f260ef85587958215b86174038e33708f45c34",
    ),
    "steady/mirror_wings/narrow+slow": (
        "2a3f416dd344d412bfafb59389db0cbf8e4bf31d598c31803b43c851a371070d",
        "c9c80c5d0cfce4410311235ba71e84d526dcae441b6f54135cbb56f513a86807",
    ),
    "steady/mirror_wings/wide": (
        "1e78dacb1b4d7a6b18c3585bd4fe9aefcc36680b48637ecb47d404191ca7b6b6",
        "9715d9199effed4b15e204f2f27cf3aec8ebf5c245c3e5b8b5f2ceef2f2117b5",
    ),
    "steady/mirror_wings/wide+fast": (
        "3255c8b4434bd85c7dad7d22e982eaf3498c99a24d9fefdb0c548dc5dde98eaa",
        "0ef196bb7d93b11450f7a536bdc5f073377ba4533f8d79c5ff2ab6a06c476932",
    ),
    "steady/mirror_wings/wide+slow": (
        "6910c06e22a739ea2e0cca386e197bdefee44ff6a9f5879b955adfc29045df45",
        "99431146cf259e92d77022165a8323836dd37c9885d714fcafb95da7e86d7274",
    ),
    "steady/target_orbit/fast": (
        "ad11809a2897e5bf39b578ce8682034b8511887ad857b0c81836d0df6575ad03",
        "43588bfac383601c9088ef39031958fd8e025b5e847e631def2ab0f1e0e5772e",
    ),
    "steady/target_orbit/narrow+fast": (
        "275429e4fa84e4dd7316548d1656edebac8469597f6045372cea9074cb31f4dd",
        "1308c094876095344e7b83a646161634527d693d0bbffd072694b8ac2bac6ec9",
    ),
    "steady/target_orbit/narrow+slow": (
        "3d9afd11478d1ccc4801ece157d6e0a638612c7a818ecf1a025d8703001f64c6",
        "d241150b19082d05439a15e5450c356734efff2b4b69be935feb1c4eacaeca1c",
    ),
    "steady/target_orbit/wide": (
        "20fb2f5d52fc61d3e13abd3e03779d74c470c760eddcd23eb1599564393f707a",
        "f97441a2cc0a824180f87a72bc39c631079d3fe6a85297d8938a2b79561024e4",
    ),
    "steady/target_orbit/wide+fast": (
        "28402e009a06da6c85c41e6699de0108c7ce841b50dccaa12a05212dbe2411a9",
        "31d0923d2ad78ee5cbb7d7d13b000ce03ab70bea35be0b36610d62318a4eec2f",
    ),
    "steady/target_orbit/wide+slow": (
        "be631bf6e6570f8d2205e5e9d37d7938b404eebaefe648f5972b0d8c52d8159a",
        "a1773507c0ac1e2e78a45c45bf2b812a6a11d592d8a0a374d5e55bd604cf5aa4",
    ),
    "steady/zoom_wave/fast": (
        "f3adcbf70d1bccda9aedc224851da51d3ec01f6b23cf4b128f17eec058ab8caa",
        "decd2e1c306dde507b609e631fb0a5113000ca10f54b215128dd27ca088d83c9",
    ),
    "steady/zoom_wave/narrow+fast": (
        "37b6ee220b95f0399009ff3197d20e8d6a7f16ca48a6539e5dd2535c2a154372",
        "bf283a730211e848435d061c5091566c0cfa10885a0db9154e1a459eb86907af",
    ),
    "steady/zoom_wave/narrow+slow": (
        "4b26ec9a930e1ef9e61e3bca460d5e67969f2ddb2c300ec65dd10f39fa81f657",
        "aeb0df9cfc651c31a1ce6d8dbf26b9c9ebd409e5b20b10f333ea4148b7bee8e6",
    ),
    "steady/zoom_wave/wide": (
        "4c53d9064604f1d0d8f96a1c78182d554055f4b98af7049f18ac94eb1f8e1fb5",
        "15b4fc9c3700a8fc3bfafa975bd4500d7a01d5564b668a6565057ff5295e1300",
    ),
    "steady/zoom_wave/wide+fast": (
        "406dc3b28e1f65726d437c7ed5adb6180ee5f5a1f473c70c9c16854b55938f84",
        "f8f6fac7d49fd2434e88c82185793d11d43984ca97c1529c7082f03467c2b093",
    ),
    "steady/zoom_wave/wide+slow": (
        "829275472be20d45fddbb66f17280fdfd7df4272cf9457315dfb63f06251a7e4",
        "f7db8dacdd1e40012fabf8fdf188d11cc159381d49d2c3b4c0e1f4d7877bf6bc",
    ),
    "variable/finite_snap_hold/fast": (
        "a6bf7d6919284893b8827e4b1901239fadb9423df783d665fd2450b96393279f",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow+fast": (
        "06435b869fd8d0f4e303fd85cb89d05ea3d80e09ac8b26259f01859ee4fc5fbb",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/narrow+slow": (
        "7d9b8355145d5a17fb7a203188787dc2892da43f24e30dd9c039012c698064dc",
        "b9c51691943843d96703ad5935a75c5d3db1532f5cf571a576a5f77c68460612",
    ),
    "variable/finite_snap_hold/wide": (
        "76aa9aa05bcffd353d948beb3e34635ea311eb89c59ccc304a3f60007100988a",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+fast": (
        "279f1622d30f4c7b71fbbedcdbdc323ced158d79c79dcb0f1ee8c37ca7779eea",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+slow": (
        "51ae1d9c5c91666a800956a8308b4372bc440ba7d6a86d699365da83325137c9",
        "230a61f4658fbe9efa21fbfc2acd10ab752aa33ae469105972e92dbc4ddaccef",
    ),
    "variable/fly_in_cascade/fast": (
        "f693e27b28b530306dd59966bef5064b099084698a7bd346f2319cb6645709e4",
        "270cb0b2b42c0b2ed0728b508ba0d03a491fbac14fe6dd585698a5057285c8f6",
    ),
    "variable/fly_in_cascade/narrow+fast": (
        "167658154eabbe7ede66f26b8273a3b6f93729343df07d7eea7526db6d416251",
        "d04ca61a22765b4e997b2ba55df0b672926e2bbf36225e98e905448f6f3526e5",
    ),
    "variable/fly_in_cascade/narrow+slow": (
        "3671ec02104307e6f36a88de3d18aa54f939ebe5c7849cb936b8b135ff04ccf6",
        "cfaa353d2cdb1dede0a7b89aa16994d656281f1275beb55d206f438ba72b2e56",
    ),
    "variable/fly_in_cascade/wide": (
        "c0fbb2ba2a6649baede30f0ad32eac8059808d33cb1897d498b913e665887140",
        "52ac24a651637610dcef0daac29221b6066598a5b7b4dcb300471f60d1cfcb10",
    ),
    "variable/fly_in_cascade/wide+fast": (
        "ce119d5b2426057b643bb04b498a8a2133a167b51206d2a62f86fc6abe2b6100",
        "7df58fab43506bab5845c90743ee60ef88fa5c8b950b08fa35dc7cf31c9b4ae8",
    ),
    "variable/fly_in_cascade/wide+slow": (
        "b4627e2128a8f84f68043be8251839cd77a0cb5568c1e57c98cd0cfada81c63f",
        "ac07ebd59cc17d574998d69c3e821d770ea7887e00b6dec324530aeed2f2b366",
    ),
    "variable/fly_out_cascade/fast": (
        "1fcee0c724b2f7cfdaa4fb308d6065dac474793b779ee2ad112c403e4b38404e",
        "819b97846f0da31760ebc1a5541ded84a2d53945af1c835795fac312bb3f8b7e",
    ),
    "variable/fly_out_cascade/narrow+fast": (
        "66f1bcbcb62c683c92bdfd5074ce84d97cebb607c37732f39c2525fe004939b2",
        "cc3dfd601cae5e3312b7c10c8a3a663e13b2dba186e85d76d6199b627adc244f",
    ),
    "variable/fly_out_cascade/narrow+slow": (
        "4a97e3bfd42cdd19320396a34125568b67c22f107a55f76c73c79e247b0f6a98",
        "dd5792077b9c4c1d1886dcb96fc5865342d1453f2e5406dba700371a582ad577",
    ),
    "variable/fly_out_cascade/wide": (
        "3ad7380bbaffcd613b2c9d0792faa2e4dcb82625c04594df9f9779763ddda952",
        "9074c99a5b6e8df580e9305a95fa13b29d8559440b6f70fb65478514b1c75040",
    ),
    "variable/fly_out_cascade/wide+fast": (
        "e6ffad8542959d7e0114c30f792e6fa79b582d9ab147f6dbb0e8a165762ffea2",
        "8b87e9c7b9aefac1611dc66d2a69ad6e4b2344f89e8f5c31baf668a64aeede3e",
    ),
    "variable/fly_out_cascade/wide+slow": (
        "734c69fafc24c3e4c01f93eec9d82e6e418d85df92509fe2bbbdaf64560136d9",
        "2a8894551edf58b38e9cd52fdbe3c9a4acca8eecb1156889072b186cf4671fa1",
    ),
    "variable/masked_wheel_flick/fast": (
        "abbbbbcf036756ab2bcc89b34d29f3c218454f484b9f9d7a262f2c8d5aebd777",
        "d8e2e72bd956b89e026ada2c23bb85281000edf3ed1eba36a60d0c0aecf52515",
    ),
    "variable/masked_wheel_flick/narrow+fast": (
        "5831d1d8affaaad25de78427142654a8fa9f2a131a786fb6f87ee79506cf90fe",
        "c1a3c12f6acd24a15aa1a9ba5d74bd28bee5810ffd3f5e0f3b1559ed2f174dfc",
    ),
    "variable/masked_wheel_flick/narrow+slow": (
        "7f1027f3c459bda21f61dadd86f80fe680ab95aff0324b0f95d928c6d127a217",
        "2558a430925d7ad6d6842e3c9af969bffb27906fdedbd947c0ca9d1b453e0fc2",
    ),
    "variable/masked_wheel_flick/wide": (
        "49bdfd060bc99a933f2783f407af9e919e978ea1083151c9210a344fa77a01eb",
        "535e039c6c26d6f78ab95f01c1aaac2c5fb26afec1e94cd2418fc546449cb7f9",
    ),
    "variable/masked_wheel_flick/wide+fast": (
        "5ce399e0f58eef93f7be4e7e9d8578dc6e4e30d976879250dad65738dc4a271b",
        "346cfecaf2cb0c70ec1ec1cc0e73130a509ef456f106ee2cf0129a68af1dd906",
    ),
    "variable/masked_wheel_flick/wide+slow": (
        "c738a94c26de431d0ac06319e5ec386e3c423e0b1007a4d2cab4f8aa8dff7945",
        "2e85d5e91e07f289299a27c49b9431ddb807008575a1309bc51bd627489f48d7",
    ),
    "variable/mirror_wings/fast": (
        "859b2359110ec9358fb943b63458502497dece927fc661111e4088edb79b8a7d",
        "97dfa43672eb9ff20f2499d975f7711f18f97076aac6e263b66ce50dc6a39014",
    ),
    "variable/mirror_wings/narrow+fast": (
        "7cea472c18eaa24002b2b6f0f06c32f9195fdeeb4b7a4ab2112196e0bcbf2199",
        "788bb43aad21501da2d566fb34d09de7f8d69ff7a3103ed6a857c7576a11ad1e",
    ),
    "variable/mirror_wings/narrow+slow": (
        "6807e691e71c84dc018f9be7f63426ec13d2c50c03879fdc3c7b64baa3cf0bf5",
        "0a557bade4807bf080b296be1a3fe68625c154163ffeeff55f3137fdb64d970a",
    ),
    "variable/mirror_wings/wide": (
        "604d9e825e4fc39a8d2a0eb9ec724794442be28fee3af1759d3b0dc1f9047087",
        "cc1afd21c39ab3aed598b1d7f469200f0c8cfff2a9a1441a3147a8b72ee10286",
    ),
    "variable/mirror_wings/wide+fast": (
        "28e28aa569dfe402687b23f53fb5a467ea9a3c8d0de520186e848e97a61f2b30",
        "19c35fa78f034db31d16242220fd0d6009008896b3ca2b11e462d6448b277152",
    ),
    "variable/mirror_wings/wide+slow": (
        "862138c5285d48fb27336d156b6053019b0cb66e4f9df86fdba57e5d5e400bb1",
        "d42e353647063d8e8ad3c4936fcbbd5e3c21a242ecff2363dfdf13dd776b50c1",
    ),
    "variable/target_orbit/fast": (
        "3d9902e036c106c94f5b61f15d7a28556db84dfe2562f53e9e0863aa81bfc7fc",
        "7f4ca6832f012f0540590242a81b24d1f94a762d0bc68e84c0260edaf9ebb3a7",
    ),
    "variable/target_orbit/narrow+fast": (
        "fcd410408064e492828bb95639812459fba2356a0036bd84808fc970a285abd1",
        "96e54669a020381c11c0b080af9364f6e61101f3150eb47121b92e32d83c0e88",
    ),
    "variable/target_orbit/narrow+slow": (
        "25cc3ea9e6ffc077272b865f8b3ea2d8a67c3440b4614f16e40c30ad94d2bdba",
        "c76a442fcfab75c97fe5b7a9369922c33b4227b1df12cb88fbc2ed10e406a12b",
    ),
    "variable/target_orbit/wide": (
        "1d4f3cb327541f29653950afe756061574434dbe11db431ce72638cdc112b0f4",
        "7e7221916d9f8fbf90b3f66e11b9a5b0d4f3545944923b916fa6c341e0b13134",
    ),
    "variable/target_orbit/wide+fast": (
        "c6a6d5dee8d01a42eeb7646811bac0ed072cf8f07fa32bed3db916b9b684e9ac",
        "da81376c87f194cf1e7249511f0788411854efc51526f87f923dbac9c9ebf193",
    ),
    "variable/target_orbit/wide+slow": (
        "430948613db0390c3054cbef0cb59204081893385feb5b462b7fa4df0eb87165",
        "42ea5df862fc884a4442023a9b798ed5d367d0dd85db6492817d0733292ee9f6",
    ),
    "variable/zoom_wave/fast": (
        "837be9f90fe1d8887c0399e8d4e54438e5e9af8e97b9b71a38e32ccfe85d1271",
        "fb4a81f1a672cf767191b3a674323caa60ac7c4ab08d4ef138dbe410a91d0bad",
    ),
    "variable/zoom_wave/narrow+fast": (
        "7021570a53b3a5f305386d7b61f11c54afc5bf92887383066a1ae85805172e65",
        "4667c2393e6bde7ba73ccc8427d6501ddf975f675d4af3e065322ad18f2640ca",
    ),
    "variable/zoom_wave/narrow+slow": (
        "9a969eada6d871e1b6172eaeeab96a18f9beca5a6697751b8672e8eed7b53390",
        "e35eec0d1c0b3554429c7b42e71740016941caff8cb3513d68973c55a583df52",
    ),
    "variable/zoom_wave/wide": (
        "cb842863c2c3a6fc857e8f62fd01cdea09f941df8fe05f78936cacf4adb107b0",
        "d1df17aa71942784b4715d6038237f6e5e36cadde3cfd06f39731140b8d90e9d",
    ),
    "variable/zoom_wave/wide+fast": (
        "6f24c762a1b501f301d8730df727728f002370d44c8ab7d8dab4a8d20257afad",
        "34eef86923bb6fa37a5ab762cf1375a203ad0bb931dcc75d94e72af86477945e",
    ),
    "variable/zoom_wave/wide+slow": (
        "4d5827cc47150362b97c15c1d0394665e43adb0448dbbebf10bada7b198206af",
        "f16960235d17895270e5fd05bd8b0bd6ab2abd81292bec177b0a68cf9443764b",
    ),
}
"""`grid/template/variant`: (render fingerprint, SHA-256 of the encoded frames)."""

MULTI_PIN = (
    "170d6e65dbdb627abf00556817727e128ddb1f3945e0e060421c06f108a878f2",
    "3ea6b3fca42f7ea4bbed6068c580331ce3649c6ef4c49f77f7b23fff7599fba7",
    "9ef5b7a162ca49079bb1a5261223b9ebcd399f8b7bb48463942ba4271861c6fb",
)
"""The multi-section plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256)."""

MULTI_SECTIONS = ("mirror_wings", "target_orbit", "finite_snap_hold", "fly_in_cascade")

GATED_PIN = (
    "50f70cae43d478d62f1c9c8aa1f6b29e3433bdae0331503f55adfcd8448e59a2",
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
    "9ba22940451392b2cfdc3c8e41edd3c6fd4ae5d1959e5cae2580d69fa3766b57",
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
    "08a0b82cc7cb21c3e7b43a5eeb43b8f04f7aeb4c64c69f7da7c9cf6f0ced2ed7",
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
        "6bbbfeb06c41f071f3a9919da0569d636abe5c7c84af54fdd8c751de03d849eb",
        "448dd5edb8649aa4e4a1d31725c6de92a9e1d8d3be740297a0de11dd76a8c57a",
    ),
    "headroom/intensity_half_hold/DRAMATIC": (
        "2300bac1a878ce006a936ba64442829dc76d6fe7fc5eed0f8d241ae0925d4c0e",
        "13d0f907cfcf370c2e250c959632c3a7ce26d446b11afad12082f1748bc10e0d",
    ),
    "authored_pulse/intensity_authored_pulse/INTENSE": (
        "8e9012ee5981d2e04211d24b561a11a373d3d9f74dfb8014f7cda204311b5d83",
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
        "3db58ce984ecc52ad455308caa6b1ec3206a12564a461dc1a76120ab378ae765",
        "325f3945dfca1082d2d52dda9e22aad57330cd50c15123fc97663683dfc89358",
        "2607e56ef3f1883d9da4c136e05dcfbf9ce3fc8ee46480c0fc75edf6aa623a9d",
    ),
    "tagged_strobe": (
        "af26d70f6d38566fd77d2bbb99335cdae879cd7137f542ea575bdbdcecb01dd7",
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
        "f904a954122d9c3f75f8707efe7feabe161e718e37ecfcb2d6ab0a79067f9071",
        "48a5bc7d737f3495c8cbf9a50fa9e29cad900a814d499da01e4bbca09787c371",
        "5650779eacdca88b2594039ce5888d1cb86d78916501f81793329ff24b02af54",
    ),
    "lit": (
        "239e56751e831185522ffb3576435cd339843a192036e6634b092b39cb92083d",
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
