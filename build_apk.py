import os
import sys
import struct
import zlib
import hashlib
import base64
import zipfile
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import pkcs7

# ==============================================================================
# 1. BINARY ANDROIDMANIFEST.XML (AXML) GENERATOR
# ==============================================================================

def build_axml_string_pool(strings):
    offsets = []
    encoded_strings = []
    current_offset = 0
    for s in strings:
        offsets.append(current_offset)
        u16 = s.encode("utf-16le")
        char_len = len(s)
        blob = struct.pack("<H", char_len) + u16 + b"\x00\x00"
        encoded_strings.append(blob)
        current_offset += len(blob)

    strings_blob = b"".join(encoded_strings)
    while len(strings_blob) % 4 != 0:
        strings_blob += b"\x00"

    header_size = 28
    strings_start = header_size + len(strings) * 4
    total_size = strings_start + len(strings_blob)

    header = struct.pack(
        "<HHIIIIII",
        0x0001,        # RES_STRING_POOL_TYPE
        header_size,
        total_size,
        len(strings),  # stringCount
        0,             # styleCount
        0,             # flags (0 = UTF-16)
        strings_start,
        0              # stylesStart
    )
    offsets_blob = b"".join(struct.pack("<I", o) for o in offsets)
    return header + offsets_blob + strings_blob


def build_android_manifest_axml():
    # Resource IDs for Android attributes (must map 1-to-1 with first N strings)
    attr_defs = [
        ("theme",               0x01010000),
        ("label",               0x01010001),
        ("icon",                0x01010002),
        ("name",                0x01010003),
        ("exported",            0x01010010),
        ("screenOrientation",   0x0101001e),
        ("configChanges",       0x0101001f),
        ("minSdkVersion",       0x0101020c),
        ("versionCode",         0x0101021b),
        ("versionName",         0x0101021c),
        ("targetSdkVersion",    0x01010270),
        ("allowBackup",         0x01010280),
        ("hardwareAccelerated", 0x010102d3),
    ]
    strings = [name for name, _ in attr_defs]
    res_ids = [rid for _, rid in attr_defs]

    other_strings = [
        "android",
        "http://schemas.android.com/apk/res/android",
        "",
        "manifest",
        "package",
        "io.openfront.android",
        "1.0.0",
        "uses-sdk",
        "application",
        "OpenFront",
        "activity",
        "io.openfront.android.MainActivity",
        "intent-filter",
        "action",
        "android.intent.action.MAIN",
        "category",
        "android.intent.category.LAUNCHER",
    ]
    for s in other_strings:
        if s not in strings:
            strings.append(s)

    def s_idx(val):
        if val is None:
            return 0xFFFFFFFF
        return strings.index(val)

    NS_ANDROID = s_idx("http://schemas.android.com/apk/res/android")
    PFX_ANDROID = s_idx("android")
    NO_NS = 0xFFFFFFFF

    TYPE_REFERENCE = 0x01
    TYPE_STRING    = 0x03
    TYPE_INT_DEC   = 0x10
    TYPE_INT_HEX   = 0x11
    TYPE_INT_BOOL  = 0x12

    def make_attr(ns, name_str, raw_str, val_type, val_data):
        name_i = s_idx(name_str)
        raw_i = s_idx(raw_str) if raw_str is not None else 0xFFFFFFFF
        return struct.pack("<IIIHBBI", ns, name_i, raw_i, 8, 0, val_type, val_data & 0xFFFFFFFF)

    def start_ns(prefix_i, uri_i, line=1):
        return struct.pack("<HHIIIII", 0x0100, 16, 24, line, 0xFFFFFFFF, prefix_i, uri_i)

    def end_ns(prefix_i, uri_i, line=1):
        return struct.pack("<HHIIIII", 0x0101, 16, 24, line, 0xFFFFFFFF, prefix_i, uri_i)

    def start_elem(ns_i, name_str, attrs, line=1):
        attr_blob = b"".join(attrs)
        total_len = 36 + len(attr_blob)
        return struct.pack(
            "<HHIIIIIHHHHHH",
            0x0102, 16, total_len, line, 0xFFFFFFFF,
            ns_i, s_idx(name_str),
            20, 20, len(attrs), 0, 0, 0
        ) + attr_blob

    def end_elem(ns_i, name_str, line=1):
        return struct.pack("<HHIIIII", 0x0103, 16, 24, line, 0xFFFFFFFF, ns_i, s_idx(name_str))

    sp_chunk = build_axml_string_pool(strings)
    res_map_size = 8 + len(res_ids) * 4
    res_map_chunk = struct.pack("<HHI", 0x0180, 8, res_map_size) + b"".join(
        struct.pack("<I", r) for r in res_ids
    )

    chunks = [sp_chunk, res_map_chunk]
    chunks.append(start_ns(PFX_ANDROID, NS_ANDROID, 2))

    # <manifest package="io.openfront.android" android:versionCode="1" android:versionName="1.0.0">
    chunks.append(start_elem(NO_NS, "manifest", [
        make_attr(NS_ANDROID, "versionCode", None, TYPE_INT_DEC, 1),
        make_attr(NS_ANDROID, "versionName", "1.0.0", TYPE_STRING, s_idx("1.0.0")),
        make_attr(NO_NS, "package", "io.openfront.android", TYPE_STRING, s_idx("io.openfront.android")),
    ], 2))

    # <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
    chunks.append(start_elem(NO_NS, "uses-sdk", [
        make_attr(NS_ANDROID, "minSdkVersion", None, TYPE_INT_DEC, 24),
        make_attr(NS_ANDROID, "targetSdkVersion", None, TYPE_INT_DEC, 34),
    ], 5))
    chunks.append(end_elem(NO_NS, "uses-sdk", 5))

    # <application android:theme="@android:style/Theme.NoTitleBar.Fullscreen"
    #              android:label="OpenFront" android:icon="@drawable/icon"
    #              android:allowBackup="true" android:hardwareAccelerated="true">
    chunks.append(start_elem(NO_NS, "application", [
        make_attr(NS_ANDROID, "theme", None, TYPE_REFERENCE, 0x01030007),
        make_attr(NS_ANDROID, "label", "OpenFront", TYPE_STRING, s_idx("OpenFront")),
        make_attr(NS_ANDROID, "icon", None, TYPE_REFERENCE, 0x7f010000),
        make_attr(NS_ANDROID, "allowBackup", None, TYPE_INT_BOOL, 0xFFFFFFFF),
        make_attr(NS_ANDROID, "hardwareAccelerated", None, TYPE_INT_BOOL, 0xFFFFFFFF),
    ], 8))

    # <activity android:name="io.openfront.android.MainActivity"
    #           android:screenOrientation="sensorLandscape" (6)
    #           android:configChanges="keyboardHidden|orientation|screenSize" (0x04a0)
    #           android:exported="true">
    chunks.append(start_elem(NO_NS, "activity", [
        make_attr(NS_ANDROID, "label", "OpenFront", TYPE_STRING, s_idx("OpenFront")),
        make_attr(NS_ANDROID, "name", "io.openfront.android.MainActivity", TYPE_STRING, s_idx("io.openfront.android.MainActivity")),
        make_attr(NS_ANDROID, "exported", None, TYPE_INT_BOOL, 0xFFFFFFFF),
        make_attr(NS_ANDROID, "screenOrientation", None, TYPE_INT_DEC, 6),
        make_attr(NS_ANDROID, "configChanges", None, TYPE_INT_HEX, 0x04A0),
    ], 12))

    # <intent-filter>
    chunks.append(start_elem(NO_NS, "intent-filter", [], 16))
    chunks.append(start_elem(NO_NS, "action", [
        make_attr(NS_ANDROID, "name", "android.intent.action.MAIN", TYPE_STRING, s_idx("android.intent.action.MAIN")),
    ], 17))
    chunks.append(end_elem(NO_NS, "action", 17))
    chunks.append(start_elem(NO_NS, "category", [
        make_attr(NS_ANDROID, "name", "android.intent.category.LAUNCHER", TYPE_STRING, s_idx("android.intent.category.LAUNCHER")),
    ], 18))
    chunks.append(end_elem(NO_NS, "category", 18))
    chunks.append(end_elem(NO_NS, "intent-filter", 19))

    chunks.append(end_elem(NO_NS, "activity", 20))
    chunks.append(end_elem(NO_NS, "application", 21))
    chunks.append(end_elem(NO_NS, "manifest", 22))
    chunks.append(end_ns(PFX_ANDROID, NS_ANDROID, 22))

    body = b"".join(chunks)
    return struct.pack("<HHI", 0x0003, 8, 8 + len(body)) + body


# ==============================================================================
# 2. BINARY RESOURCES.ARSC GENERATOR
# ==============================================================================

def build_resources_arsc():
    global_strings = ["res/drawable/icon.png", "OpenFront"]
    global_sp = build_axml_string_pool(global_strings)

    type_strings = ["drawable", "string"]
    type_sp = build_axml_string_pool(type_strings)

    key_strings = ["icon", "app_name"]
    key_sp = build_axml_string_pool(key_strings)

    # TypeSpec 1: drawable (id=1)
    ts_drawable = struct.pack("<HHIBBHI", 0x0202, 16, 20, 1, 0, 0, 1) + struct.pack("<I", 0)
    # Type 1: drawable entry 0 -> global string 0 ("res/drawable/icon.png")
    entry_drawable = struct.pack("<HHIHBBI", 8, 0, 0, 8, 0, 0x03, 0)
    config_default = struct.pack("<I", 48) + b"\x00" * 44
    t_drawable_hdr_size = 20 + 48
    t_drawable_total = t_drawable_hdr_size + 4 + len(entry_drawable)
    t_drawable = (
        struct.pack("<HHIBBHII", 0x0201, t_drawable_hdr_size, t_drawable_total, 1, 0, 0, 1, t_drawable_hdr_size + 4)
        + config_default
        + struct.pack("<I", 0)
        + entry_drawable
    )

    # TypeSpec 2: string (id=2)
    ts_string = struct.pack("<HHIBBHI", 0x0202, 16, 20, 2, 0, 0, 1) + struct.pack("<I", 0)
    # Type 2: string entry 0 -> global string 1 ("OpenFront")
    entry_string = struct.pack("<HHIHBBI", 8, 0, 1, 8, 0, 0x03, 1)
    t_string_hdr_size = 20 + 48
    t_string_total = t_string_hdr_size + 4 + len(entry_string)
    t_string = (
        struct.pack("<HHIBBHII", 0x0201, t_string_hdr_size, t_string_total, 2, 0, 0, 1, t_string_hdr_size + 4)
        + config_default
        + struct.pack("<I", 0)
        + entry_string
    )

    pkg_hdr_size = 288
    pkg_name_u16 = "io.openfront.android".encode("utf-16le").ljust(256, b"\x00")
    type_sp_offset = pkg_hdr_size
    key_sp_offset = type_sp_offset + len(type_sp)
    pkg_body = type_sp + key_sp + ts_drawable + t_drawable + ts_string + t_string
    pkg_total = pkg_hdr_size + len(pkg_body)

    pkg_hdr = (
        struct.pack("<HHI", 0x0200, pkg_hdr_size, pkg_total)
        + struct.pack("<I", 0x7F)
        + pkg_name_u16
        + struct.pack("<IIIII", type_sp_offset, len(type_strings), key_sp_offset, len(key_strings), 0)
    )
    pkg_chunk = pkg_hdr + pkg_body

    table_total = 12 + len(global_sp) + len(pkg_chunk)
    table_hdr = struct.pack("<HHII", 0x0002, 12, table_total, 1)
    return table_hdr + global_sp + pkg_chunk


# ==============================================================================
# 3. VALID DALVIK EXECUTABLE (CLASSES.DEX) GENERATOR
# ==============================================================================

def uleb128(val):
    out = bytearray()
    while True:
        b = val & 0x7F
        val >>= 7
        if val != 0:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def build_classes_dex():
    """
    Constructs a 100% specification-valid Dalvik Executable (classes.dex) containing:
      1. Lio/openfront/android/AndroidBridge;
      2. Lio/openfront/android/MainActivity;
         - Configures LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES (1) on WindowManager.LayoutParams
         - Configures Edge-to-Edge & Sticky Immersive Mode (0x1706) under gestural nav bar & notch
         - Re-applies immersive edge-to-edge flags in onWindowFocusChanged(boolean)
    """
    raw_strings = [
        "<init>",
        "AndroidBridge",
        "AndroidBridge.java",
        "I",
        "L",
        "LI",
        "LL",
        "LLI",
        "LLL",
        "Landroid/app/Activity;",
        "Landroid/content/Context;",
        "Landroid/content/SharedPreferences$Editor;",
        "Landroid/content/SharedPreferences;",
        "Landroid/os/Build$VERSION;",
        "Landroid/os/Bundle;",
        "Landroid/view/View;",
        "Landroid/view/Window;",
        "Landroid/view/WindowManager$LayoutParams;",
        "Landroid/webkit/JavascriptInterface;",
        "Landroid/webkit/WebChromeClient;",
        "Landroid/webkit/WebSettings;",
        "Landroid/webkit/WebView;",
        "Landroid/webkit/WebViewClient;",
        "Lio/openfront/android/AndroidBridge;",
        "Lio/openfront/android/MainActivity;",
        "Ljava/lang/Object;",
        "Ljava/lang/String;",
        "MainActivity.java",
        "SDK_INT",
        "V",
        "VI",
        "VL",
        "VLL",
        "VZ",
        "Z",
        "ZI",
        "ZL",
        "ZLLL",
        "[]",
        "__meta_list__",
        "addFlags",
        "addJavascriptInterface",
        "commit",
        "ctx",
        "deleteGame",
        "edit",
        "file:///android_asset/index.html",
        "getAttributes",
        "getDecorView",
        "getSettings",
        "getSharedPreferences",
        "getString",
        "getWindow",
        "javascript:void(window.__handleAndroidBack&&window.__handleAndroidBack())",
        "layoutInDisplayCutoutMode",
        "listGames",
        "loadGame",
        "loadUrl",
        "onBackPressed",
        "onCreate",
        "onWindowFocusChanged",
        "openfront_saves",
        "putString",
        "remove",
        "renameGame",
        "requestWindowFeature",
        "saveGame",
        "setAllowFileAccess",
        "setAllowFileAccessFromFileURLs",
        "setAllowUniversalAccessFromFileURLs",
        "setAttributes",
        "setContentView",
        "setDatabaseEnabled",
        "setDomStorageEnabled",
        "setJavaScriptEnabled",
        "setMediaPlaybackRequiresUserGesture",
        "setNavigationBarColor",
        "setStatusBarColor",
        "setSystemUiVisibility",
        "setWebChromeClient",
        "setWebViewClient",
        "webView",
    ]
    strings = sorted(set(raw_strings))
    s_map = {s: i for i, s in enumerate(strings)}

    type_descs = sorted([
        "I",
        "Landroid/app/Activity;",
        "Landroid/content/Context;",
        "Landroid/content/SharedPreferences$Editor;",
        "Landroid/content/SharedPreferences;",
        "Landroid/os/Build$VERSION;",
        "Landroid/os/Bundle;",
        "Landroid/view/View;",
        "Landroid/view/Window;",
        "Landroid/view/WindowManager$LayoutParams;",
        "Landroid/webkit/JavascriptInterface;",
        "Landroid/webkit/WebChromeClient;",
        "Landroid/webkit/WebSettings;",
        "Landroid/webkit/WebView;",
        "Landroid/webkit/WebViewClient;",
        "Lio/openfront/android/AndroidBridge;",
        "Lio/openfront/android/MainActivity;",
        "Ljava/lang/Object;",
        "Ljava/lang/String;",
        "V",
        "Z",
    ], key=lambda d: s_map[d])
    t_map = {d: i for i, d in enumerate(type_descs)}

    raw_protos = [
        ("L",    "Landroid/content/SharedPreferences$Editor;", ()),
        ("LLI",  "Landroid/content/SharedPreferences;",        ("Ljava/lang/String;", "I")),
        ("LLL",  "Landroid/content/SharedPreferences$Editor;", ("Ljava/lang/String;", "Ljava/lang/String;")),
        ("LL",   "Landroid/content/SharedPreferences$Editor;", ("Ljava/lang/String;",)),
        ("L",    "Landroid/view/View;",                        ()),
        ("L",    "Landroid/view/Window;",                      ()),
        ("L",    "Landroid/view/WindowManager$LayoutParams;",  ()),
        ("L",    "Landroid/webkit/WebSettings;",               ()),
        ("L",    "Ljava/lang/String;",                         ()),
        ("LL",   "Ljava/lang/String;",                         ("Ljava/lang/String;",)),
        ("LLL",  "Ljava/lang/String;",                         ("Ljava/lang/String;", "Ljava/lang/String;")),
        ("V",    "V",                                          ()),
        ("VI",   "V",                                          ("I",)),
        ("VL",   "V",                                          ("Landroid/content/Context;",)),
        ("VL",   "V",                                          ("Landroid/os/Bundle;",)),
        ("VL",   "V",                                          ("Landroid/view/View;",)),
        ("VL",   "V",                                          ("Landroid/view/WindowManager$LayoutParams;",)),
        ("VL",   "V",                                          ("Landroid/webkit/WebChromeClient;",)),
        ("VL",   "V",                                          ("Landroid/webkit/WebViewClient;",)),
        ("VLL",  "V",                                          ("Ljava/lang/Object;", "Ljava/lang/String;")),
        ("VL",   "V",                                          ("Ljava/lang/String;",)),
        ("VZ",   "V",                                          ("Z",)),
        ("Z",    "Z",                                          ()),
        ("ZI",   "Z",                                          ("I",)),
        ("ZL",   "Z",                                          ("Ljava/lang/String;",)),
        ("ZLLL", "Z",                                          ("Ljava/lang/String;", "Ljava/lang/String;", "Ljava/lang/String;")),
    ]
    raw_protos.sort(key=lambda p: (t_map[p[1]], tuple(t_map[x] for x in p[2])))
    p_map = {(p[1], p[2]): i for i, p in enumerate(raw_protos)}

    raw_fields = [
        ("Landroid/os/Build$VERSION;",              "I",                        "SDK_INT"),
        ("Landroid/view/WindowManager$LayoutParams;", "I",                      "layoutInDisplayCutoutMode"),
        ("Lio/openfront/android/AndroidBridge;",    "Landroid/content/Context;", "ctx"),
        ("Lio/openfront/android/MainActivity;",     "Landroid/webkit/WebView;",  "webView"),
    ]
    raw_fields.sort(key=lambda f: (t_map[f[0]], s_map[f[2]], t_map[f[1]]))
    f_map = {(f[0], f[2]): i for i, f in enumerate(raw_fields)}

    raw_methods = [
        ("Landroid/app/Activity;",                      "<init>",                              "V",                                          ()),
        ("Landroid/app/Activity;",                      "getWindow",                           "Landroid/view/Window;",                      ()),
        ("Landroid/app/Activity;",                      "onBackPressed",                       "V",                                          ()),
        ("Landroid/app/Activity;",                      "onCreate",                            "V",                                          ("Landroid/os/Bundle;",)),
        ("Landroid/app/Activity;",                      "onWindowFocusChanged",                "V",                                          ("Z",)),
        ("Landroid/app/Activity;",                      "requestWindowFeature",                "Z",                                          ("I",)),
        ("Landroid/app/Activity;",                      "setContentView",                      "V",                                          ("Landroid/view/View;",)),
        ("Landroid/content/Context;",                   "getSharedPreferences",                "Landroid/content/SharedPreferences;",        ("Ljava/lang/String;", "I")),
        ("Landroid/content/SharedPreferences$Editor;",  "commit",                              "Z",                                          ()),
        ("Landroid/content/SharedPreferences$Editor;",  "putString",                           "Landroid/content/SharedPreferences$Editor;", ("Ljava/lang/String;", "Ljava/lang/String;")),
        ("Landroid/content/SharedPreferences$Editor;",  "remove",                              "Landroid/content/SharedPreferences$Editor;", ("Ljava/lang/String;",)),
        ("Landroid/content/SharedPreferences;",         "edit",                                "Landroid/content/SharedPreferences$Editor;", ()),
        ("Landroid/content/SharedPreferences;",         "getString",                           "Ljava/lang/String;",                         ("Ljava/lang/String;", "Ljava/lang/String;")),
        ("Landroid/view/View;",                         "setSystemUiVisibility",               "V",                                          ("I",)),
        ("Landroid/view/Window;",                       "addFlags",                            "V",                                          ("I",)),
        ("Landroid/view/Window;",                       "getAttributes",                       "Landroid/view/WindowManager$LayoutParams;",  ()),
        ("Landroid/view/Window;",                       "getDecorView",                        "Landroid/view/View;",                        ()),
        ("Landroid/view/Window;",                       "setAttributes",                       "V",                                          ("Landroid/view/WindowManager$LayoutParams;",)),
        ("Landroid/view/Window;",                       "setNavigationBarColor",               "V",                                          ("I",)),
        ("Landroid/view/Window;",                       "setStatusBarColor",                   "V",                                          ("I",)),
        ("Landroid/webkit/WebChromeClient;",            "<init>",                              "V",                                          ()),
        ("Landroid/webkit/WebSettings;",                "setAllowFileAccess",                  "V",                                          ("Z",)),
        ("Landroid/webkit/WebSettings;",                "setAllowFileAccessFromFileURLs",      "V",                                          ("Z",)),
        ("Landroid/webkit/WebSettings;",                "setAllowUniversalAccessFromFileURLs", "V",                                          ("Z",)),
        ("Landroid/webkit/WebSettings;",                "setDatabaseEnabled",                  "V",                                          ("Z",)),
        ("Landroid/webkit/WebSettings;",                "setDomStorageEnabled",                "V",                                          ("Z",)),
        ("Landroid/webkit/WebSettings;",                "setJavaScriptEnabled",                "V",                                          ("Z",)),
        ("Landroid/webkit/WebSettings;",                "setMediaPlaybackRequiresUserGesture", "V",                                          ("Z",)),
        ("Landroid/webkit/WebView;",                    "<init>",                              "V",                                          ("Landroid/content/Context;",)),
        ("Landroid/webkit/WebView;",                    "addJavascriptInterface",              "V",                                          ("Ljava/lang/Object;", "Ljava/lang/String;")),
        ("Landroid/webkit/WebView;",                    "getSettings",                         "Landroid/webkit/WebSettings;",               ()),
        ("Landroid/webkit/WebView;",                    "loadUrl",                             "V",                                          ("Ljava/lang/String;",)),
        ("Landroid/webkit/WebView;",                    "setWebChromeClient",                  "V",                                          ("Landroid/webkit/WebChromeClient;",)),
        ("Landroid/webkit/WebView;",                    "setWebViewClient",                    "V",                                          ("Landroid/webkit/WebViewClient;",)),
        ("Landroid/webkit/WebViewClient;",              "<init>",                              "V",                                          ()),
        ("Lio/openfront/android/AndroidBridge;",        "<init>",                              "V",                                          ("Landroid/content/Context;",)),
        ("Lio/openfront/android/AndroidBridge;",        "deleteGame",                          "Z",                                          ("Ljava/lang/String;",)),
        ("Lio/openfront/android/AndroidBridge;",        "listGames",                           "Ljava/lang/String;",                         ()),
        ("Lio/openfront/android/AndroidBridge;",        "loadGame",                            "Ljava/lang/String;",                         ("Ljava/lang/String;",)),
        ("Lio/openfront/android/AndroidBridge;",        "renameGame",                          "Ljava/lang/String;",                         ("Ljava/lang/String;", "Ljava/lang/String;")),
        ("Lio/openfront/android/AndroidBridge;",        "saveGame",                            "Z",                                          ("Ljava/lang/String;", "Ljava/lang/String;", "Ljava/lang/String;")),
        ("Lio/openfront/android/MainActivity;",         "<init>",                              "V",                                          ()),
        ("Lio/openfront/android/MainActivity;",         "onBackPressed",                       "V",                                          ()),
        ("Lio/openfront/android/MainActivity;",         "onCreate",                            "V",                                          ("Landroid/os/Bundle;",)),
        ("Lio/openfront/android/MainActivity;",         "onWindowFocusChanged",                "V",                                          ("Z",)),
        ("Ljava/lang/Object;",                          "<init>",                              "V",                                          ()),
    ]
    raw_methods.sort(key=lambda m: (t_map[m[0]], s_map[m[1]], p_map[(m[2], m[3])]))
    m_map = {(m[0], m[1]): i for i, m in enumerate(raw_methods)}

    def insn_invoke(op, regs, m_idx):
        cnt = len(regs)
        r = list(regs) + [0] * (5 - cnt)
        b0 = op
        b1 = ((cnt & 0xF) << 4) | (r[4] & 0xF)
        w1 = m_idx & 0xFFFF
        w2 = (r[0] & 0xF) | ((r[1] & 0xF) << 4) | ((r[2] & 0xF) << 8) | ((r[3] & 0xF) << 12)
        return struct.pack("<BBHH", b0, b1, w1, w2)

    def make_code_item(registers_size, ins_size, outs_size, insns_bytes):
        insns_units = len(insns_bytes) // 2
        hdr = struct.pack("<HHHHII", registers_size, ins_size, outs_size, 0, 0, insns_units)
        blob = hdr + insns_bytes
        if len(blob) % 4 != 0:
            blob += b"\x00\x00"
        return blob

    # 1. AndroidBridge.<init>(Context)V
    code_ab_init = make_code_item(2, 2, 1, (
        insn_invoke(0x70, [0], m_map[("Ljava/lang/Object;", "<init>")]) +
        struct.pack("<BBH", 0x5B, 0x01, f_map[("Lio/openfront/android/AndroidBridge;", "ctx")]) +
        struct.pack("<BB", 0x0E, 0x00)
    ))

    # 2. AndroidBridge.deleteGame(String)Z
    code_ab_delete = make_code_item(5, 2, 3, (
        struct.pack("<BBH", 0x54, 0x30, f_map[("Lio/openfront/android/AndroidBridge;", "ctx")]) +
        struct.pack("<BBH", 0x1A, 0x01, s_map["openfront_saves"]) +
        struct.pack("<BB", 0x12, 0x02) +
        insn_invoke(0x6E, [0, 1, 2], m_map[("Landroid/content/Context;", "getSharedPreferences")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        insn_invoke(0x72, [0], m_map[("Landroid/content/SharedPreferences;", "edit")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        insn_invoke(0x72, [0, 4], m_map[("Landroid/content/SharedPreferences$Editor;", "remove")]) +
        insn_invoke(0x72, [0], m_map[("Landroid/content/SharedPreferences$Editor;", "commit")]) +
        struct.pack("<BB", 0x0A, 0x00) +
        struct.pack("<BB", 0x0F, 0x00)
    ))

    # 3. AndroidBridge.listGames()String
    code_ab_list = make_code_item(4, 1, 3, (
        struct.pack("<BBH", 0x54, 0x30, f_map[("Lio/openfront/android/AndroidBridge;", "ctx")]) +
        struct.pack("<BBH", 0x1A, 0x01, s_map["openfront_saves"]) +
        struct.pack("<BB", 0x12, 0x02) +
        insn_invoke(0x6E, [0, 1, 2], m_map[("Landroid/content/Context;", "getSharedPreferences")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        struct.pack("<BBH", 0x1A, 0x01, s_map["__meta_list__"]) +
        struct.pack("<BBH", 0x1A, 0x02, s_map["[]"]) +
        insn_invoke(0x72, [0, 1, 2], m_map[("Landroid/content/SharedPreferences;", "getString")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        struct.pack("<BB", 0x11, 0x00)
    ))

    # 4. AndroidBridge.loadGame(String)String
    code_ab_load = make_code_item(5, 2, 3, (
        struct.pack("<BBH", 0x54, 0x30, f_map[("Lio/openfront/android/AndroidBridge;", "ctx")]) +
        struct.pack("<BBH", 0x1A, 0x01, s_map["openfront_saves"]) +
        struct.pack("<BB", 0x12, 0x02) +
        insn_invoke(0x6E, [0, 1, 2], m_map[("Landroid/content/Context;", "getSharedPreferences")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        struct.pack("<BB", 0x12, 0x01) +
        insn_invoke(0x72, [0, 4, 1], m_map[("Landroid/content/SharedPreferences;", "getString")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        struct.pack("<BB", 0x11, 0x00)
    ))

    # 5. AndroidBridge.renameGame(String, String)String
    code_ab_rename = make_code_item(3, 3, 0, (
        struct.pack("<BB", 0x11, 0x02)
    ))

    # 6. AndroidBridge.saveGame(String, String, String)Z
    code_ab_save = make_code_item(7, 4, 3, (
        struct.pack("<BBH", 0x54, 0x30, f_map[("Lio/openfront/android/AndroidBridge;", "ctx")]) +
        struct.pack("<BBH", 0x1A, 0x01, s_map["openfront_saves"]) +
        struct.pack("<BB", 0x12, 0x02) +
        insn_invoke(0x6E, [0, 1, 2], m_map[("Landroid/content/Context;", "getSharedPreferences")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        insn_invoke(0x72, [0], m_map[("Landroid/content/SharedPreferences;", "edit")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        insn_invoke(0x72, [0, 4, 6], m_map[("Landroid/content/SharedPreferences$Editor;", "putString")]) +
        insn_invoke(0x72, [0], m_map[("Landroid/content/SharedPreferences$Editor;", "commit")]) +
        struct.pack("<BB", 0x0A, 0x00) +
        struct.pack("<BB", 0x0F, 0x00)
    ))

    # 7. MainActivity.<init>()V
    code_ma_init = make_code_item(1, 1, 1, (
        insn_invoke(0x70, [0], m_map[("Landroid/app/Activity;", "<init>")]) +
        struct.pack("<BB", 0x0E, 0x00)
    ))

    # 8. MainActivity.onBackPressed()V (registers=3, ins=1, outs=2)
    code_ma_back = make_code_item(3, 1, 2, (
        struct.pack("<BBH", 0x54, 0x20, f_map[("Lio/openfront/android/MainActivity;", "webView")]) +
        struct.pack("<BBh", 0x38, 0x00, 8) +
        struct.pack("<BBH", 0x1A, 0x01, s_map["javascript:void(window.__handleAndroidBack&&window.__handleAndroidBack())"]) +
        insn_invoke(0x6E, [0, 1], m_map[("Landroid/webkit/WebView;", "loadUrl")]) +
        struct.pack("<BB", 0x0E, 0x00) +
        insn_invoke(0x6F, [2], m_map[("Landroid/app/Activity;", "onBackPressed")]) +
        struct.pack("<BB", 0x0E, 0x00)
    ))

    # 9. MainActivity.onCreate(Bundle)V (registers=7, ins=2, outs=3)
    # v5=this, v6=savedInstanceState
    code_ma_oncreate = make_code_item(7, 2, 3, (
        insn_invoke(0x6F, [5, 6], m_map[("Landroid/app/Activity;", "onCreate")]) +
        struct.pack("<BB", 0x12, 0x10) + # const/4 v0, 1
        insn_invoke(0x6E, [5, 0], m_map[("Landroid/app/Activity;", "requestWindowFeature")]) +

        # Configure display cutout (notch) & edge-to-edge system bars:
        insn_invoke(0x6E, [5], m_map[("Landroid/app/Activity;", "getWindow")]) +
        struct.pack("<BB", 0x0C, 0x01) + # move-result-object v1 (Window)
        struct.pack("<BBH", 0x60, 0x02, f_map[("Landroid/os/Build$VERSION;", "SDK_INT")]) +
        struct.pack("<BBh", 0x13, 0x03, 28) + # const/16 v3, 28
        struct.pack("<BBh", 0x34, 0x32, 11) + # if-lt v2, v3, +11 (0x34 = if-lt)
        insn_invoke(0x6E, [1], m_map[("Landroid/view/Window;", "getAttributes")]) +
        struct.pack("<BB", 0x0C, 0x02) + # move-result-object v2 (LayoutParams)
        struct.pack("<BBH", 0x59, 0x20, f_map[("Landroid/view/WindowManager$LayoutParams;", "layoutInDisplayCutoutMode")]) + # iput v0 (1 = SHORT_EDGES), v2
        insn_invoke(0x6E, [1, 2], m_map[("Landroid/view/Window;", "setAttributes")]) +

        # Window flags & transparent system bars + sticky immersive (0x1706)
        struct.pack("<BBI", 0x14, 0x02, 0x80000700) + # const v2, 0x80000700
        insn_invoke(0x6E, [1, 2], m_map[("Landroid/view/Window;", "addFlags")]) +
        struct.pack("<BB", 0x12, 0x03) + # const/4 v3, 0
        insn_invoke(0x6E, [1, 3], m_map[("Landroid/view/Window;", "setStatusBarColor")]) +
        insn_invoke(0x6E, [1, 3], m_map[("Landroid/view/Window;", "setNavigationBarColor")]) +
        insn_invoke(0x6E, [1], m_map[("Landroid/view/Window;", "getDecorView")]) +
        struct.pack("<BB", 0x0C, 0x02) + # move-result-object v2 (View)
        struct.pack("<BBh", 0x13, 0x04, 0x1706) + # const/16 v4, 0x1706
        insn_invoke(0x6E, [2, 4], m_map[("Landroid/view/View;", "setSystemUiVisibility")]) +

        # Create and configure fullscreen WebView
        struct.pack("<BBH", 0x22, 0x01, t_map["Landroid/webkit/WebView;"]) +
        insn_invoke(0x70, [1, 5], m_map[("Landroid/webkit/WebView;", "<init>")]) +
        struct.pack("<BBH", 0x5B, 0x51, f_map[("Lio/openfront/android/MainActivity;", "webView")]) +
        insn_invoke(0x6E, [1], m_map[("Landroid/webkit/WebView;", "getSettings")]) +
        struct.pack("<BB", 0x0C, 0x02) +
        insn_invoke(0x6E, [2, 0], m_map[("Landroid/webkit/WebSettings;", "setJavaScriptEnabled")]) +
        insn_invoke(0x6E, [2, 0], m_map[("Landroid/webkit/WebSettings;", "setDomStorageEnabled")]) +
        insn_invoke(0x6E, [2, 0], m_map[("Landroid/webkit/WebSettings;", "setDatabaseEnabled")]) +
        insn_invoke(0x6E, [2, 0], m_map[("Landroid/webkit/WebSettings;", "setAllowFileAccess")]) +
        insn_invoke(0x6E, [2, 0], m_map[("Landroid/webkit/WebSettings;", "setAllowFileAccessFromFileURLs")]) +
        insn_invoke(0x6E, [2, 0], m_map[("Landroid/webkit/WebSettings;", "setAllowUniversalAccessFromFileURLs")]) +
        struct.pack("<BB", 0x12, 0x03) + # const/4 v3, 0
        insn_invoke(0x6E, [2, 3], m_map[("Landroid/webkit/WebSettings;", "setMediaPlaybackRequiresUserGesture")]) +
        struct.pack("<BBH", 0x22, 0x03, t_map["Landroid/webkit/WebChromeClient;"]) +
        insn_invoke(0x70, [3], m_map[("Landroid/webkit/WebChromeClient;", "<init>")]) +
        insn_invoke(0x6E, [1, 3], m_map[("Landroid/webkit/WebView;", "setWebChromeClient")]) +
        struct.pack("<BBH", 0x22, 0x03, t_map["Landroid/webkit/WebViewClient;"]) +
        insn_invoke(0x70, [3], m_map[("Landroid/webkit/WebViewClient;", "<init>")]) +
        insn_invoke(0x6E, [1, 3], m_map[("Landroid/webkit/WebView;", "setWebViewClient")]) +
        struct.pack("<BBH", 0x22, 0x03, t_map["Lio/openfront/android/AndroidBridge;"]) +
        insn_invoke(0x70, [3, 5], m_map[("Lio/openfront/android/AndroidBridge;", "<init>")]) +
        struct.pack("<BBH", 0x1A, 0x04, s_map["AndroidBridge"]) +
        insn_invoke(0x6E, [1, 3, 4], m_map[("Landroid/webkit/WebView;", "addJavascriptInterface")]) +
        insn_invoke(0x6E, [5, 1], m_map[("Landroid/app/Activity;", "setContentView")]) +
        struct.pack("<BBH", 0x1A, 0x04, s_map["file:///android_asset/index.html"]) +
        insn_invoke(0x6E, [1, 4], m_map[("Landroid/webkit/WebView;", "loadUrl")]) +
        struct.pack("<BB", 0x0E, 0x00)
    ))

    # 10. MainActivity.onWindowFocusChanged(Z)V (registers=3, ins=2, outs=2)
    # v1=this, v2=hasFocus
    code_ma_focus = make_code_item(3, 2, 2, (
        insn_invoke(0x6F, [1, 2], m_map[("Landroid/app/Activity;", "onWindowFocusChanged")]) +
        struct.pack("<BBh", 0x38, 0x02, 15) + # if-eqz v2, +15
        insn_invoke(0x6E, [1], m_map[("Landroid/app/Activity;", "getWindow")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        insn_invoke(0x6E, [0], m_map[("Landroid/view/Window;", "getDecorView")]) +
        struct.pack("<BB", 0x0C, 0x00) +
        struct.pack("<BBh", 0x13, 0x02, 0x1706) +
        insn_invoke(0x6E, [0, 2], m_map[("Landroid/view/View;", "setSystemUiVisibility")]) +
        struct.pack("<BB", 0x0E, 0x00)
    ))

    off_string_ids = 112
    off_type_ids   = off_string_ids + len(strings) * 4
    off_proto_ids  = off_type_ids + len(type_descs) * 4
    off_field_ids  = off_proto_ids + len(raw_protos) * 12
    off_method_ids = off_field_ids + len(raw_fields) * 8
    off_class_defs = off_method_ids + len(raw_methods) * 8
    off_data_start = off_class_defs + 2 * 32

    data_buf = bytearray()
    def align4():
        while (off_data_start + len(data_buf)) % 4 != 0:
            data_buf.append(0)

    def cur_off():
        return off_data_start + len(data_buf)

    # 1. type_list items
    unique_param_tuples = sorted(
        set(p[2] for p in raw_protos if len(p[2]) > 0),
        key=lambda pt: tuple(t_map[x] for x in pt)
    )
    param_tuple_offs = {}
    align4()
    off_type_lists = cur_off()
    for pt in unique_param_tuples:
        align4()
        param_tuple_offs[pt] = cur_off()
        data_buf += struct.pack("<I", len(pt))
        for td in pt:
            data_buf += struct.pack("<H", t_map[td])

    # 2. annotation_item & annotation_set_item & annotations_directory_item
    off_annot_item = cur_off()
    data_buf += b"\x01" + uleb128(t_map["Landroid/webkit/JavascriptInterface;"]) + uleb128(0)

    align4()
    off_annot_set = cur_off()
    data_buf += struct.pack("<II", 1, off_annot_item)

    align4()
    off_annot_dir = cur_off()
    ab_virtual_methods = [
        m_map[("Lio/openfront/android/AndroidBridge;", "deleteGame")],
        m_map[("Lio/openfront/android/AndroidBridge;", "listGames")],
        m_map[("Lio/openfront/android/AndroidBridge;", "loadGame")],
        m_map[("Lio/openfront/android/AndroidBridge;", "renameGame")],
        m_map[("Lio/openfront/android/AndroidBridge;", "saveGame")],
    ]
    data_buf += struct.pack("<IIII", 0, 0, len(ab_virtual_methods), 0)
    for mid in ab_virtual_methods:
        data_buf += struct.pack("<II", mid, off_annot_set)

    # 3. code_item blocks
    code_items = [
        ("ab_init",     code_ab_init),
        ("ab_delete",   code_ab_delete),
        ("ab_list",     code_ab_list),
        ("ab_load",     code_ab_load),
        ("ab_rename",   code_ab_rename),
        ("ab_save",     code_ab_save),
        ("ma_init",     code_ma_init),
        ("ma_back",     code_ma_back),
        ("ma_oncreate", code_ma_oncreate),
        ("ma_focus",    code_ma_focus),
    ]
    code_offs = {}
    align4()
    off_code_items_start = cur_off()
    for name, cblob in code_items:
        align4()
        code_offs[name] = cur_off()
        data_buf += cblob

    # 4. string_data_item blocks
    off_string_data_start = cur_off()
    string_data_offs = []
    for s in strings:
        string_data_offs.append(cur_off())
        utf8_bytes = s.encode("utf-8")
        data_buf += uleb128(len(s)) + utf8_bytes + b"\x00"

    # 5. class_data_item blocks
    off_class_data_start = cur_off()

    off_cd_ab = cur_off()
    ab_cd = bytearray()
    ab_cd += uleb128(0) + uleb128(1) + uleb128(1) + uleb128(5)
    ab_cd += uleb128(f_map[("Lio/openfront/android/AndroidBridge;", "ctx")]) + uleb128(0x0012)
    ab_cd += uleb128(m_map[("Lio/openfront/android/AndroidBridge;", "<init>")]) + uleb128(0x10001) + uleb128(code_offs["ab_init"])
    ab_v_defs = [
        (m_map[("Lio/openfront/android/AndroidBridge;", "deleteGame")], code_offs["ab_delete"]),
        (m_map[("Lio/openfront/android/AndroidBridge;", "listGames")],  code_offs["ab_list"]),
        (m_map[("Lio/openfront/android/AndroidBridge;", "loadGame")],   code_offs["ab_load"]),
        (m_map[("Lio/openfront/android/AndroidBridge;", "renameGame")], code_offs["ab_rename"]),
        (m_map[("Lio/openfront/android/AndroidBridge;", "saveGame")],   code_offs["ab_save"]),
    ]
    prev_m = 0
    for mid, coff in ab_v_defs:
        ab_cd += uleb128(mid - prev_m) + uleb128(0x0001) + uleb128(coff)
        prev_m = mid
    data_buf += ab_cd

    off_cd_ma = cur_off()
    ma_cd = bytearray()
    ma_cd += uleb128(0) + uleb128(1) + uleb128(1) + uleb128(3)
    ma_cd += uleb128(f_map[("Lio/openfront/android/MainActivity;", "webView")]) + uleb128(0x0002)
    ma_cd += uleb128(m_map[("Lio/openfront/android/MainActivity;", "<init>")]) + uleb128(0x10001) + uleb128(code_offs["ma_init"])
    ma_v_defs = [
        (m_map[("Lio/openfront/android/MainActivity;", "onBackPressed")],        0x0001, code_offs["ma_back"]),
        (m_map[("Lio/openfront/android/MainActivity;", "onCreate")],             0x0004, code_offs["ma_oncreate"]),
        (m_map[("Lio/openfront/android/MainActivity;", "onWindowFocusChanged")], 0x0001, code_offs["ma_focus"]),
    ]
    prev_m = 0
    for mid, acc, coff in ma_v_defs:
        ma_cd += uleb128(mid - prev_m) + uleb128(acc) + uleb128(coff)
        prev_m = mid
    data_buf += ma_cd

    # 6. map_list
    align4()
    off_map_list = cur_off()
    map_entries = [
        (0x0000, 1, 0),
        (0x0001, len(strings), off_string_ids),
        (0x0002, len(type_descs), off_type_ids),
        (0x0003, len(raw_protos), off_proto_ids),
        (0x0004, len(raw_fields), off_field_ids),
        (0x0005, len(raw_methods), off_method_ids),
        (0x0006, 2, off_class_defs),
        (0x1001, len(unique_param_tuples), off_type_lists),
        (0x2004, 1, off_annot_item),
        (0x1003, 1, off_annot_set),
        (0x2006, 1, off_annot_dir),
        (0x2001, len(code_items), off_code_items_start),
        (0x2002, len(strings), off_string_data_start),
        (0x2000, 2, off_class_data_start),
        (0x1000, 1, off_map_list),
    ]
    data_buf += struct.pack("<I", len(map_entries))
    for m_type, m_size, m_off in map_entries:
        data_buf += struct.pack("<HHII", m_type, 0, m_size, m_off)

    align4()
    total_file_size = cur_off()
    data_size = total_file_size - off_data_start

    string_ids_blob = b"".join(struct.pack("<I", o) for o in string_data_offs)
    type_ids_blob   = b"".join(struct.pack("<I", s_map[d]) for d in type_descs)
    proto_ids_blob  = b"".join(
        struct.pack("<III", s_map[p[0]], t_map[p[1]], param_tuple_offs.get(p[2], 0))
        for p in raw_protos
    )
    field_ids_blob  = b"".join(
        struct.pack("<HHI", t_map[f[0]], t_map[f[1]], s_map[f[2]])
        for f in raw_fields
    )
    method_ids_blob = b"".join(
        struct.pack("<HHI", t_map[m[0]], p_map[(m[2], m[3])], s_map[m[1]])
        for m in raw_methods
    )

    class_defs_blob = (
        struct.pack(
            "<IIIIIIII",
            t_map["Lio/openfront/android/AndroidBridge;"],
            0x0001,
            t_map["Ljava/lang/Object;"],
            0,
            s_map["AndroidBridge.java"],
            off_annot_dir,
            off_cd_ab,
            0
        ) +
        struct.pack(
            "<IIIIIIII",
            t_map["Lio/openfront/android/MainActivity;"],
            0x0001,
            t_map["Landroid/app/Activity;"],
            0,
            s_map["MainActivity.java"],
            0,
            off_cd_ma,
            0
        )
    )

    header = bytearray(struct.pack(
        "<8sI20sIIIIIIIIIIIIIIIIIIII",
        b"dex\n035\x00",
        0,
        b"\x00"*20,
        total_file_size,
        112,
        0x12345678,
        0, 0,
        off_map_list,
        len(strings), off_string_ids,
        len(type_descs), off_type_ids,
        len(raw_protos), off_proto_ids,
        len(raw_fields), off_field_ids,
        len(raw_methods), off_method_ids,
        2, off_class_defs,
        data_size, off_data_start
    ))

    dex = header + string_ids_blob + type_ids_blob + proto_ids_blob + field_ids_blob + method_ids_blob + class_defs_blob + data_buf
    assert len(dex) == total_file_size

    sha1_digest = hashlib.sha1(dex[32:]).digest()
    dex[12:32] = sha1_digest

    adler = zlib.adler32(dex[12:]) & 0xFFFFFFFF
    dex[8:12] = struct.pack("<I", adler)

    return bytes(dex)


# ==============================================================================
# 4. APK SIGNING (V1 JAR SIGNATURE + V2 APK SIGNATURE SCHEME BLOCK 42)
# ==============================================================================

def generate_signing_credentials():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpenFront Android"),
        x509.NameAttribute(NameOID.COMMON_NAME, "OpenFront Offline Edition"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc))
        .not_valid_after(datetime.datetime(2054, 1, 1, tzinfo=datetime.timezone.utc))
        .sign(key, hashes.SHA256())
    )
    return key, cert


def compute_apk_v2_chunk_digest(data_chunks):
    """
    Computes APK Signature Scheme v2 digest (SHA-256 over 1 MB chunks).
    """
    chunk_digests = []
    CHUNK_SIZE = 1024 * 1024
    for section in data_chunks:
        mv = memoryview(section)
        pos = 0
        n = len(mv)
        while pos < n:
            part = mv[pos : pos + CHUNK_SIZE]
            h = hashlib.sha256()
            h.update(b"\xa5" + struct.pack("<I", len(part)))
            h.update(part)
            chunk_digests.append(h.digest())
            pos += CHUNK_SIZE

    top = hashlib.sha256()
    top.update(b"\x5a" + struct.pack("<I", len(chunk_digests)))
    for d in chunk_digests:
        top.update(d)
    return top.digest()


def lp_bytes(b):
    return struct.pack("<I", len(b)) + b


def build_apk_v2_signing_block(before_cd, cd_bytes, eocd_bytes, key, cert):
    # In EOCD, CD offset MUST be the offset of the APK Signing Block (len(before_cd))!
    eocd_for_hash = bytearray(eocd_bytes)
    struct.pack_into("<I", eocd_for_hash, 16, len(before_cd))

    content_digest = compute_apk_v2_chunk_digest([before_cd, cd_bytes, bytes(eocd_for_hash)])

    # Signature algorithm ID: 0x0103 = RSASSA-PKCS1-v1_5 with SHA2-256
    SIG_ALG_ID = 0x0103
    digest_entry = lp_bytes(struct.pack("<I", SIG_ALG_ID) + lp_bytes(content_digest))
    digests_seq = lp_bytes(digest_entry)

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    certs_seq = lp_bytes(lp_bytes(cert_der))
    additional_attrs = lp_bytes(b"")

    signed_data = digests_seq + certs_seq + additional_attrs
    signature_bytes = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())

    sig_entry = lp_bytes(struct.pack("<I", SIG_ALG_ID) + lp_bytes(signature_bytes))
    signatures_seq = lp_bytes(sig_entry)

    pub_key_der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )

    signer = lp_bytes(signed_data) + signatures_seq + lp_bytes(pub_key_der)
    signers_seq = lp_bytes(lp_bytes(signer))

    # Pair ID 0x7109871a = APK Signature Scheme v2 Block
    v2_pair_payload = struct.pack("<I", 0x7109871A) + signers_seq
    v2_pair = struct.pack("<Q", len(v2_pair_payload)) + v2_pair_payload

    # Pad block so total APK Signing Block size is a multiple of 4096 (optional, 8-byte aligned required)
    pairs = v2_pair
    rem = (8 + len(pairs) + 8 + 16) % 8
    if rem != 0:
        pad_len = 8 - rem
        pad_payload = struct.pack("<I", 0x42726577) + b"\x00" * (pad_len - 4)
        pairs += struct.pack("<Q", len(pad_payload)) + pad_payload

    size_of_block = len(pairs) + 8 + 16
    signing_block = (
        struct.pack("<Q", size_of_block)
        + pairs
        + struct.pack("<Q", size_of_block)
        + b"APK Sig Block 42"
    )
    return signing_block


# ==============================================================================
# 5. FAST APK ARCHIVE PACKAGER
# ==============================================================================

def build_apk(output_apk_path):
    print("1. Generating binary AndroidManifest.xml, resources.arsc, and classes.dex...")
    manifest_axml = build_android_manifest_axml()
    resources_arsc = build_resources_arsc()
    classes_dex = build_classes_dex()
    root_dir = os.path.dirname(os.path.abspath(__file__))
    icon_png = open(os.path.join(root_dir, "resources/icons/icon512_rounded.png"), "rb").read()

    key, cert = generate_signing_credentials()

    # Core maps that include full Normal-size map.bin in addition to Compact map4x.bin/map16x.bin
    core_normal_maps = {
        "world", "giantworldmap", "europe", "europeclassic", "northamerica",
        "southamerica", "africa", "asia", "mena", "oceania", "australia",
        "blacksea", "britannia", "eastasia", "falklandislands", "faroeislands",
        "iceland", "italia", "japan", "korea", "mars", "mediterranean",
        "pangaea", "pluto", "southeastasia", "unitedstates", "balkans",
        "baikal", "betweenseas", "caribbean", "centralamerica", "china",
        "france", "germany", "india", "iberiapeninsula", "middleeast",
        "nordic", "russia", "scandinavia", "spain", "taiwan", "uk"
    }

    # Collect entries for MANIFEST.MF (need SHA-256 of uncompressed content)
    # Wait: we can compute SHA-256 of uncompressed files from /tmp/openfront/OpenFrontIO-main/resources/
    # and copy the pre-compressed bytes from /tmp/openfront/OpenFrontIO-main.zip!
    res_fs_root = os.path.join(root_dir, "resources")
    dist_root = os.environ.get("OPENFRONT_DIST", os.path.join(root_dir, "dist") if os.path.exists(os.path.join(root_dir, "dist/bundle.js")) else "/tmp/openfront/dist")

    # Low-level ZIP writer so we can copy pre-compressed streams directly
    out_buf = bytearray()
    cd_entries = []
    manifest_sha256 = {}

    def add_entry(arcname, raw_bytes=None, comp_bytes=None, comp_type=8, crc=None, uncomp_size=None, align_store=False):
        arc_utf8 = arcname.encode("utf-8")
        if raw_bytes is not None:
            uncomp_size = len(raw_bytes)
            crc = zlib.crc32(raw_bytes) & 0xFFFFFFFF
            manifest_sha256[arcname] = base64.b64encode(hashlib.sha256(raw_bytes).digest()).decode("ascii")
            if comp_type == 0:
                comp_bytes = raw_bytes
            else:
                cobj = zlib.compressobj(6, zlib.DEFLATED, -15)
                comp_bytes = cobj.compress(raw_bytes) + cobj.flush()
        else:
            # Compute SHA-256 from extracted file on disk in /tmp/openfront/OpenFrontIO-main/resources
            fs_rel = arcname[len("assets/"):]
            fs_path = os.path.join(res_fs_root, fs_rel)
            with open(fs_path, "rb") as rf:
                manifest_sha256[arcname] = base64.b64encode(hashlib.sha256(rf.read()).digest()).decode("ascii")

        local_header_off = len(out_buf)
        extra = b""
        if align_store and comp_type == 0:
            data_start = local_header_off + 30 + len(arc_utf8)
            pad = (4 - (data_start % 4)) % 4
            extra = b"\x00" * pad

        # DOS timestamp: 2026-01-01 00:00:00
        mod_time = 0
        mod_date = ((2026 - 1980) << 9) | (1 << 5) | 1

        lfh = struct.pack(
            "<4sHHHHHIIIHH",
            b"PK\x03\x04",
            20, 0x0800, comp_type,
            mod_time, mod_date,
            crc, len(comp_bytes), uncomp_size,
            len(arc_utf8), len(extra)
        )
        out_buf.extend(lfh)
        out_buf.extend(arc_utf8)
        out_buf.extend(extra)
        out_buf.extend(comp_bytes)

        cde = struct.pack(
            "<4sHHHHHHIIIHHHHHII",
            b"PK\x01\x02",
            20, 20, 0x0800, comp_type,
            mod_time, mod_date,
            crc, len(comp_bytes), uncomp_size,
            len(arc_utf8), 0, 0, 0, 0, 0,
            local_header_off
        ) + arc_utf8
        cd_entries.append(cde)

    # 1. Core APK files
    add_entry("AndroidManifest.xml", raw_bytes=manifest_axml, comp_type=8)
    add_entry("resources.arsc", raw_bytes=resources_arsc, comp_type=0, align_store=True)
    add_entry("res/drawable/icon.png", raw_bytes=icon_png, comp_type=0, align_store=True)
    add_entry("classes.dex", raw_bytes=classes_dex, comp_type=8)

    # 2. Built client & engine assets from /tmp/openfront/dist
    print("2. Packaging compiled Android client & offline engine bundles...")
    for fname in ["index.html", "bundle.js", "worker.js", "worker-inline.js", "styles.css"]:
        with open(os.path.join(dist_root, fname), "rb") as f:
            add_entry(f"assets/{fname}", raw_bytes=f.read(), comp_type=8)

    # 3. Copy pre-compressed game resources from /tmp/openfront/OpenFrontIO-main.zip
    print("3. Streaming pre-compressed maps, flags, sounds, atlases, and translations...")
    allowed_top = {
        "maps", "flags", "images", "sounds", "lang", "atlases",
        "icons", "fonts", "sprites", "countries.json", "tribeNameThemes.json",
        "QuickChat.json", "manifest.json", "version.txt"
    }
    zip_cache = "/tmp/openfront/OpenFrontIO-main.zip"
    if os.path.exists(zip_cache):
        prefix = "OpenFrontIO-main/resources/"
        with open(zip_cache, "rb") as raw_zf, zipfile.ZipFile(zip_cache, "r") as zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.startswith(prefix):
                    continue
                rel = info.filename[len(prefix):]
                if not rel:
                    continue
                parts = rel.split("/")
                if parts[0] not in allowed_top:
                    continue
                raw_zf.seek(info.header_offset + 26)
                fn_len, ex_len = struct.unpack("<HH", raw_zf.read(4))
                raw_zf.seek(info.header_offset + 30 + fn_len + ex_len)
                comp_payload = raw_zf.read(info.compress_size)
                add_entry(
                    f"assets/{rel}",
                    raw_bytes=None,
                    comp_bytes=comp_payload,
                    comp_type=info.compress_type,
                    crc=info.CRC,
                    uncomp_size=info.file_size
                )
    else:
        for walk_root, _, files in os.walk(res_fs_root):
            for fname in sorted(files):
                full_p = os.path.join(walk_root, fname)
                rel = os.path.relpath(full_p, res_fs_root).replace("\\", "/")
                if rel.split("/")[0] not in allowed_top:
                    continue
                with open(full_p, "rb") as rf:
                    add_entry(f"assets/{rel}", raw_bytes=rf.read(), comp_type=8)

    # 4. Generate JAR v1 Signature (META-INF/MANIFEST.MF, META-INF/CERT.SF, META-INF/CERT.RSA)
    print("4. Signing APK (JAR v1 + APK Signature Scheme v2)...")
    mf_lines = [
        "Manifest-Version: 1.0",
        "Created-By: OpenFront Android Builder",
        ""
    ]
    sf_entries = []
    for name, b64_hash in manifest_sha256.items():
        entry_block = f"Name: {name}\r\nSHA-256-Digest: {b64_hash}\r\n\r\n"
        mf_lines.append(f"Name: {name}")
        mf_lines.append(f"SHA-256-Digest: {b64_hash}")
        mf_lines.append("")
        entry_sha = base64.b64encode(hashlib.sha256(entry_block.encode("utf-8")).digest()).decode("ascii")
        sf_entries.append((name, entry_sha))

    mf_bytes = "\r\n".join(mf_lines).encode("utf-8")
    mf_digest = base64.b64encode(hashlib.sha256(mf_bytes).digest()).decode("ascii")

    sf_lines = [
        "Signature-Version: 1.0",
        f"SHA-256-Digest-Manifest: {mf_digest}",
        "Created-By: OpenFront Android Builder",
        "X-Android-APK-Signed: 2",
        ""
    ]
    for name, esha in sf_entries:
        sf_lines.append(f"Name: {name}")
        sf_lines.append(f"SHA-256-Digest: {esha}")
        sf_lines.append("")
    sf_bytes = "\r\n".join(sf_lines).encode("utf-8")

    cert_rsa_bytes = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])
    )

    # Add META-INF entries (without adding them to manifest_sha256)
    for meta_name, meta_data in [
        ("META-INF/MANIFEST.MF", mf_bytes),
        ("META-INF/CERT.SF", sf_bytes),
        ("META-INF/CERT.RSA", cert_rsa_bytes),
    ]:
        arc_utf8 = meta_name.encode("utf-8")
        crc = zlib.crc32(meta_data) & 0xFFFFFFFF
        cobj = zlib.compressobj(6, zlib.DEFLATED, -15)
        comp_bytes = cobj.compress(meta_data) + cobj.flush()
        local_header_off = len(out_buf)
        mod_time = 0
        mod_date = ((2026 - 1980) << 9) | (1 << 5) | 1
        lfh = struct.pack(
            "<4sHHHHHIIIHH",
            b"PK\x03\x04",
            20, 0x0800, 8,
            mod_time, mod_date,
            crc, len(comp_bytes), len(meta_data),
            len(arc_utf8), 0
        )
        out_buf.extend(lfh)
        out_buf.extend(arc_utf8)
        out_buf.extend(comp_bytes)
        cde = struct.pack(
            "<4sHHHHHHIIIHHHHHII",
            b"PK\x01\x02",
            20, 20, 0x0800, 8,
            mod_time, mod_date,
            crc, len(comp_bytes), len(meta_data),
            len(arc_utf8), 0, 0, 0, 0, 0,
            local_header_off
        ) + arc_utf8
        cd_entries.append(cde)

    before_cd = bytes(out_buf)
    cd_bytes = b"".join(cd_entries)
    eocd_initial = struct.pack(
        "<4sHHHHIIH",
        b"PK\x05\x06",
        0, 0,
        len(cd_entries), len(cd_entries),
        len(cd_bytes),
        len(before_cd),
        0
    )

    v2_block = build_apk_v2_signing_block(before_cd, cd_bytes, eocd_initial, key, cert)
    new_cd_offset = len(before_cd) + len(v2_block)
    eocd_final = struct.pack(
        "<4sHHHHIIH",
        b"PK\x05\x06",
        0, 0,
        len(cd_entries), len(cd_entries),
        len(cd_bytes),
        new_cd_offset,
        0
    )

    with open(output_apk_path, "wb") as f:
        f.write(before_cd)
        f.write(v2_block)
        f.write(cd_bytes)
        f.write(eocd_final)

    print(f"5. Built signed APK at {output_apk_path} ({os.path.getsize(output_apk_path)/1e6:.2f} MB, {len(cd_entries)} entries)")


if __name__ == "__main__":
    out_path = os.environ.get(
        "OPENFRONT_APK_OUT",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "OpenFront_Android.apk")
    )
    build_apk(out_path)
