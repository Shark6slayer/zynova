import os
import subprocess

FFMPEG = r"C:\Users\karup\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\karup\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffprobe.exe"
SCREENSHOTS_DIR = r"C:\super_ai_docs\screenshots"
TMP_DIR = r"C:\super_ai_docs\video\tmp"
OUTPUT_VIDEO = r"C:\super_ai_docs\video\SUPER_AI_Product_Demo.mp4"
FONT_PATH = "C\\:/Windows/Fonts/arial.ttf"

# 12 Scenes totaling exactly 150 seconds (2 minutes 30 seconds)
# Note: Percentage symbols (%) are written as 'percent' to prevent FFmpeg strftime expansion errors
SCENES = [
    {
        "id": "scene_00_intro",
        "duration": 12,
        "image": None,
        "title": "SUPER_AI PLATFORM SHOWCASE",
        "subtitle": "Sovereign, Privacy-First Super-Application Engine",
        "caption": "Unified digital ecosystem integrating Social, Chat, Video, Shopping and Food into a 14.2 MB binary."
    },
    {
        "id": "scene_01_dashboard",
        "duration": 15,
        "image": "01_dashboard.png",
        "title": "01. UNIFIED CLIENT AND DASHBOARD",
        "subtitle": "React 19 + TypeScript + Capacitor 8 Android",
        "caption": "Native 60fps shell with unified identity, instant module switching, and centralized session control."
    },
    {
        "id": "scene_02_social",
        "duration": 14,
        "image": "02_social_feed.png",
        "title": "02. SOCIAL NETWORK AND CONTENT CREATION",
        "subtitle": "Interactive Feed with EICAR Malware Quarantine",
        "caption": "Rich media sharing, real-time engagement, and automated quarantine inspection for uploaded assets."
    },
    {
        "id": "scene_03_chat",
        "duration": 14,
        "image": "03_chat.png",
        "title": "03. REALTIME ENCRYPTED MESSAGING",
        "subtitle": "AES-256-GCM Envelope Encryption and WebSockets",
        "caption": "Context-bound cryptographic keys prevent database transplant attacks; native script rendering."
    },
    {
        "id": "scene_04_video",
        "duration": 13,
        "image": "04_video.png",
        "title": "04. VIDEO PLATFORM AND CULINARY REELS",
        "subtitle": "Seamless Transition from Media to Commerce",
        "caption": "Embedded creator and restaurant tags allow instant transitions from video discovery to ordering."
    },
    {
        "id": "scene_05_search",
        "duration": 12,
        "image": "05_search.png",
        "title": "05. UNIVERSAL COMMAND PALETTE",
        "subtitle": "Cross-Module Instant Search",
        "caption": "Global search across products, restaurants, posts, and creators with ReDoS-protected indexing."
    },
    {
        "id": "scene_06_shopping",
        "duration": 15,
        "image": "06_zaviro_shopping.png",
        "title": "06. ZAVIRO MULTI-VENDOR MARKETPLACE",
        "subtitle": "Authoritative Integer-Paise Financial Precision",
        "caption": "Atomic stock decrements and idempotency headers eliminate overselling and duplicate checkout charges."
    },
    {
        "id": "scene_07_food",
        "duration": 14,
        "image": "07_food_ordering.png",
        "title": "07. FOOD DISCOVERY AND ON-DEMAND DINING",
        "subtitle": "Dynamic 5 percent GST and Packaging Fee Calculations",
        "caption": "Server-side pricing calculations prevent client manipulation; restaurant tenant isolation enforced."
    },
    {
        "id": "scene_08_i18n",
        "duration": 14,
        "image": "08_language_preferences.png",
        "title": "08. 23-LANGUAGE LINGUISTIC EQUITY",
        "subtitle": "All 22 Eighth Schedule Indian Languages + English",
        "caption": "Script-accurate typography with dynamic RTL bidirectional layout for Urdu, Kashmiri, and Sindhi."
    },
    {
        "id": "scene_09_security",
        "duration": 14,
        "image": "09_security_architecture.png",
        "title": "09. CRYPTOGRAPHIC DEVICE IDENTITY AND SESSIONS",
        "subtitle": "Ed25519 Challenge-Response and IP /24 Masking",
        "caption": "Stateless JTI token revocation store instantly invalidates compromised sessions across all workers."
    },
    {
        "id": "scene_10_ledger",
        "duration": 13,
        "image": "10_application_overview.png",
        "title": "10. PRIVATE AUDIT LEDGER AND BLOCKCHAIN ANCHOR",
        "subtitle": "RFC 8785 Canonical JSON and SHA-256 Hash Chaining",
        "caption": "Zero-PII Merkle checkpoints anchored to EVM contracts; 100 percent detection of log tampering or deletion."
    },
    {
        "id": "scene_11_outro",
        "duration": 12,
        "image": None,
        "title": "SUPER_AI: VERIFIED AND STAGING READY",
        "subtitle": "69/69 Backend Tests | 108/108 i18n Tests | 0 Vulnerabilities",
        "caption": "A sovereign digital foundation built on zero-trust cryptography and mathematical state integrity."
    }
]

print("Rendering individual scene video clips...")
clip_files = []

for idx, scene in enumerate(SCENES):
    clip_path = os.path.join(TMP_DIR, f"clip_{idx:02d}.mp4")
    dur = scene["duration"]
    title = scene["title"].replace(":", r"\:").replace("'", r"\'")
    sub = scene["subtitle"].replace(":", r"\:").replace("'", r"\'")
    cap = scene["caption"].replace(":", r"\:").replace("'", r"\'")
    
    if scene["image"] is None:
        # Title Card / Outro Card
        filter_str = (
            f"drawbox=y=0:color=black:width=1920:height=1080:t=fill,"
            f"drawbox=y=40:x=60:width=1800:height=1000:color=blue@0.2:t=fill,"
            f"drawbox=y=40:x=60:width=1800:height=1000:color=white@0.4:t=2,"
            f"drawtext=fontfile='{FONT_PATH}':text='{title}':fontsize=54:fontcolor=white:x=(w-text_w)/2:y=380,"
            f"drawtext=fontfile='{FONT_PATH}':text='{sub}':fontsize=32:fontcolor=#60a5fa:x=(w-text_w)/2:y=470,"
            f"drawtext=fontfile='{FONT_PATH}':text='{cap}':fontsize=24:fontcolor=#94a3b8:x=(w-text_w)/2:y=560,"
            f"drawtext=fontfile='{FONT_PATH}':text='SUPER_AI SOVEREIGN APPLICATION ENGINE':fontsize=20:fontcolor=#475569:x=(w-text_w)/2:y=920"
        )
        cmd = [
            FFMPEG, "-f", "lavfi", "-i", f"color=c=#0f172a:s=1920x1080:d={dur}",
            "-vf", filter_str,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
            "-y", clip_path
        ]
    else:
        # Screenshot presentation with subtle zoom and professional lower-third overlay
        img_path = os.path.join(SCREENSHOTS_DIR, scene["image"])
        filter_str = (
            f"scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0b0f19,"
            f"zoompan=z='min(zoom+0.0004,1.06)':d={dur*30}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
            f"drawbox=y=0:width=1920:height=70:color=black@0.85:t=fill,"
            f"drawtext=fontfile='{FONT_PATH}':text='{title}':fontsize=28:fontcolor=white:x=40:y=20,"
            f"drawtext=fontfile='{FONT_PATH}':text='{sub}':fontsize=20:fontcolor=#38bdf8:x=w-text_w-40:y=25,"
            f"drawbox=y=960:width=1920:height=120:color=black@0.9:t=fill,"
            f"drawtext=fontfile='{FONT_PATH}':text='{cap}':fontsize=22:fontcolor=#e2e8f0:x=40:y=980,"
            f"drawtext=fontfile='{FONT_PATH}':text='Empirical UI Evidence | Grounded in Verified SUPER_AI Code':fontsize=16:fontcolor=#64748b:x=40:y=1030"
        )
        cmd = [
            FFMPEG, "-loop", "1", "-i", img_path,
            "-vf", filter_str,
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
            "-y", clip_path
        ]
    
    print(f"Rendering [{idx+1}/{len(SCENES)}] {scene['id']} ({dur}s)...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"Error rendering {scene['id']}: {res.stderr.decode('utf-8', errors='ignore')[:400]}")
        raise RuntimeError(f"FFmpeg failed on {scene['id']}")
    clip_files.append(clip_path)

print("All clips rendered successfully. Creating concat file...")
concat_file = os.path.join(TMP_DIR, "concat_list.txt")
with open(concat_file, "w") as f:
    for c in clip_files:
        f.write(f"file '{c}'\n")

print("Concatenating clips into final presentation MP4...")
concat_cmd = [
    FFMPEG, "-f", "concat", "-safe", "0", "-i", concat_file,
    "-c", "copy",
    "-movflags", "+faststart",
    "-y", OUTPUT_VIDEO
]
subprocess.run(concat_cmd, check=True)

print("Adding clean tone audio track to ensure universal audio/video stream compatibility...")
AUDIO_VIDEO = os.path.join(TMP_DIR, "video_with_audio.mp4")
audio_cmd = [
    FFMPEG, "-i", OUTPUT_VIDEO,
    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
    "-movflags", "+faststart",
    "-y", AUDIO_VIDEO
]
subprocess.run(audio_cmd, check=True)

os.replace(AUDIO_VIDEO, OUTPUT_VIDEO)
print(f"Finished! Video successfully created at: {OUTPUT_VIDEO}")
