ReusableMarquee — Widget／Live Activity用の一方向マーキー

MarqueeTextは、長い1行の文字列を一定速度で画面左へ流すSwiftUI Viewです。
2つの文字列コピーを並べ、SwiftUICoreの非公開appearanceAnimationで1コピー分ずつ
移動させます。アプリ側のTimer、連続したTimeline更新、UIViewRepresentableは使いません。

この配布物はSwift Packageではありません。Sources/MarqueeText.swiftを対象に追加し、
使用するXcodeのSDKから生成した宣言モジュールをSWIFT_INCLUDE_PATHSへ追加する構成です。
独自のSwiftUICore実装や私有frameworkをアプリに同梱する構成ではありません。

導入前に把握する範囲
- 実表示の検証基盤はiOS 27.2 (24B5084k)、arm64 Simulatorです。
- ブリッジはXcode 27.0／SDK 27.0でSimulatorとiphoneosの両方についてコンパイルと
  実システムシンボルへのリンクを確認しました。実機での実行は未検証です。
- 非公開APIの導入OSバージョン、将来の互換性は不明です。
- deployment targetを26.0にしてビルドできることは、iOS 26での動作確認を意味しません。
- PRIVATE_MARQUEE_ENABLEDを付けずにビルドすれば、公開SDKだけを使う静止Textになります。
  OSに応じて私有シンボルの存在を自動検出する仕組みではありません。

ファイル構成
  Sources/MarqueeText.swift                  再利用するView本体
  Examples/MarqueeExamples.swift             Widget、Live Activity、Dynamic Typeの例
  Examples/MarqueeGallery.swift              任意のアプリ内検証画面
  Bridge/AppearanceAnimation.declarations.swift  復元した非公開宣言のみ
  Bridge/LinkProbe.swift                     ビルド時リンク検証用
  Bridge/NOTES.txt, VALIDATION.txt           ブリッジの設計・検証記録
  Scripts/build-bridge.sh, build_bridge.py   ローカルSDKから生成するスクリプト
  Config/PrivateMarquee.xcconfig             Xcode設定のひな形
  Generated/                                手元で生成するSDK別モジュール

1. プロジェクトへ配置する

例として、Xcodeプロジェクトのルートに次のように置きます。
  YourProject/
    YourProject.xcodeproj
    Vendor/ReusableMarquee/
      Sources/
      Bridge/
      Scripts/
      Config/
      Examples/

Xcodeに追加する本体ソースはSources/MarqueeText.swiftです。
Target Membershipで、利用するアプリとWidget extensionの両方にチェックを入れてください。
アプリ画面にViewを置かない場合、View本体をアプリターゲットへ追加する必要はありません。

Bridge/*.swiftは通常のアプリソースとして追加しないでください。
この宣言はSwiftUICoreというモジュールの一部としてコンパイルする必要があります。
Generated以下の.dylibやframeworkをEmbed／Copy Bundle Resourcesへ追加する必要もありません。

2. 使用するXcodeでブリッジを生成する

TerminalでVendor/ReusableMarqueeへ移動し、実際に使用するXcodeを明示します。
Mac上のXcodeとpython3を使用します。Pythonの追加パッケージは不要です。

  ./Scripts/build-bridge.sh \
    --developer-dir /Applications/Xcode.app/Contents/Developer \
    --sdk iphonesimulator \
    --deployment-target 26.0

--deployment-targetは、アプリとextensionのIPHONEOS_DEPLOYMENT_TARGETに合わせてください。
26.0は検証時の値です。ターゲットごとに異なる場合、それぞれの値で生成が必要です。
arm64のみ対応します。x86_64 Simulator用の私有ブリッジは含まれません。

iphoneos用のビルドも試す場合は別に生成します。

  ./Scripts/build-bridge.sh \
    --developer-dir /Applications/Xcode.app/Contents/Developer \
    --sdk iphoneos \
    --deployment-target 26.0

このスクリプトは、選んだローカルSDKの公開SwiftUICore.swiftinterfaceへ最小限の宣言を
追記し、同じXcodeでモジュールをコンパイルします。SDKのファイル自体は変更しません。
続いてリンク検証を行い、appearanceAnimation本体とopaque return descriptorへの
未解決importが実システムシンボルとして正しくリンクできることを確認します。
アプリのインストールや起動、実機への接続は行いません。

出力例:
  Generated/iphonesimulator27.0/arm64-apple-ios26.0-simulator/Modules
  Generated/iphoneos27.0/arm64-apple-ios26.0/Modules

各targetフォルダのmanifest.jsonには、SDK、コンパイラ、元interfaceのハッシュ、
使用するinclude pathを記録します。Diagnostics/BridgeLinkProbe.dylibは検証成果物であり、
アプリへ同梱しません。SDK内に必要なシンボルや期待するモジュールABIがない場合、生成は失敗します。

初回ビルド前に1回生成してください。アプリとextensionが並列実行する各Build Phaseへ
同じ生成処理を重複して置く必要はありません。CIでもxcodebuildの前に実行できます。
Xcodeを更新したら、SDK_NAMEが同じでも再生成してください。生成済みバイナリモジュールを
異なるコンパイラへ使い回すことは想定していません。

3. アプリとextensionのXcode設定へ追加する

既存の.xcconfigがある場合、それを置き換えず、includeまたは設定のマージを行います。
以下は、プロジェクトルートにApp.xcconfigを置く場合の例です。

  #include "Vendor/ReusableMarquee/Config/PrivateMarquee.xcconfig"

XcodeのProject > Info > Configurationsで、使用するapp／Widget extensionの
Debug／Releaseに、この設定を含む.xcconfigを指定します。includeの相対パスは、
includeを書いた.xcconfigファイルの所在に合わせて調整してください。

標準配置以外の例:

  #include "Libraries/ReusableMarquee/Config/PrivateMarquee.xcconfig"
  PRIVATE_MARQUEE_ROOT = $(SRCROOT)/Libraries/ReusableMarquee

PRIVATE_MARQUEE_ROOTの上書きはincludeの後に置きます。
設定ひな形の中に標準値があるため、前に書くとその値で上書きされます。

ひな形が追加する主な設定は次の2つです。
  SWIFT_INCLUDE_PATHS[arch=arm64] = $(inherited) "$(PRIVATE_MARQUEE_MODULES)"
  SWIFT_ACTIVE_COMPILATION_CONDITIONS[arch=arm64] = $(inherited) PRIVATE_MARQUEE_ENABLED

PRIVATE_MARQUEE_MODULESは、SDK_NAME、IPHONEOS_DEPLOYMENT_TARGET、Simulatorかどうかを
使ってGenerated以下の該当フォルダを選びます。独自の--output-rootを使った場合は、
PRIVATE_MARQUEE_GENERATED_ROOTもinclude後に上書きしてください。

既存のBuild SettingsでSWIFT_INCLUDE_PATHSやSWIFT_ACTIVE_COMPILATION_CONDITIONSを
直接指定していると、.xcconfigの値より優先されることがあります。$(inherited)を保ち、
生成されたModulesのパスとPRIVATE_MARQUEE_ENABLEDが最終設定に入ることを確認してください。
追加のOTHER_LDFLAGS、FRAMEWORK_SEARCH_PATHS、私有entitlementは不要です。

4. MarqueeTextを使う

  import SwiftUI
  import UIKit

  struct TitleRow: View {
      let title: String

      var body: some View {
          MarqueeText(
              title,
              font: .systemFont(ofSize: 18, weight: .semibold),
              speed: 40,
              spacing: 32
          )
          .foregroundStyle(.primary)
          .frame(width: 260)
      }
  }

パラメータ:
- text: String。plain textとして表示。改行・タブは画面上では空白に正規化します。
- font: UIFont。既定はsystemFont(ofSize: 17)。計測と描画で同じフォントを使います。
- speed: CGFloat、pt/秒。既定40。0以下、NaN、無限大では静止します。
- spacing: CGFloat、コピー間の空白幅。既定32。負数や非有限値は0として扱います。
- isEnabled: Bool、既定true。falseなら末尾省略の静止Textになります。
- respectsReduceMotion: Bool、既定true。Reduce Motion環境では静止します。

文字列が表示幅に収まる場合や空文字列の場合はアニメーションしません。
進行方向は画面左で固定です。RTLの環境でも流す方向を自動反転するモードはありません。
アクセシビリティには2コピーを読み上げさせず、元の全文を1つの静的テキストとして渡します。

サイズ・フォントの条件
- 親Viewは有限の表示幅を提案する必要があります。Widgetの領域、VStack内の幅、
  明示的な.frame(width:)などを使います。親が幅を決めるなら固定の数値幅は不要です。
- MarqueeTextの外側に.fixedSize(horizontal: true, vertical: false)や.fixedSize()を付けないでください。
  横方向の無制約ScrollView内でも、表示幅を明示してください。
- 高さはfontの行高と文字列の計測結果から求めます。通常は高さの指定やGeometryReader不要です。
- タイポグラフィはfont引数で指定します。外側の.font、.bold、.italic、.kerning、
  .trackingなどによる変更は計測幅と一致しなくなるため未対応です。
- foregroundStyle、opacity、padding、backgroundなど、文字寸法を変えない装飾は利用できます。
- AttributedString、複数行、開始待ち時間、任意方向指定はこのコンポーネントの対象外です。
- 文字列・フォント・速度・間隔・表示幅が変わると、アニメーションを先頭から作り直します。
  同じViewに古い反復周期が残る現象を避けるため、入力から生成した.idを内部で使います。
  更新前のスクロール位置を維持するAPIは提供していません。

Dynamic Type
UIFontは指定した固定ポイントサイズとして扱います。必要なら呼び出し側で拡大します。

  struct ScaledTitle: View {
      @ScaledMetric(relativeTo: .body) private var pointSize: CGFloat = 17

      var body: some View {
          MarqueeText("Dynamic Typeで拡大する長いタイトル",
                      font: .systemFont(ofSize: pointSize))
      }
  }

5. Widgetへ組み込む

Examples/MarqueeExamples.swiftに、TimelineProviderとMarqueeExampleWidgetがあります。
このファイル全体はWidget extensionだけのTarget Membershipにします。
MarqueeExampleWidget()を、既存の@main WidgetBundleのbodyへ追加してください。
例のために2つ目の@mainや別のWidgetBundleエントリポイントを作る必要はありません。

既存WidgetのViewへ直接使うなら、これだけでも組み込めます。

  VStack(alignment: .leading, spacing: 8) {
      Text("TITLE").font(.caption)
      MarqueeText(entry.title, font: .systemFont(ofSize: 18))
  }
  .containerBackground(for: .widget) { Color(uiColor: .systemBackground) }

Timelineは情報が変わるタイミングに合わせて更新してください。
文字を動かすための高頻度TimelineやWidgetCenter.reloadAllTimelines()の連打は不要です。
プレビューだけでなく、ホーム画面へ装着したWidgetで確認してください。

6. Live Activityへ組み込む

同じExamples/MarqueeExamples.swiftに、ロック画面と展開Dynamic Islandの例があります。
MarqueeExampleLiveActivity()を既存のWidgetBundleへ追加します。

MarqueeExampleAttributesは、アプリとextensionの両方が共有する必要があります。
例ファイル内のその宣言ブロックをShared/MarqueeExampleAttributes.swiftなどへ移動し、
移動先ファイルのTarget Membershipを両方にします。元の例ファイルからは同じ宣言を
取り除いて、extension側に同名の定義を重複させないでください。
既存のActivityAttributesを使う場合は、そのContentStateのタイトルをMarqueeTextへ渡します。

アプリのInfo.plistへBooleanのNSSupportsLiveActivities = YESを設定します。
開始処理はアプリ側で行います。以下は、共有Attributesを使った最小例です。

  import ActivityKit

  @MainActor
  func startMarqueeActivity() throws -> Activity<MarqueeExampleAttributes> {
      try Activity<MarqueeExampleAttributes>.request(
          attributes: MarqueeExampleAttributes(name: "Now Playing"),
          content: ActivityContent(
              state: MarqueeExampleAttributes.ContentState(
                  title: "START — ライブアクティビティで表示する長いタイトル — END"
              ),
              staleDate: nil
          ),
          pushType: nil
      )
  }

戻り値のactivityを保持しておくと、タイトル変更や終了に使えます。
requestはthrowするため、呼び出し側でdo/catchなど通常のエラー処理を行ってください。

  await activity.update(
      ActivityContent(
          state: MarqueeExampleAttributes.ContentState(title: "変更後の長いタイトル"),
          staleDate: nil
      )
  )

  // 必要になったタイミングで終了する。
  await activity.end(nil, dismissalPolicy: .immediate)

updateは内容の変更時だけで構いません。マーキーの各フレームをActivity.updateで送る
必要はありません。例のcompact／minimal領域はアイコンと識別文字だけです。
マーキーはロック画面と、Dynamic Islandを長押しした展開領域へ配置しています。

公開SDKだけの静止版でビルドする

PRIVATE_MARQUEE_ENABLEDをコンパイル条件から除外し、私有モジュールのinclude pathも
追加しない構成で、Sources/MarqueeText.swiftをそのままコンパイルしてください。
例えば、私有ブリッジ用.xcconfigをincludeしない別の構成を作れます。
この場合、ソース内の私有API呼び出しそのものがコンパイル対象から外れます。

isEnabled=falseやReduce Motionは表示の停止だけです。私有APIを有効にしてビルドした
バイナリから、そのシンボルへのimportを取り除くものではありません。#availableで
分岐しただけで、未検証のOS上で安全に動くと考えないでください。

よくある問題
- appearanceAnimationが見つからない:
  appとextensionの両方で生成済みModulesがinclude pathに入っているか確認します。
  ビルドに使うXcode、SDK_NAME、deployment targetと、生成時の値を合わせてください。
- ビルドできるが静止する:
  PRIVATE_MARQUEE_ENABLED、文字幅、speed、isEnabled、Reduce Motionを確認します。
  extension側だけフラグが入っていないケースにも注意してください。
- フォント端が切れる／継ぎ目の幅がおかしい:
  font引数以外で太字・字間などを変えていないか、親の表示幅が有限か確認します。
- bridge生成でSDK symbol不足／重複宣言と表示される:
  そのSDKのAPIを再確認する必要があります。検査を外して無条件に生成しないでください。
- Xcode更新後にモジュールが読み込めない:
  そのXcodeでbridgeを再生成し、プロジェクトを再ビルドします。
- OS起動時に私有シンボルを解決できない:
  SDKでのリンク成功とランタイムのAPI存在は別です。確認済み環境を使うか、
  PRIVATE_MARQUEE_ENABLEDを外した静止版としてビルドしてください。

配布・再現性
Generated/にはApple SDKからコピーした公開interfaceとコンパイラ依存の生成物が入ります。
配布ZIPやソース管理へ含めず、受け取り側のローカルSDKから再生成してください。
元のSDKファイルやシステムframeworkを変更する手順はありません。
詳しいブリッジ設計はBridge/NOTES.txt、コンパイル／リンク記録はBridge/VALIDATION.txtを参照。
UI検証の記録は、この配布物のVerification以下および元の検証プロジェクトに保存します。

今回の最終版で確認したこと
- iOS 27.2 SimulatorのホームWidget、Live Activityのロック画面と展開Dynamic Islandで左移動。
- ブリッジON／OFFの両構成で、本体とWidget／Live Activityの例がコンパイル・リンク成功。
- iphoneos向けもコンパイル・リンク成功。実機での実行は未検証。
- タイトル更新後の60秒録画で、1秒ごとの全60区間が約40pt/秒で左へ移動。
  入力依存の.id追加前に見つかった周期境界の文字飛びは、この録画内で再現しなかった。
- 実際のOSのReduce Motion設定で静止し、設定を尊重しない指定では移動を継続。
  検証後はOS設定を元に戻した。
- 同期計測・停止条件・文字列正規化の27項目に合格。
各表示面の記録、修正前データとの区別、検証の範囲はVerification/RESULTS.txtを参照。
