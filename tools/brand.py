#!/usr/bin/env python3
"""Turn Mozilla's Firefox for Android (the release build) into PosterFox.

usage: brand.py <firefox checkout> <icon png>

Every edit ASSERTS what it replaces, so a Mozilla release that moves a line stops the build here, by name, instead of
shipping an app that is half Firefox. Edits:

  applicationId  `place.poster.posterfox` (installs beside Firefox, its own Zapstore listing).
  sharedUserId   our own. The release build inherits Firefox's `org.mozilla.firefox.sharedID`, and Android refuses to
                 install an app whose sharedUserId belongs to an app signed with a different key -- so with Firefox on
                 the phone, PosterFox would not install at all.
  app name       "PosterFox" (the launcher label and the brand string).
  telemetry      off: TELEMETRY and CRASH_REPORTING are false in the build config (as Mozilla's own debug build has
                 them), and the "Send technical and interaction data" setting defaults to off. Mozilla's service tokens
                 (Sentry, Adjust, Nimbus) are only added when token files exist, and a PosterFox build has none.
  icons          the ostrich: the adaptive icon's foreground becomes a bitmap of it on PosterChan purple, and the legacy
                 launcher icons are redrawn from it. The WebP files are deleted, not shadowed -- two resources with
                 one name in one folder is a build error.
"""
import os
import re
import sys

from PIL import Image, ImageDraw

APP_ID = "place.poster"
APP_SUFFIX = ".posterfox"
SHARED_ID = "place.poster.posterfox.sharedID"
NAME = "PosterFox"
BACKGROUND = "#1a0b2e"
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def edit(path, old, new, count=1):
    s = open(path, encoding="utf-8").read()
    n = s.count(old)
    if n != count:
        sys.exit(f"brand.py: expected {count} of {old!r} in {path}, found {n} -- Mozilla moved it; update brand.py")
    open(path, "w", encoding="utf-8").write(s.replace(old, new))


def main(ff, icon):
    app = os.path.join(ff, "mobile/android/fenix/app")
    gradle = os.path.join(app, "build.gradle")
    res = os.path.join(app, "src/release/res")

    edit(gradle, 'applicationId "org.mozilla"', f'applicationId "{APP_ID}"')
    # The release block: its suffix and its sharedUserId (the other build types keep theirs).
    s = open(gradle, encoding="utf-8").read()
    m = re.search(r'\n        release releaseTemplate >> \{.*?\n        \}\n', s, re.S)
    if not m:
        sys.exit("brand.py: no `release releaseTemplate >> {` block in build.gradle")
    block = m.group(0)
    for old, new in (('applicationIdSuffix ".firefox"', f'applicationIdSuffix "{APP_SUFFIX}"'),
                     ('"sharedUserId": "org.mozilla.firefox.sharedID"', f'"sharedUserId": "{SHARED_ID}"')):
        if block.count(old) != 1:
            sys.exit(f"brand.py: release block lost {old!r}")
        block = block.replace(old, new)
    open(gradle, "w", encoding="utf-8").write(s[:m.start()] + block + s[m.end():])

    edit(gradle, "    buildConfigField 'boolean', 'CRASH_REPORTING', 'true'\n    buildConfigField 'boolean', 'TELEMETRY', 'true'\n",
         "    buildConfigField 'boolean', 'CRASH_REPORTING', 'false'\n    buildConfigField 'boolean', 'TELEMETRY', 'false'\n")
    edit(os.path.join(app, "src/main/java/org/mozilla/fenix/utils/Settings.kt"),
         "            appContext.getPreferenceKey(R.string.pref_key_telemetry),\n            default = true,",
         "            appContext.getPreferenceKey(R.string.pref_key_telemetry),\n            default = false,")

    edit(os.path.join(res, "values/static_strings.xml"),
         '<string name="app_name" translatable="false">Firefox</string>',
         f'<string name="app_name" translatable="false">{NAME}</string>')
    edit(os.path.join(res, "values/colors.xml"),
         '<color name="ic_launcher_background">@color/photonInk80</color>',
         f'<color name="ic_launcher_background">{BACKGROUND}</color>')

    art = Image.open(icon).convert("RGBA")
    # Adaptive foreground: 108dp canvas, the art inside the 66dp safe circle (432 px = xxxhdpi).
    fg = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
    inner = art.resize((264, 264), Image.LANCZOS)
    fg.paste(inner, (84, 84), inner)
    os.makedirs(os.path.join(res, "drawable-nodpi"), exist_ok=True)
    fg.save(os.path.join(res, "drawable-nodpi/posterfox_launcher_fg.png"))
    fgxml = os.path.join(res, "drawable/ic_launcher_foreground.xml")
    if not os.path.isfile(fgxml):
        sys.exit("brand.py: release drawable/ic_launcher_foreground.xml is gone -- the adaptive icon moved")
    open(fgxml, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!-- PosterFox: the ostrich (tools/brand.py). -->\n'
        '<bitmap xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    android:src="@drawable/posterfox_launcher_fg" android:gravity="center" />\n')

    # Legacy launcher icons (Android 7 and older launchers): the art on a purple square / circle.
    for dens, px in DENSITIES.items():
        d = os.path.join(res, f"mipmap-{dens}")
        for name, round_ in (("ic_launcher", False), ("ic_launcher_round", True)):
            webp = os.path.join(d, name + ".webp")
            if not os.path.isfile(webp):
                sys.exit(f"brand.py: {webp} is gone -- the launcher icons moved")
            os.remove(webp)
            base = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            mask = Image.new("L", (px, px), 0)
            dr = ImageDraw.Draw(mask)
            if round_:
                dr.ellipse((0, 0, px - 1, px - 1), fill=255)
            else:
                dr.rounded_rectangle((0, 0, px - 1, px - 1), radius=px // 5, fill=255)
            base.paste(Image.new("RGBA", (px, px), BACKGROUND), (0, 0), mask)
            a = art.resize((int(px * 0.8),) * 2, Image.LANCZOS)
            o = (px - a.size[0]) // 2
            base.paste(a, (o, o), a)
            base.save(os.path.join(d, name + ".png"))
    print("branded:", APP_ID + APP_SUFFIX, NAME)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
