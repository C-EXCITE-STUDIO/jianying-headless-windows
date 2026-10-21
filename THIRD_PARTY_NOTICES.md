# Third-party notices and provenance

This source preview preserves provenance. It is not a claim that all files,
schemas, techniques, external libraries, or generated videos are original to
this project or covered by one license.

The project's original contributions are licensed under the MIT License in
[LICENSE](LICENSE). Existing third-party notices and permissions remain in
effect for their respective portions; this project's MIT grant does not
relicense or restrict the upstream MIT / Apache-2.0 materials.

## pyJianYingDraft upstream and fixed Windows fork — Apache-2.0

- Upstream: <https://github.com/GuanYixuan/pyJianYingDraft>
- Exact version license: <https://github.com/GuanYixuan/pyJianYingDraft/blob/0.3.0/LICENSE>
- Copyright 2024 Gary Guan.
- Full retained text: [licenses/pyJianYingDraft-0.3.0-Apache-2.0.txt](licenses/pyJianYingDraft-0.3.0-Apache-2.0.txt).

Earlier 11.x project adapters directly used this package to construct text
objects and inspect media. The Windows draft builder now directly imports a
fixed source checkout of the separately maintained
[aoguai/pyJianYingDraft](https://github.com/aoguai/pyJianYingDraft), commit
`2b6ed48b0f096e5a76a5b8a68a6d7d233defb463`, plus the two source patches
under `third_party/pyJianYingDraft/patches/`. The fork retains Apache-2.0;
see [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt). The setup script
downloads or reads that fixed source, checks the patched file hashes, then
installs it into the user's local virtual environment. Neither fork checkout
nor installed Python package is bundled in this repository. These facts do
not constitute a clean-room originality claim.

## jy-draftc macOS sample — MIT

- Upstream: <https://github.com/wenshui330/jy-draftc>
- Source interface: <https://github.com/wenshui330/jy-draftc/blob/main/jy-draftc-mac/jy-draftc-mac/EncryptUtil.h>
- Copyright 2026 wenshui330.
- Full retained text: [licenses/jy-draftc-MIT.txt](licenses/jy-draftc-MIT.txt).

`bridge/EncryptUtil.h` adapts the sample's method declarations. The project
codec implements bounded file/pipe handling around those declarations. The
underlying encryption/decryption implementation is supplied by the separately
installed Jianying application; it is not implemented or redistributed here.
The MIT notice is retained; this release does not remove attribution by
renaming the adapter or mechanically rewriting code.

## Existing project implementation and native structure captures

The current timeline builder, editing/export wrappers, tests and speech-plan
helpers were developed in this project's local workflow. `bridge/runtime_io.py`
is a mechanically selected subset of the project's prior native IO helper;
its source hash and included definitions are recorded in
`bridge/SOURCE_MANIFEST.json`. No independent clean-room provenance is claimed.

`engine/blueprint.json`, `compound-blueprint.json`, and the resource catalog
contain sanitized, experimentally observed native structures and identities.
They are compatibility data, not a distribution of the editor, original source
media, native effect packages, fonts, bookmarks, or account data. Home-relative
paths replace the capture machine's personal directory. Native resource IDs,
hashes and observed usage restrictions remain intact.

## Jianying Professional — proprietary external runtime

Users must separately install the exact supported application from an
authorized source. This repository does not contain the application,
`libvideoeditor.dylib`, Windows `videoeditor.dll`, its built-in resources, or
an application installer.
Calling internal interfaces is not equivalent to using a documented official
SDK or obtaining integration permission.

- User agreement: <https://lv.ulikecam.com/clause/agreement/pro>
- Material license: <https://lf9-cdn-tos.draftstatic.com/obj/ies-hotsoon-draft/faceu/Commercial_Material_User_Agreement_Cn.html>

Licensing project code does not grant rights to the editor, override the user
agreement, or establish commercial/redistribution rights for native materials.
Private storage and successful rendering are not legal clearance. Native
material availability, account entitlement, permitted use, and integration
authorization must be assessed separately before any relevant use or release.

## FFmpeg / ffprobe — separately installed command-line tools

- Upstream and licensing: <https://ffmpeg.org/legal.html>

These executables are invoked for media inspection, audio analysis and output
validation; their binaries are not distributed in this repository. Their
applicable license depends on how they were built. The development environment
used a GPL-enabled FFmpeg build. If distributing binaries or changing the
integration approach, review the actual build and its separate obligations.

## fontTools 4.60.2 — MIT, optional external dependency

- Upstream: <https://github.com/fonttools/fonttools>
- Exact version license: <https://github.com/fonttools/fonttools/blob/4.60.2/LICENSE>
- Package: <https://pypi.org/project/fonttools/4.60.2/>

Explicit local-font assignment uses fontTools to parse font metadata and
tables. Install it separately using [requirements-fonts.txt](requirements-fonts.txt);
its package, font files and binaries are not included in this source preview.
Default builds and existing snapshot verification do not require the parser.
The project license does not replace the dependency's MIT license or grant rights
to font files supplied by users.

## Openverse / Freesound 音效 — 各素材獨立授權

選用 `scripts/openverse_sfx.py` 時，工具會透過 Openverse 搜尋並下載 Freesound 的
音效預覽；本倉庫不附帶下載的音效。程式碼的 MIT 授權不涵蓋這些第三方素材。
每段音效可能標示為 [CC0](https://creativecommons.org/publicdomain/zero/1.0/)、
[CC BY](https://creativecommons.org/licenses/by/4.0/) 或
[CC BY-NC](https://creativecommons.org/licenses/by-nc/4.0/)；實際版本及來源見
每次執行產生的 `credits.md`。CC BY 與 CC BY-NC 有署名要求，CC BY-NC 限非商業用途。
商業用途應使用 `--commercial` 排除 CC BY-NC，並於發佈前核對原始素材頁面及署名。
Openverse 的彙整資訊不能代替對原始授權的查核。

## Python, macOS/Xcode and Windows/MSVC toolchains

Python, Apple's developer tools and Microsoft's Visual C++ Build Tools are
external prerequisites, not bundled assets. Their own terms continue to apply.
Optional ASR executors and services
are also separate dependencies; this repository contains no service key and
does not grant service access or paid inference permission.
