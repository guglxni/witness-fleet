# Launch film source

This is the final HTML/GSAP timeline used by **HyperFrames 0.8.169**. It contains the actual ElevenLabs Sarah narration, the original mixed score, native MuJoCo footage, an OpenDesign Motion excerpt, and captions. The finished delivery is [`../../site/public/media/launch.mp4`](../../site/public/media/launch.mp4).

```bash
npm ci
npx --no-install hyperframes check
npx --no-install hyperframes render -o rendered.mp4 --fps 30 --quality delivery --workers 2 --strict --no-best-effort
# Delivery audio gain used after rendering:
ffmpeg -i rendered.mp4 -map 0:v -map 0:a -c:v copy -af volume=-2.66dB -c:a aac -b:a 192k -movflags +faststart launch.mp4
```

The official CLI downloads a browser when needed. Export uses real HTML motion rendering; it is not a video-file concatenation claiming to use HyperFrames. Render output is 86 seconds at 1920×1080. The retained final encode was checked with FFmpeg full decode, ffprobe, audio analysis and sampled encoded frames.

`SCRIPT.md` documents the story and research. `assets/provenance.json` is sanitized capture provenance; the original journal/graph and working-machine paths are not published. Narrative/illustrative footage is visibly distinguished from native simulation. The configured demo-owner in the captured run is scripted, not proof of a human-authenticated approval.

GSAP retains its Standard License; DM Sans retains SIL OFL. Generated speech is not open-source model output tooling. See root THIRD_PARTY.md.
