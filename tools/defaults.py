#!/usr/bin/env python3
"""Desktop PosterFox's defaults, for Firefox for Android.

usage: defaults.py <firefox checkout>

Desktop PosterFox sets its defaults in distribution/posterfox-prefs.js (in the posterfox repo). Most of those are
desktop-only (the new tab page, the AI sidebar, containers); these are the ones Android has a counterpart for. Every
edit ASSERTS what it replaces, so a Mozilla release that moves a line stops the build here, by name. Defaults, never
locks: each stays changeable in Settings, as on the desktop.

  strict tracking protection        browser.contentblocking.category = "strict"
  no saving / filling of passwords   signon.rememberSignons = false, signon.autofillForms = false -- the PosterChan
    or forms by Firefox itself       vault (the built-in extension) does passwords; browser.formfill.enable = false
  no sponsored shortcuts, stories    browser.newtabpage.activity-stream.showSponsored*, topsites.contile = false
    or suggestions                   browser.urlbar.suggest.quicksuggest.sponsored = false
  no welcome flow                    browser.aboutwelcome.enabled = false (Fenix's also asks for a Firefox account)
  poster.place shortcuts             browser.newtabpage.pinned: poster.place, the two git repos, PosterChan Passwords
  proxy never falls back to direct   network.proxy.failover_direct = false
  WebRTC stays behind a proxy        media.peerconnection.ice.proxy_only_if_behind_proxy = true
  no Mozilla VPN ("IP protection")   it signs in with a Firefox account; desktop PosterFox has no accounts
Studies follow telemetry, which brand.py already turns off.
"""
import json
import os
import sys

SHORTCUTS = [
    ("https://poster.place/", "poster.place"),
    ("https://poster.place/r/npub1fdtthaqujtjcd6yfy7kt0zpkadyl9vvypq00s5nztnmche74d0tqv6uwwr/posterchanai", "PosterChan Git"),
    ("https://poster.place/r/npub1fdtthaqujtjcd6yfy7kt0zpkadyl9vvypq00s5nztnmche74d0tqv6uwwr/posterfox", "PosterFox Git"),
    ("https://addons.mozilla.org/firefox/addon/posterchan-passwords/", "PosterChan Passwords"),
]

GECKO_PREFS = """
// ---- PosterFox (tools/defaults.py in the posterfox-android repo) ----
// A proxy that fails must not quietly send the page direct, and WebRTC must not go around one (desktop PosterFox).
pref("network.proxy.failover_direct", false);
pref("media.peerconnection.ice.proxy_only_if_behind_proxy", true);
// Mozilla's VPN ("IP protection") signs in with a Firefox account; PosterFox has no accounts.
pref("browser.ipProtection.enabled", false);
"""


def edit(path, old, new, count=1):
    s = open(path, encoding="utf-8").read()
    n = s.count(old)
    if n != count:
        sys.exit(f"defaults.py: expected {count} of {old!r} in {path}, found {n} -- Mozilla moved it; update defaults.py")
    open(path, "w", encoding="utf-8").write(s.replace(old, new))


def main(ff):
    app = os.path.join(ff, "mobile/android/fenix/app/src/main")
    settings = os.path.join(app, "java/org/mozilla/fenix/utils/Settings.kt")

    # Strict tracking protection: the two radio options' defaults change places.
    edit(settings, """            appContext.getPreferenceKey(R.string.pref_key_tracking_protection_standard_option),
            true,
        )""", """            appContext.getPreferenceKey(R.string.pref_key_tracking_protection_standard_option),
            false, // PosterFox: strict by default
        )""")
    edit(settings, """            appContext.getPreferenceKey(R.string.pref_key_tracking_protection_strict_default),
            false,
        )

    val useCustomTrackingProtection""", """            appContext.getPreferenceKey(R.string.pref_key_tracking_protection_strict_default),
            true, // PosterFox: strict by default
        )

    val useCustomTrackingProtection""")

    # Firefox's own logins / cards / addresses: off by default (the PosterChan vault does passwords).
    for key in ("pref_key_save_logins", "pref_key_autofill_logins",
                "pref_key_credit_cards_save_and_autofill_cards", "pref_key_addresses_save_and_autofill_addresses"):
        edit(settings, f"""            appContext.getPreferenceKey(R.string.{key}),
            default = {{ isAutofillSupported }},""", f"""            appContext.getPreferenceKey(R.string.{key}),
            default = {{ false }}, // PosterFox""")

    # Sponsored shortcuts (Contile), sponsored and recommended stories, sponsored suggestions: off.
    edit(settings, """            key = appContext.getPreferenceKey(R.string.pref_key_enable_contile),
            default = true,""", """            key = appContext.getPreferenceKey(R.string.pref_key_enable_contile),
            default = false, // PosterFox""")
    edit(settings, "defaultValue = { homescreenSections[HomeScreenSection.POCKET_SPONSORED_STORIES] == true },",
         "defaultValue = { false }, // PosterFox")
    edit(settings, "defaultValue = { homescreenSections[HomeScreenSection.POCKET] == true },",
         "defaultValue = { false }, // PosterFox")
    edit(settings, """            key = appContext.getPreferenceKey(R.string.pref_key_show_sponsored_suggestions),
            defaultValue = { enableFxSuggest },""", """            key = appContext.getPreferenceKey(R.string.pref_key_show_sponsored_suggestions),
            defaultValue = { false }, // PosterFox""")

    # No welcome flow: Mozilla's early return for benchmark builds, for every build (no unreachable code -- the
    # benchmark generators' opt-in keeps working).
    edit(settings, """        if (isBenchmarkBuild && !forceOnboardingForBenchmark) {
            return false
        }""", """        if (!forceOnboardingForBenchmark) { // PosterFox: no onboarding (it also asks for a Firefox account)
            return false
        }""")

    # The home screen's shortcuts, both the pinned ones and the suggested ones.
    rows = [{"url": u, "order": i, "title": t, "schema": 1, "exclude_locales": [], "exclude_regions": [],
             "include_locales": [], "include_regions": [], "exclude_experiments": [], "include_experiments": [],
             "id": "", "last_modified": 1} for i, (u, t) in enumerate(SHORTCUTS)]
    for name in ("default_pinned_shortcuts.json", "default_shortcuts.json"):
        path = os.path.join(app, "res/raw", name)
        if not os.path.isfile(path) or "data" not in json.load(open(path, encoding="utf-8")):
            sys.exit(f"defaults.py: {path} is gone or changed shape -- the home shortcuts moved")
        json.dump({"data": rows}, open(path, "w", encoding="utf-8"), indent=2)

    # NO FIREFOX ACCOUNTS (desktop PosterFox has none): the two places a signed-out person is offered one on every
    # visit -- the Settings screen's "Sign in to sync" row and the main menu's account row. The menu row stays for an
    # account that already exists (there is no way to make one), so no code becomes dead.
    edit(os.path.join(app, "java/org/mozilla/fenix/settings/account/AccountUiView.kt"), """            // Signed-out.
        } else {
            preferenceSignIn.isVisible = true""", """            // Signed-out.
        } else {
            preferenceSignIn.isVisible = false // PosterFox: no Firefox accounts""")
    edit(os.path.join(app, "java/org/mozilla/fenix/components/menu/compose/MainMenu.kt"), """        MenuGroup {
            MozillaAccountMenuItem(
                account = account,
                accountState = accountState,
                onClick = onMozillaAccountButtonClick,
            )
""", """        MenuGroup {
            if (account != null) { // PosterFox: no Firefox accounts -- shown only for one that already exists
                MozillaAccountMenuItem(
                    account = account,
                    accountState = accountState,
                    onClick = onMozillaAccountButtonClick,
                )
            }
""")

    # POSTERCHAN AI IN THE MENU. Desktop PosterFox has it in the sidebar (browser.ml.chat.provider =
    # <instance>/client?pcai=1); Android has no sidebar, so the main menu gets the same page, opened in a tab of this
    # app (an explicit intent to our own package -- never another browser).
    menu = os.path.join(app, "java/org/mozilla/fenix/components/menu/compose/MainMenu.kt")
    edit(menu, "import androidx.compose.foundation.LocalIndication\n",
         "import android.content.Intent\nimport android.net.Uri\nimport androidx.compose.foundation.LocalIndication\n"
         "import androidx.compose.ui.platform.LocalContext\n")
    edit(menu, """            MenuItem(
                label = stringResource(id = R.string.browser_menu_settings),
                beforeIconPainter = painterResource(id = iconsR.drawable.mozac_ic_settings_24),
                onClick = onSettingsButtonClick,
            )
        }""", """            MenuItem(
                label = stringResource(id = R.string.browser_menu_settings),
                beforeIconPainter = painterResource(id = iconsR.drawable.mozac_ic_settings_24),
                onClick = onSettingsButtonClick,
            )

            // PosterFox: PosterChan AI (desktop PosterFox's sidebar), opened in a tab of this app.
            val posterfoxContext = LocalContext.current
            MenuItem(
                label = "PosterChan AI",
                beforeIconPainter = painterResource(id = iconsR.drawable.mozac_ic_sparkle_24),
                onClick = {
                    posterfoxContext.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse("https://poster.place/client?pcai=1"))
                            .setPackage(posterfoxContext.packageName)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                },
            )
        }""")

    # uBLOCK ORIGIN AND PRIVACY BADGER WITHOUT A PROMPT. Desktop PosterFox ships them by policy; here the app installs
    # them from addons.mozilla.org on first start (PosterChanBookmarks.kt) so they keep AMO's updates, and these two
    # add-on ids -- and only these -- skip the permission dialog and the "added" dialog. An id is AMO-signed and unique,
    # so another add-on cannot pass as one of them.
    prompts = os.path.join(app, "java/org/mozilla/fenix/extension/WebExtensionPromptFeature.kt")
    edit(prompts, """    private fun handlePostInstallationRequest(addon: Addon) {
        showPostInstallationDialog(addon)
    }""", """    private fun handlePostInstallationRequest(addon: Addon) {
        if (addon.id in POSTERFOX_BUNDLED_ADDONS) { // PosterFox: installed for the person, nothing to announce
            consumePromptRequest()
            return
        }
        showPostInstallationDialog(addon)
    }""")
    edit(prompts, """        promptRequest: WebExtensionPromptRequest.AfterInstallation.Permissions.Required,
    ) {
        showPermissionDialog(""", """        promptRequest: WebExtensionPromptRequest.AfterInstallation.Permissions.Required,
    ) {
        if (addon.id in POSTERFOX_BUNDLED_ADDONS) { // PosterFox: what desktop PosterFox installs by policy
            handlePermissions(
                promptRequest,
                granted = true,
                privateBrowsingAllowed = false,
                technicalAndInteractionDataGranted = false,
            )
            return
        }
        showPermissionDialog(""")
    edit(prompts, """    companion object {""", """    companion object {
        /** PosterFox: installed on first start like desktop PosterFox's policy add-ons (uBlock Origin, Privacy Badger). */
        internal val POSTERFOX_BUNDLED_ADDONS = setOf("uBlock0@raymondhill.net", "jid1-MnnxcxisBPnSXQ@jetpack")
""")

    # Gecko engine defaults (built from source in artifact mode, so they reach the app's omni.ja).
    gp = os.path.join(ff, "mobile/android/app/geckoview-prefs.js")
    edit(gp, 'pref("browser.ipProtection.enabled", true);', 'pref("browser.ipProtection.enabled", true); // see below')
    with open(gp, "a", encoding="utf-8") as fh:
        fh.write(GECKO_PREFS)
    print("defaults: strict ETP, no Firefox password/form saving, no sponsored content, no onboarding, "
          "poster.place shortcuts, proxy-safe Gecko prefs, no Mozilla VPN")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
