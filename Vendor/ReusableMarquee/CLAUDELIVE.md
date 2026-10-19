# ClaudeLive integration

Imported from the user's `ReusableMarquee.zip` on 2026-10-19. `Sources/MarqueeText.swift`
was initially unchanged from the ZIP (original SHA-256 `f9ca051838031e2ced482553c7bd09ae2ba76ce0555709d725c952dd0db99605`).
The local extension adds optional finite `repeatCount` and `scrollWhenFits`; both default
to the original behavior. Completed reply suffixes use two passes with a one-second initial delay.
The upstream documentation and verification notes describe the component's original investigation.

The iOS app and Widget share this source. Existing input, response and question marquees now
use its UIFont-based initializer with a default speed of 40 pt/s. The component measures its
own height, repeats continuously, and respects Reduce Motion. The older daemon's `textSettled`
updates do not stop it. Completed replies use a synchronous CoreText line split in
`CompletedResponseView`: the visible prefix stays in place and only the hidden suffix
scrolls twice. Font, actual width, available height and composed character boundaries
are used consistently. Compact tables are flattened without discarding hidden cells.
The other icon animations retain their existing rendering.

`Widget/Animation/ActivityMarqueeText.swift` adapts the surrounding semantic text styles to
the component's fixed UIFont API. It uses `@ScaledMetric` relative to `.footnote` (13 pt at
the default size) or `.caption2` (11 pt for compact questions), and passes that scaled font
to both measurement and rendering. This preserves Dynamic Type instead of fixing the marquee
at 13/11 pt while adjacent SwiftUI text grows with the user's settings.

StandBy uses the same marquee for questions (22 pt semibold) and for input and response
rows (18 pt), retaining its larger typography. Completed responses use the same
measured-prefix/two-pass-suffix behavior. Other rows repeat independently of the
daemon's `textSettled` flag. Inline Markdown in response previews is flattened before
measurement. Question answer buttons remain below the scrolling question.

Only these target configurations include `Config/PrivateMarqueeDebug.xcconfig`:

- ClaudeLive / Debug
- ClaudeLiveWidget / Debug

Release configurations use the component's static fallback and do not import the private
animation symbols. No bridge framework or diagnostic dylib is embedded in either product.
Generated SDK interfaces and modules are ignored by Git and must be regenerated locally.

Generate before an arm64 Debug build, matching the selected Xcode and deployment target:

```sh
python3 Vendor/ReusableMarquee/Scripts/build_bridge.py \
  --developer-dir "$(xcode-select -p)" --sdk iphoneos --deployment-target 18.0
```

For a Simulator Debug build, repeat with `--sdk iphonesimulator`. An Xcode update also requires
regeneration. No SDK files are modified. Runtime availability on older OS versions is unknown;
a successful build for deployment target 18.0 is not a runtime compatibility test.

Integration validation on 2026-10-19:

- Xcode's iPhoneOS 26.2 SDK: Debug and Release app/Widget builds succeeded.
- `nm -u`: 4 private marquee imports in each Debug binary; 0 in each Release binary.
- Neither product embeds SwiftUICore.framework or BridgeLinkProbe.dylib.
- Debug app installed and launched on the paired iPhone 16 Pro running iOS 27.2.
- The scrolling animation on the physical screen has not been visually verified.

Home-screen widgets also use the shared marquee for session names and summaries.
Completed summaries use the finite overflow presentation. Branding and the manual
refresh button are omitted; cached/offline state is still labeled.

Reply sizing has no default line cap. `ReplyPriorityLayout` measures headers and
usage first, then gives replies the remaining height; short replies shrink naturally.
The lock-screen card uses a 160 pt total budget. Home-screen session rows share
remaining space, reclaiming unused space from short rows. The Watch Smart Stack
uses the same measured overflow component and scrolls names/questions/progress,
with movement disabled during reduced-luminance Always On Display.
