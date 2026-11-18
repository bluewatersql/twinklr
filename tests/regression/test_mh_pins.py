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
        "5221f0fe455c419c2854ee776070b5bf0eb3eb14f49b8f7ebff557bae9dde632",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow": (
        "26d463d3766d1bd88dda511637488a7f9805894af9f87dd80a45be964a236098",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/slow": (
        "de10eaa64a895d5563bcd88767a519c53d552afd1783536fe2dcef735244a9a3",
        "4d455965979b705ad9af8136e4fd229c7b5374635e1786d07b8cab7636861b9d",
    ),
    "steady/fly_in_cascade/base": (
        "159e7791e17555353c50a822e84ac9af7152fa27bab7974aee3fa441c7bef79a",
        "ffdfb044c11edf3040dd81744d17558a2d46c21181071367cca5f752a8413b0d",
    ),
    "steady/fly_in_cascade/narrow": (
        "6e0cbd6a834aa0d88059a60cefb789a6c7d5d46de53f370f03ad166ae09f8e40",
        "0280d85aaf1e832fc23b428e311b24ccb67dac720116f25f71d147261f88f310",
    ),
    "steady/fly_in_cascade/slow": (
        "e1b08f0fa8ba5d03f45e466903a0c365a1d25462d2e9801e9a93a2860bd8b11c",
        "dd49563a5956e1e52f4a2c01e8f005a64a297ff28f9155f3eb05d10a29312433",
    ),
    "steady/fly_out_cascade/base": (
        "4fa01a350fc4e7fd4271b2e4a74f759168a16f812457d4908cd82946379d2925",
        "4235e01012dddfdae05f050fa904a9efa2e8eb4cf4f3b7e2ddd06b23951c733e",
    ),
    "steady/fly_out_cascade/narrow": (
        "049c71b6d98b2ca3454bb470d54dc2c669fa9ce9cd013d279b1574795b32e8b1",
        "150edd82e9273731bd9ab781ab5c6caf420cf5d1129cddb637915687dab01a88",
    ),
    "steady/fly_out_cascade/slow": (
        "e7f2d2c00e10f04d66bcfb017374aca05c3ac7d48be7210ba0e4b903fa853587",
        "c7e91342cab3b42a868f59ab824961da433ac89db0c5646f1fd41e29b0444a70",
    ),
    "steady/masked_wheel_flick/base": (
        "a52f6a01757b8123ebdd4d7c3354e5ce3de0640d399ece43a604b61050002b4f",
        "08ce9090980dbfefa79b6d78c90ef0f0b0c8ef3a19bb47d193d9af34805cd2de",
    ),
    "steady/masked_wheel_flick/narrow": (
        "e2c151ec8974738d7f388ed32079c7b0c1f2e97455a397ef8aed21ae65539f33",
        "2537e7e6cf39dad19aadb07a271b223f83c2af7fbbe52b4732f6416cee5993ad",
    ),
    "steady/masked_wheel_flick/slow": (
        "fd2728c477784c038209ea67b211162ad004eec75bbd3228108aa64a3f40d5bd",
        "56a758e57a37773c558bff6f8134843cf45c76d005021a6e882374d16d96431a",
    ),
    "steady/mirror_wings/base": (
        "38e72141f6958023261396f9ba4717987752cf3304959761440f4bfb87dff484",
        "8e3cb9be3de61f968b065d8d0442ac5551becdbbf4624afb76b13a58e0f000fd",
    ),
    "steady/mirror_wings/narrow": (
        "f325cda3500a5628b36c7b2f61b73b806888069a60fd6edfcd4226191ac48f75",
        "d83a23f4fea33e3e6f1b2bbfabdc0b5c26f605b673861c0021a1cc1c8bd36a1b",
    ),
    "steady/mirror_wings/slow": (
        "072a8635273de8a0013b00432b92ca55b8d8c73abc13c82c0cb66ec74f382a95",
        "bbcdbab3564fa3d0a7f107562326940ef92fa3f38130a37ac9d8b43f68bdd3b6",
    ),
    "steady/target_orbit/base": (
        "1a2b22f7b00f1c4a9f8d024540090f6d0a985c3a5228bd7e83aa8b4361c7f67c",
        "78d35ed327d359ca0cc456a151ae19f800a20b80ac1cc040ea4448be4d014ed1",
    ),
    "steady/target_orbit/narrow": (
        "f6e115c74020f6313b6988886bae6539a0b814955d0618632b4ed95fddb2a2c3",
        "a35e080540356862ecfe8738414c7cef0d781b639b869db97bc27ff0db5f180b",
    ),
    "steady/target_orbit/slow": (
        "3e7a2fdbf125cb81442634ec470954d5afced44ceda508d6bade29c6907db525",
        "a2eb0bf1f4d04307af57da96941f9d02e8c47ffcc583db3361b0a754975c7d36",
    ),
    "steady/zoom_wave/base": (
        "25f2fa55a6c6653a7e36aedf20ca74dc2a7f5f8d820064bf3639b84d518e44ec",
        "bfa3f5ef5efd80d8f801f76ab412044d35161bb606288fc35f6fbeaf6970675a",
    ),
    "steady/zoom_wave/narrow": (
        "e1848c2abac30f8c71d42a08426a452e3104fc61061383b5dc9631e9f1244dc3",
        "0ddc62b56b92e1af2deedbc6b9bf47570bbe82663ff559091f3883f32e20169b",
    ),
    "steady/zoom_wave/slow": (
        "7cd5f6832dcb9b46c8a0e6330026cd9b849a5483bd3a754b9dcde4b01bffe6c5",
        "394aa7ae9fb0cc8e948e2c1b68264b9652edbddd44bcefd9d5ac0dea8e5cdb2c",
    ),
    "variable/finite_snap_hold/base": (
        "f3787780ba4a9d818ff04e8cf72b5e8c02e8e69d782614a420fb2a18f316c19d",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow": (
        "82d60386127a9444a106cdf26aa9bfd4c0d623a3ab44ed86eb791f25736c850c",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/slow": (
        "e5b6df592d65ad61d40f45596e462d9c07372a9b16213c1ebbf9ec207fa09467",
        "e4f7f3d9a0863c4f423dae91e481e8874d5971308aa2196a93e6fca84a6d8930",
    ),
    "variable/fly_in_cascade/base": (
        "5e0c6b047e19809385b33cc51b8a8ab89690147d76ae62470daa1c32b7164756",
        "34f9987fa593584b7894352d13944905315dd6c260035971de447db3c121fd7a",
    ),
    "variable/fly_in_cascade/narrow": (
        "ec171de29005d38f7dce20217e0cfec06a28901d1c7be0114b1ee484d5f4352b",
        "f2d02f0c7cdbcda887bcd350188338a8bfe0ae583b2b5e092c64b921985f1a9e",
    ),
    "variable/fly_in_cascade/slow": (
        "1bdf4ba730e60d0ccb646ba0ad122711824a5967c310130a4c8a371151e04735",
        "49c484a8585d159fc61d0989eef1cc2a35fc22a5e46cf202f789736c8dd37ebe",
    ),
    "variable/fly_out_cascade/base": (
        "ac9cfce6bad86ee188a65e716b95100831eb58fea0b9686146b1a9a09e5a779e",
        "36f29b21188085c76c462a8cfd73f3e10f21f7adfdbca525a674c4960aca28d2",
    ),
    "variable/fly_out_cascade/narrow": (
        "cb08aaed146b7b91b78c48dff15e50e6bb3e1b7e212a0f2dbb6452eccd65fe3a",
        "c773f3be51097dd3ec2c309f6149f76e6c3bb7f6d1ea24416aba4662a10cb420",
    ),
    "variable/fly_out_cascade/slow": (
        "d4bc3fa0922e6c4ffa907025f09514df0bdc99d30a0e39af26068de21cde0e57",
        "de6e5fb69f6beeeb43df051367101bd88d3d75b61e811bab2ac3e69d2edd499a",
    ),
    "variable/masked_wheel_flick/base": (
        "c77fc8e3b1bd608eb8660d7fb01fbf040aa8383d5d1e8e80e6817dcbeec8922c",
        "a628fb0ca672aba2a7c36e3ecfafcf1003b8d9c8a06adc5edcf0840004981f3f",
    ),
    "variable/masked_wheel_flick/narrow": (
        "08d43e8387718cea52c6cc533e2be3b20fffa3e751b98e5c724e94205fd78bd1",
        "a8b2c6b2cf905f657c6993dca020c6aa14bbfacc10f89bfb97491860bc81a6c3",
    ),
    "variable/masked_wheel_flick/slow": (
        "928f71967f2a3dc377c75287a11b186c09becdff379c95560e039f9e0bfdc515",
        "058ed1d9cbdde981fa5213dd23654d42fc86a9ebd6150fc50b089e07f85825f8",
    ),
    "variable/mirror_wings/base": (
        "7c4c2da72ebdedd0d9fd6a38f7ec50779d4492b2e0e314e7569498f89700f3ba",
        "a59b343515d159c1603c1a0ed576afa3b6721178a643ad1c5fbc02d6bb706dde",
    ),
    "variable/mirror_wings/narrow": (
        "a9219ef38cb1fbdc5b4d1e39ecf297b79e1a7231bf9d7a20dddf3e14fa0203e0",
        "4d326471bc6af0e6f429bd8e5d5b7e374587d3f545a2fe3d2ad3ef908ab6f801",
    ),
    "variable/mirror_wings/slow": (
        "87b72ba338503ce93888eb58708ae3a9bd1c042faa84efb3c012904c9b11dd15",
        "cee179ea21422e5e6f268664dd79981055afedfd98c5849c5dbfd44f5b80904e",
    ),
    "variable/target_orbit/base": (
        "02d067cd3befe13b11bb5100160a8b3f60088237983217b15b403c92b905252c",
        "2bfe8b5bd75f0097dd6fb8011e38a11578764984050474ddf0ee402ae3c85fa1",
    ),
    "variable/target_orbit/narrow": (
        "8f3469416cd06c098e5590f5f649a69d2ea7c989deb7d2778335d903fe0c7dc7",
        "9f453dce2badb89d745c808896a8fe6d3b9feafacf5d122371d75d0a6377b4a6",
    ),
    "variable/target_orbit/slow": (
        "a146776943901d7ea3f57880547abd683c7cff9058a88976342d18c3a9dbcdc9",
        "ac930585ef5e3f15f79cc7267d407f586e99f71923c67b287415b69ec32365c5",
    ),
    "variable/zoom_wave/base": (
        "8afc54ffca4559a4c7ec659130ccbd47dec5ec8b8de80ab53ecff17f23fb0304",
        "0020b12393f7dd4cf89bb4c4bbf3cd942ed5aa0de2abde665b3caffefdc751a7",
    ),
    "variable/zoom_wave/narrow": (
        "21c7d9f234dd29288491408f398e7127d0132a00f2c0eceaeec228c74eebb041",
        "a39df6ddbe83086edd4664152946711a1b5a24a927837fd366218594215ce44a",
    ),
    "variable/zoom_wave/slow": (
        "de5b46b979a837a45228643581123541f37917797d449f01ff556dd0d9d88c58",
        "503a36b0d6d9b85cfa6e5518367e787f835571fbc02f9f44e09f96f2c6689561",
    ),
    "steady/finite_snap_hold/fast": (
        "e784be831217c1dd8285911e8eea611b7d0cb59009a0f42b5aa715809ae84db0",
        "8dc76627bbfb3e4e0a170d097e491277cdb571b09c41198381db8cbcc374e120",
    ),
    "steady/finite_snap_hold/narrow+fast": (
        "8ccdf7cbe6ba1e8d4c2f4f25faf1eed826fd2ab8523d98a44e6ae5209ccb0857",
        "c0d8292c375a952740fbbb4fdec44ca69ed99c1bc90decfe2f2f22b57387ccce",
    ),
    "steady/finite_snap_hold/narrow+slow": (
        "3c2763e31088313f910cdbb4f3924da7e0e28fd879ce140119f8e882fa3a24b9",
        "84296f1bd1d0c1616da22afeecacfd8e2653b25a47e68272bba162023e8ed304",
    ),
    "steady/finite_snap_hold/wide": (
        "627838f70708322c397d5e2734a56f7f5b097eeaf135f1130c00e37423dfc7aa",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+fast": (
        "8ea98fa2507d3c483e7ea45414d1ede0c0e13b911cb4a149be8fd180d8708894",
        "4016eea0a821273c61cf1fa51048da22b5652aab29a7df78c75269c5dc9c85ff",
    ),
    "steady/finite_snap_hold/wide+slow": (
        "85680d7ab87cda8d1597d96b4e16c86c7d0e82733591038fcbe685de518d693c",
        "9f9ddc3e26639bc1c0d79680d8363004b5817b974d67286d8edca8e459848bce",
    ),
    "steady/fly_in_cascade/fast": (
        "c944cae00912df1be107421d6c13486b5e1ff9c3d48152569e0bf3d320dbc20b",
        "1a39008b463ea6e6e8aaae5119af1676e82017712e0ecec42606e526fd9db2d4",
    ),
    "steady/fly_in_cascade/narrow+fast": (
        "2df2db5e9daddc09abbb5f34fb908e23391460c5a7dd11ded6323f6ff83a2caa",
        "bef2eadb974023db7f86422e5dc581fdb3eb86a9f391ae5c569949528763b568",
    ),
    "steady/fly_in_cascade/narrow+slow": (
        "b41607fd814a98709fe3b7117fe11f16b82ef44ac126804e02e696802095630c",
        "f3d783b88c9fc99c3c06cbf2d0e540fe69cc923428f37294400a6beb3d3bb589",
    ),
    "steady/fly_in_cascade/wide": (
        "a7f9936bd6b157e1d2c429e3c195c523f79cdd495a7c9780f52d99e599d11822",
        "8d4615bd8a8f8267488e4f32055abc94facf5c38404bb1aa295c5e31b6a05a48",
    ),
    "steady/fly_in_cascade/wide+fast": (
        "4b1f7ceafd036f73637858d39dd3a16fbf7f5748feb2ca97081fb1262651d9d2",
        "2a29a810de1938502c6c9d8c1450f4b7902f587de543129aa538f419c5d908f9",
    ),
    "steady/fly_in_cascade/wide+slow": (
        "e2a653bc28fa565df1b0eacd8d91a9c192310d4656649009f49ad28cf0d59f3f",
        "ce3a2cd0bbe40c0eb7037219459d5201beb4914ae7a06bbd7f2a7f4c6df79343",
    ),
    "steady/fly_out_cascade/fast": (
        "0d75362aa6936b5e157e8ae3dd94a99b9e04dd30835c9d81d36944c0616e1eca",
        "9bd7bbc96f5edea525cfaaa0b3671dff06056e8f96934baac3128d3c277bc437",
    ),
    "steady/fly_out_cascade/narrow+fast": (
        "3a0563eab2044729c40af18a89bc0b4af844d4f3dc5e07be02cb059b145a61cc",
        "ea055d37932acdc69bd56640b74050741cfec611d3caffb4e5df24044879f1e1",
    ),
    "steady/fly_out_cascade/narrow+slow": (
        "8425e753c108bbde75de51731ffb27824a107e4d963483ccfe7cc6798c46b296",
        "ac661a02d9502c30de8e04fd79afc6546368a6ce41a0e8a3855007e49ddee553",
    ),
    "steady/fly_out_cascade/wide": (
        "e9e029c3c57976af9e0c2738be769e0c684f4b3c721f1dab27f3a6a8209c1f41",
        "5dea8d5716164cafab9c6f2ae54ec7c3854f8737b927936edf50d32059134379",
    ),
    "steady/fly_out_cascade/wide+fast": (
        "3e2c77e18fed80fd193964dc754c8cd3d3516f2df7ac6f4d0c2e20c19a9ad2d3",
        "9eac67a83c21237ea0d41f09d90d3ce1174c6ba4fd0c237292cbc07e9b5a072a",
    ),
    "steady/fly_out_cascade/wide+slow": (
        "6e237945aa1781a6cea99d2a9845d8626e3cff35a7d06da0291e4e850d72bedb",
        "fb9d420703dc0f52f8e319bd479a35063bd40e49fedf2ee61503ed95991251fb",
    ),
    "steady/masked_wheel_flick/fast": (
        "529d6aef89775d17037a113a93cac911d6480cb63d2178dee5e185fe2e48994c",
        "e82432d2c5316dd24833f6459d703aee946e7519bf58f946df24373c9a0db2e9",
    ),
    "steady/masked_wheel_flick/narrow+fast": (
        "36fed07cda690e76ec9e192fd1f5d04a9357903c8b54ea5347c7f6c1d8e0a319",
        "63c6c553c067cd8dab2602fd548017803c24076bcf3f7549a022d7dfc9c73436",
    ),
    "steady/masked_wheel_flick/narrow+slow": (
        "6bc191d2f8f319b9ab4882822b1b9d19f110f20eb0d9efb7ae81010f741629ef",
        "982bff05eba5994eedec53718c022f3e126434825fa025087858e2320024b876",
    ),
    "steady/masked_wheel_flick/wide": (
        "93d962c3af4b6fea86362266618b7ca3242186539c2e4d3d599c9eacbfae98c7",
        "fe80354759a79a46b1b35cb901462e17f2693848d5adef051175a83708b32e35",
    ),
    "steady/masked_wheel_flick/wide+fast": (
        "e9155479f6b1bf801a5775388d4f23ff1d1a7013cd399b114ff039fa88a7f2e9",
        "dec3fbafa55e95e2957605f6c7ff2d32b1e21c3225486c8ed89a0b4a6f6c174c",
    ),
    "steady/masked_wheel_flick/wide+slow": (
        "d473c784340d59a0913769b4a9129247102e42e766900e9fec3bb16df009fb3d",
        "6fc8bfd1a4a336e340b34c323846f611ec217d96912ebcfabc3fe3a057422291",
    ),
    "steady/mirror_wings/fast": (
        "28a58cb0a26bb1b2cc93d8ff61064b5b0b0b9d527a88ee02c226aac15dd351cd",
        "b04447e6c2f1ee6e28ccd6a41ce4d75bcfc1b4675d8e58a508e8c37b0f5467ab",
    ),
    "steady/mirror_wings/narrow+fast": (
        "a89b021c07b201a9e5fb779248b7ac4884845784c7794a5ab58d3e977ed87fcb",
        "858e7e61fec8a862058908f825f260ef85587958215b86174038e33708f45c34",
    ),
    "steady/mirror_wings/narrow+slow": (
        "a7f4016d06f787bdb474ff9abb36562bb6478b8f3cccccca64f1997675beed08",
        "c9c80c5d0cfce4410311235ba71e84d526dcae441b6f54135cbb56f513a86807",
    ),
    "steady/mirror_wings/wide": (
        "4d3904e1f2b2754ec8f9c7e87f6157457eb3a664e6cfa7bb18d97eda70a2a36a",
        "9715d9199effed4b15e204f2f27cf3aec8ebf5c245c3e5b8b5f2ceef2f2117b5",
    ),
    "steady/mirror_wings/wide+fast": (
        "8ff27d02c2a244eb9218c2d17652fc342b681fe9d7225a7fe6e9b2cb859fdde1",
        "0ef196bb7d93b11450f7a536bdc5f073377ba4533f8d79c5ff2ab6a06c476932",
    ),
    "steady/mirror_wings/wide+slow": (
        "5c2f33b8795e664457dc5c19dfbcab481e3dff52074c7df003733bdfdd8e6919",
        "99431146cf259e92d77022165a8323836dd37c9885d714fcafb95da7e86d7274",
    ),
    "steady/target_orbit/fast": (
        "a3a025f3e779b0244f36f3adb5afca8a130d7cb7ee9e8e76125e123dcfdd0a8a",
        "43588bfac383601c9088ef39031958fd8e025b5e847e631def2ab0f1e0e5772e",
    ),
    "steady/target_orbit/narrow+fast": (
        "38f20470b2b4da5da9a2b3c7678c4a97d7589a304bbc4fa096ece71a9513eb7b",
        "1308c094876095344e7b83a646161634527d693d0bbffd072694b8ac2bac6ec9",
    ),
    "steady/target_orbit/narrow+slow": (
        "28d405e77d7374b208789698de78939fae464b0fead69140ff104ea1660568a1",
        "d241150b19082d05439a15e5450c356734efff2b4b69be935feb1c4eacaeca1c",
    ),
    "steady/target_orbit/wide": (
        "06eceb8ec71d8ac9478a8acdfa353507f1a5d215ba8700e8b9184059c4f8c3b7",
        "f97441a2cc0a824180f87a72bc39c631079d3fe6a85297d8938a2b79561024e4",
    ),
    "steady/target_orbit/wide+fast": (
        "a8cfa33f11dfac8eb8811822ac99595d026f196bce2687e2b3c4a02df5664691",
        "31d0923d2ad78ee5cbb7d7d13b000ce03ab70bea35be0b36610d62318a4eec2f",
    ),
    "steady/target_orbit/wide+slow": (
        "e25fa42e90a8f4efe94f5e06673fa7daae950ebbc2281908425c45f6e201d797",
        "a1773507c0ac1e2e78a45c45bf2b812a6a11d592d8a0a374d5e55bd604cf5aa4",
    ),
    "steady/zoom_wave/fast": (
        "8e46ae70220329cabd6cb8aef2e28aebec2bd69b0d17be20e3f8f9ade7732824",
        "decd2e1c306dde507b609e631fb0a5113000ca10f54b215128dd27ca088d83c9",
    ),
    "steady/zoom_wave/narrow+fast": (
        "a3f4c627aa275b7832f489e4e0792707abd8dbbcf1bcbe86800e9ec570415915",
        "bf283a730211e848435d061c5091566c0cfa10885a0db9154e1a459eb86907af",
    ),
    "steady/zoom_wave/narrow+slow": (
        "a283f7535aef0cf215d9b773e809f7f5e69cf22918183cf6d68aa3e1f6cbca32",
        "aeb0df9cfc651c31a1ce6d8dbf26b9c9ebd409e5b20b10f333ea4148b7bee8e6",
    ),
    "steady/zoom_wave/wide": (
        "baa0fa85571f137bac5d87e36f97ecf0901095afc223a464568d3a45038a8d58",
        "15b4fc9c3700a8fc3bfafa975bd4500d7a01d5564b668a6565057ff5295e1300",
    ),
    "steady/zoom_wave/wide+fast": (
        "e1aab7863c207a1f2d62fe69cfbbce2db90e35685b834ccc5f25f318c543d79b",
        "f8f6fac7d49fd2434e88c82185793d11d43984ca97c1529c7082f03467c2b093",
    ),
    "steady/zoom_wave/wide+slow": (
        "22554e2f37c64e6eb28a3857a5315abcf99fe28b52e8cb0dfec5357b1b0d4506",
        "f7db8dacdd1e40012fabf8fdf188d11cc159381d49d2c3b4c0e1f4d7877bf6bc",
    ),
    "variable/finite_snap_hold/fast": (
        "1cefbb9a4f99a1bb4615bbe89f9b085c86ee4c130d2fe7406a98aa7fb21791b8",
        "d03e6f47159bc26621e835d36e191f370e0f90955ddac4b356afb477e613ba0f",
    ),
    "variable/finite_snap_hold/narrow+fast": (
        "3cdc1570049fe580381ad05ff1182fb4320fced2376675aef9d05f9337360a67",
        "9af804ac9d4aa9765aba26e095a80714399942811724696373cc015653545af6",
    ),
    "variable/finite_snap_hold/narrow+slow": (
        "f4ba7de50b16a2110e8fc8422eae21d7fbc1e5539c6401e3cc742fe282e98e29",
        "b9c51691943843d96703ad5935a75c5d3db1532f5cf571a576a5f77c68460612",
    ),
    "variable/finite_snap_hold/wide": (
        "7900ebbff2e34b4ab9b9d1208a0add610de58d92c245cc4dbbbd3f2aa6d35aad",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+fast": (
        "437eec697da0c404261cf085ee6af249d8f16c7e925be0186e07339aab8fc59a",
        "747b4dd15b6295637917548ad24022049a276a3a0edb6d138831334e18c81128",
    ),
    "variable/finite_snap_hold/wide+slow": (
        "c82d3431775d18cc251c3627525e5017ba6abb6f87ea242e1acd8c66889fd5a3",
        "230a61f4658fbe9efa21fbfc2acd10ab752aa33ae469105972e92dbc4ddaccef",
    ),
    "variable/fly_in_cascade/fast": (
        "011141e5b47013521ef7da57d32741d1e46e730dc35d7e32f6530b9603a0ee51",
        "270cb0b2b42c0b2ed0728b508ba0d03a491fbac14fe6dd585698a5057285c8f6",
    ),
    "variable/fly_in_cascade/narrow+fast": (
        "2f5651599f9550a6f993c37a27751ec90411da806e58ecc6113697eaa19bf276",
        "d04ca61a22765b4e997b2ba55df0b672926e2bbf36225e98e905448f6f3526e5",
    ),
    "variable/fly_in_cascade/narrow+slow": (
        "69c9ea48ba922c2628d4864d5d9330b5717d2fd9bcb8aebb53e5d1b774a80282",
        "cfaa353d2cdb1dede0a7b89aa16994d656281f1275beb55d206f438ba72b2e56",
    ),
    "variable/fly_in_cascade/wide": (
        "03f2f9bb038a861c5bcb6ec0de533cb978fa2ade98e74192f2f1f1fdc95f48a8",
        "52ac24a651637610dcef0daac29221b6066598a5b7b4dcb300471f60d1cfcb10",
    ),
    "variable/fly_in_cascade/wide+fast": (
        "44bc8ecb6425ee97a29a0ebd3a62d9c000e89b9b9778087e09edc8bdac4724cf",
        "7df58fab43506bab5845c90743ee60ef88fa5c8b950b08fa35dc7cf31c9b4ae8",
    ),
    "variable/fly_in_cascade/wide+slow": (
        "3c8e9c478cd80bdee6b9018c5d399e21114791ec88a2a048d42224659388b5bb",
        "ac07ebd59cc17d574998d69c3e821d770ea7887e00b6dec324530aeed2f2b366",
    ),
    "variable/fly_out_cascade/fast": (
        "fc747f2333f58c6e92e7ed77a8738ee5126004b88a0dbef4aa8bf00a0a4ef0f6",
        "819b97846f0da31760ebc1a5541ded84a2d53945af1c835795fac312bb3f8b7e",
    ),
    "variable/fly_out_cascade/narrow+fast": (
        "feaf226b708b3d1c10739607346af9642e4df0380e68ff463c50f4d857a2085f",
        "cc3dfd601cae5e3312b7c10c8a3a663e13b2dba186e85d76d6199b627adc244f",
    ),
    "variable/fly_out_cascade/narrow+slow": (
        "4ef58260c203dcf56c8f07af3e62d018be93cb0e90e1fe706bc504541409dfa6",
        "dd5792077b9c4c1d1886dcb96fc5865342d1453f2e5406dba700371a582ad577",
    ),
    "variable/fly_out_cascade/wide": (
        "dd2fc23d93746aa8909f4d28b70b88c6840021bf776fd8626524ee37b78759f4",
        "9074c99a5b6e8df580e9305a95fa13b29d8559440b6f70fb65478514b1c75040",
    ),
    "variable/fly_out_cascade/wide+fast": (
        "63833cf382c6d8a61c2ebfb9521af8d3afbefd8bb72189c993cff9bad50c69e9",
        "8b87e9c7b9aefac1611dc66d2a69ad6e4b2344f89e8f5c31baf668a64aeede3e",
    ),
    "variable/fly_out_cascade/wide+slow": (
        "748e828c0371186feeb9396f4b789f696b527d8c9ad4eb786d325ac2ea26cb2b",
        "2a8894551edf58b38e9cd52fdbe3c9a4acca8eecb1156889072b186cf4671fa1",
    ),
    "variable/masked_wheel_flick/fast": (
        "c418c98ff967281033fcd1e3e9f72a63350c9990c162cd085f60fc1a6cc53a4b",
        "d8e2e72bd956b89e026ada2c23bb85281000edf3ed1eba36a60d0c0aecf52515",
    ),
    "variable/masked_wheel_flick/narrow+fast": (
        "0e6e6f41109b3dc9b1152c0bd96858cd9b28a938d15a1c818a6e4d0d35229c79",
        "c1a3c12f6acd24a15aa1a9ba5d74bd28bee5810ffd3f5e0f3b1559ed2f174dfc",
    ),
    "variable/masked_wheel_flick/narrow+slow": (
        "c50cf624dc451b4e483795269237b3328fa0375ca35b566d0926ef297eddacfa",
        "2558a430925d7ad6d6842e3c9af969bffb27906fdedbd947c0ca9d1b453e0fc2",
    ),
    "variable/masked_wheel_flick/wide": (
        "1aeb4a3ecfdb44f487ec788336486608fb79d5f4de139755545df2c5fd017920",
        "535e039c6c26d6f78ab95f01c1aaac2c5fb26afec1e94cd2418fc546449cb7f9",
    ),
    "variable/masked_wheel_flick/wide+fast": (
        "e22a161c5e2d7c96ad9506214e13b738c3401e909d8fe89c03824de15bd55ca9",
        "346cfecaf2cb0c70ec1ec1cc0e73130a509ef456f106ee2cf0129a68af1dd906",
    ),
    "variable/masked_wheel_flick/wide+slow": (
        "0e39e6ee626ccefbebdca3ceece19d60b4fa1d1c41070dc3ad4660d87ef127e3",
        "2e85d5e91e07f289299a27c49b9431ddb807008575a1309bc51bd627489f48d7",
    ),
    "variable/mirror_wings/fast": (
        "4e400922f799f646de5da9fed4073a1923e1e4a6f25d910a861e188975843535",
        "97dfa43672eb9ff20f2499d975f7711f18f97076aac6e263b66ce50dc6a39014",
    ),
    "variable/mirror_wings/narrow+fast": (
        "1fd6e4c0b5277422e39eba6627eb19fc0fc6e7f690896d440f00515f32319d40",
        "788bb43aad21501da2d566fb34d09de7f8d69ff7a3103ed6a857c7576a11ad1e",
    ),
    "variable/mirror_wings/narrow+slow": (
        "9691727a275dac03cce248949bba94b86eaaa5917345398fc445096edef1915b",
        "0a557bade4807bf080b296be1a3fe68625c154163ffeeff55f3137fdb64d970a",
    ),
    "variable/mirror_wings/wide": (
        "a7d2ad4e48e4c66d21087d95fa4c91330a4dc6067e04c0bba4b30fd8f1d89633",
        "cc1afd21c39ab3aed598b1d7f469200f0c8cfff2a9a1441a3147a8b72ee10286",
    ),
    "variable/mirror_wings/wide+fast": (
        "10242620bc1f918a75e068a6b55d6aa22bf88e3d599968d1279219723fbfb400",
        "19c35fa78f034db31d16242220fd0d6009008896b3ca2b11e462d6448b277152",
    ),
    "variable/mirror_wings/wide+slow": (
        "fac5b28384b98451719698bad824516b8c905523db6f123bb9083c2b18bd5582",
        "d42e353647063d8e8ad3c4936fcbbd5e3c21a242ecff2363dfdf13dd776b50c1",
    ),
    "variable/target_orbit/fast": (
        "6afee8420bec62b7741835af9ca062ebdee3201a334eb9d6baa06b7eeedccaca",
        "7f4ca6832f012f0540590242a81b24d1f94a762d0bc68e84c0260edaf9ebb3a7",
    ),
    "variable/target_orbit/narrow+fast": (
        "c35e2aea718cca6e7c2b046ecbe2cb4bace8f8632f6486c1bdddd939aa54fdde",
        "96e54669a020381c11c0b080af9364f6e61101f3150eb47121b92e32d83c0e88",
    ),
    "variable/target_orbit/narrow+slow": (
        "172a533bd0eadb9af7fa2ba4315913f176bb0a57c5bd74b0301b7b5c0aacf332",
        "c76a442fcfab75c97fe5b7a9369922c33b4227b1df12cb88fbc2ed10e406a12b",
    ),
    "variable/target_orbit/wide": (
        "427edd0ba612ccb3ee551f2a9b6ad44c993ad4686fad06cc45049098a676cf0a",
        "7e7221916d9f8fbf90b3f66e11b9a5b0d4f3545944923b916fa6c341e0b13134",
    ),
    "variable/target_orbit/wide+fast": (
        "7b7ebc78cfb3208ed1fa6790da2713fa855f3b4e290a81f92fdae0c0a3756ab3",
        "da81376c87f194cf1e7249511f0788411854efc51526f87f923dbac9c9ebf193",
    ),
    "variable/target_orbit/wide+slow": (
        "e4109776c87aaac439e9475d36bb21e4ab53e58c73c175703219c5cf797e27d9",
        "42ea5df862fc884a4442023a9b798ed5d367d0dd85db6492817d0733292ee9f6",
    ),
    "variable/zoom_wave/fast": (
        "05f097e4f0c19fe3d817b65a0aa69222614cb4cda2931033574803606e302194",
        "fb4a81f1a672cf767191b3a674323caa60ac7c4ab08d4ef138dbe410a91d0bad",
    ),
    "variable/zoom_wave/narrow+fast": (
        "9d48445ad81cfece5bc1dbbffda55440675321f138c7a080a8b9123201c75abc",
        "4667c2393e6bde7ba73ccc8427d6501ddf975f675d4af3e065322ad18f2640ca",
    ),
    "variable/zoom_wave/narrow+slow": (
        "51111c4bc5d98cd62a23d1a2e03017b6ddbb5b11d85836cbae4fa99f10425f77",
        "e35eec0d1c0b3554429c7b42e71740016941caff8cb3513d68973c55a583df52",
    ),
    "variable/zoom_wave/wide": (
        "9d6ea964a8f848cfd4327bf185c5e37991cf7795ea2930f38c5e32d99a52ec22",
        "d1df17aa71942784b4715d6038237f6e5e36cadde3cfd06f39731140b8d90e9d",
    ),
    "variable/zoom_wave/wide+fast": (
        "10aab12380b23fa707ed373ff338d551d5d0e2e950668225e3d7a88617d1713e",
        "34eef86923bb6fa37a5ab762cf1375a203ad0bb931dcc75d94e72af86477945e",
    ),
    "variable/zoom_wave/wide+slow": (
        "d916ab2e2770720eecfa52cdddc0cfac24cbf4c56c53775306918011d4cf1aa4",
        "f16960235d17895270e5fd05bd8b0bd6ab2abd81292bec177b0a68cf9443764b",
    ),
}
"""`grid/template/variant`: (render fingerprint, SHA-256 of the encoded frames)."""

MULTI_PIN = (
    "cd85fb61081122a3d2aaa617685a6cfa4ca0750030a58497d2d48f9c6431c039",
    "3ea6b3fca42f7ea4bbed6068c580331ce3649c6ef4c49f77f7b23fff7599fba7",
    "9ef5b7a162ca49079bb1a5261223b9ebcd399f8b7bb48463942ba4271861c6fb",
)
"""The multi-section plan: (render fingerprint, frames SHA-256, delivered `.xsq` SHA-256)."""

MULTI_SECTIONS = ("mirror_wings", "target_orbit", "finite_snap_hold", "fly_in_cascade")

GATED_PIN = (
    "dfa3f2b95c3e9bbb1b46637028dfa13ecaf6719bc4147d258ca239fb58d0cb86",
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
    "1b8012ed32d9386d8fc65f679dc9bf8021352912a31f699294235fd891a8438e",
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
    "904d0b72d4af493ad2323bcccc5db4c54d3498865da1332a97076fb9587c7138",
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
        "d41e3a558e7abb887420cec9b9a0876355c08b3fc2d3f29e8c15fef39a074f80",
        "448dd5edb8649aa4e4a1d31725c6de92a9e1d8d3be740297a0de11dd76a8c57a",
    ),
    "headroom/intensity_half_hold/DRAMATIC": (
        "ccbb6b129dcab5898fcd2b676bea4e1cff832e2f5bf75a4dc4d79f465be0a2ba",
        "13d0f907cfcf370c2e250c959632c3a7ce26d446b11afad12082f1748bc10e0d",
    ),
    "authored_pulse/intensity_authored_pulse/INTENSE": (
        "686163e4953369fb670d384e100732fd12bab577e3e3e6430022e94b8d9f0eb7",
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
        "d30d6c8618eaa8adfcee869d94ba679273a0b4c58051ac1eae53af56b4eb98ac",
        "325f3945dfca1082d2d52dda9e22aad57330cd50c15123fc97663683dfc89358",
        "2607e56ef3f1883d9da4c136e05dcfbf9ce3fc8ee46480c0fc75edf6aa623a9d",
    ),
    "tagged_strobe": (
        "ff675d179d82b157d27316130888ea227dc84c1232e111aab626cc8ad50b5346",
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
        "779d84b227b21272181ed72b0d0617f637c05ff1eb49b340bc571d557e15492d",
        "48a5bc7d737f3495c8cbf9a50fa9e29cad900a814d499da01e4bbca09787c371",
        "5650779eacdca88b2594039ce5888d1cb86d78916501f81793329ff24b02af54",
    ),
    "lit": (
        "83d1f9fe06453b093f6c66090982a86d3ccebda31d68b67a4cdceff48e157efe",
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
