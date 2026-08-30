# LocalGuard AI — editable product demo

This Remotion 4.0.518 project is the editable source for the 160-second, 1920×1080,
30-fps LocalGuard AI product film. The main composition is `LocalGuardProductDemo`;
all nine chapters are also registered separately under **Editable scenes** in Studio.

## Commands

```powershell
npm install
npm run lint
npm run build
npm run dev
```

Render a half-size verification frame at the architecture scene:

```powershell
npm run still:check
```

Render a high-quality H.264 master:

```powershell
npm run render:master
```

## Narration and captions

The nine narration clips live in `public/audio/` and are independently placed on the
timeline so one chapter can be replaced without disturbing the others. Narration is enabled
by default and can be muted with `narrationEnabled`. The external subtitle source is
`public/captions/product-demo.srt`; the burned-in caption layer can be controlled separately
with `showCaptions`.

The source browser recording is muted by design. It supplies authentic interaction motion;
the finished film's voice track comes from the chapter narration clips.

To regenerate the synthetic narration and captions, create a disposable Python environment and
run the pinned generator:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-narration.txt
.\.venv\Scripts\python.exe .\scripts\generate-narration.py
```

This optional step uses Microsoft Edge neural TTS. Only the public narration in
`scripts/narration-scenes.json` is sent to that service; LocalGuard documents, credentials, and
application data are never read by the generator.
