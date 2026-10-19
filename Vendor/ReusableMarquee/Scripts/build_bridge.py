#!/usr/bin/env python3
"""Generate a local SwiftUICore declaration bridge and verify real-symbol linkage."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


FUNCTION_SYMBOL = "_$s7SwiftUI4ViewPAAE19appearanceAnimation9animation8strategy8modifierQrAA0E0V_AA010AppearanceE8StrategyOqd__x_SbtXEtAaBRd__lF"
REQUIRED_SYMBOLS = [
    FUNCTION_SYMBOL,
    FUNCTION_SYMBOL + "QOMQ",
    "_$s7SwiftUI27AppearanceAnimationStrategyOMa",
    "_$s7SwiftUI27AppearanceAnimationStrategyO04withD0yA2CmFWC",
]


def run(command, *, capture=False, environment=None):
    return subprocess.run(
        [str(item) for item in command], check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=environment,
    )


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--developer-dir", type=Path,
                        default=Path(os.environ.get("DEVELOPER_DIR", "/Applications/Xcode.app/Contents/Developer")))
    parser.add_argument("--sdk", choices=["iphonesimulator", "iphoneos"], default="iphonesimulator")
    parser.add_argument("--sdk-path", type=Path, help="Override the selected platform's SDK directory")
    parser.add_argument("--deployment-target", default="26.0", help="Must match the app and extension build settings")
    parser.add_argument("--arch", choices=["arm64"], default="arm64", help="Only the recovered arm64 ABI is supported")
    parser.add_argument("--output-root", type=Path, default=root / "Generated")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", args.deployment_target):
        parser.error("--deployment-target must be numeric, for example 26.0")

    developer = args.developer_dir.expanduser().resolve()
    platform = "iPhoneSimulator" if args.sdk == "iphonesimulator" else "iPhoneOS"
    sdk = (args.sdk_path or developer / f"Platforms/{platform}.platform/Developer/SDKs/{platform}.sdk").expanduser().resolve()
    environment = dict(os.environ, DEVELOPER_DIR=str(developer), SDKROOT=str(sdk))
    toolchain = developer / "Toolchains/XcodeDefault.xctoolchain/usr/bin"
    frontend, compiler, nm = (toolchain / name for name in ["swift-frontend", "swiftc", "nm"])
    for executable in [frontend, compiler, nm]:
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RuntimeError(f"Missing executable: {executable}")
    settings = json.loads((sdk / "SDKSettings.json").read_text())
    sdk_name = settings["CanonicalName"]
    if not sdk_name.startswith(args.sdk) or not re.fullmatch(r"[a-z0-9.]+", sdk_name):
        raise RuntimeError(f"SDK platform/name mismatch: {sdk_name!r} versus {args.sdk}")

    suffix = "-simulator" if args.sdk == "iphonesimulator" else ""
    target = f"arm64-apple-ios{args.deployment_target}{suffix}"
    module_basename = f"arm64-apple-ios{suffix}"
    framework = sdk / "System/Library/Frameworks/SwiftUICore.framework"
    interface = framework / f"Modules/SwiftUICore.swiftmodule/{module_basename}.swiftinterface"
    if not interface.exists() and args.sdk == "iphoneos":
        # Apple ships the device SDK interface as arm64e. Compile that textual
        # declaration set for the explicit arm64 target; verify with a real link.
        interface = framework / "Modules/SwiftUICore.swiftmodule/arm64e-apple-ios.swiftinterface"
    public_source = interface.read_text()
    if "-module-name SwiftUICore" not in public_source or "-module-abi-name SwiftUI" not in public_source:
        raise RuntimeError("Unexpected SDK module/ABI name. Inspect the SDK before adapting this bridge.")
    if re.search(r"\b(?:func\s+appearanceAnimation\b|enum\s+AppearanceAnimationStrategy\b)", public_source):
        raise RuntimeError("SDK already declares the recovered API; inspect its signatures instead of appending duplicates.")
    stub = framework / "SwiftUICore.tbd"
    stub_text = stub.read_text()
    missing = [symbol for symbol in REQUIRED_SYMBOLS if symbol not in stub_text]
    if missing:
        raise RuntimeError("SDK linker stub lacks required symbols:\n" + "\n".join(missing))

    declarations = root / "Bridge/AppearanceAnimation.declarations.swift"
    output = args.output_root.expanduser().resolve() / sdk_name / target
    output.mkdir(parents=True, exist_ok=True)
    module_dir = output / "Modules/SwiftUICore.swiftmodule"
    diagnostics = output / "Diagnostics"
    module_dir.mkdir(parents=True, exist_ok=True)
    diagnostics.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=output) as staging_name:
        staging = Path(staging_name)
        staged_interface = staging / f"{module_basename}.swiftinterface"
        staged_module = staging / f"{module_basename}.swiftmodule"
        staged_interface.write_text(public_source + "\n" + declarations.read_text())
        run([frontend, "-compile-module-from-interface", staged_interface,
             "-module-name", "SwiftUICore", "-target", target, "-sdk", sdk,
             "-o", staged_module], environment=environment)
        # Publish only after successful compilation. Existing generated modules
        # survive a compiler failure. No SDK file is modified.
        os.replace(staged_interface, module_dir / staged_interface.name)
        os.replace(staged_module, module_dir / staged_module.name)

    probe = diagnostics / "BridgeLinkProbe.dylib"
    run([compiler, "-target", target, "-sdk", sdk, "-I", output / "Modules",
         "-emit-library", "-module-name", "PrivateMarqueeBridgeLinkProbe",
         root / "Bridge/LinkProbe.swift", "-o", probe], environment=environment)
    imports = run([nm, "-u", probe], capture=True, environment=environment).stdout
    imported_api = [line for line in imports.splitlines()
                    if "appearanceAnimation" in line or "AppearanceAnimationStrategy" in line]
    if FUNCTION_SYMBOL not in imports or FUNCTION_SYMBOL + "QOMQ" not in imports:
        raise RuntimeError("Probe did not import the recovered function and opaque return descriptor.")
    (diagnostics / "linkage.txt").write_text("\n".join(imported_api) + "\n")
    compiler_version = run([compiler, "-version"], capture=True, environment=environment).stdout.strip()
    manifest = {
        "generator": "ReusableMarquee private SwiftUICore declaration bridge",
        "sdk_name": sdk_name, "sdk_path": str(sdk), "target": target,
        "compiler": compiler_version,
        "source_interface": str(interface), "source_interface_sha256": sha256(interface),
        "declarations_sha256": sha256(declarations),
        "linker_stub": str(stub), "link_probe_passed": True,
        "runtime_validation": "Only iOS 27.2 arm64 Simulator was runtime-tested in the containing investigation. This build is not a runtime availability check.",
        "swift_include_path": str(output / "Modules"),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Bridge generated and system-symbol linkage verified for {target} ({sdk_name}).")
    print(f"SWIFT_INCLUDE_PATHS: {output / 'Modules'}")
    print(f"Manifest: {output / 'manifest.json'}")
    if args.sdk == "iphoneos":
        print("Device compile/link passed; this does not establish device runtime compatibility.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Bridge generation failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        sys.exit(1)
