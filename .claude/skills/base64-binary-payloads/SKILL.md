---
name: base64-binary-payloads
description: How to correctly emit a binary file (PDF, image, zip) as Base64 through a tool-call argument that only accepts an inline string — including why Base64 length is always a multiple of 4, which kinds of "splitting" are safe and which silently corrupt the file, how to build a large payload from slices, and how to verify the round-trip. Use this whenever a task involves base64, base64Content, an attachment or upload field that takes a string instead of a file path, a corrupted or unopenable file after transfer, a payload that seems too large to emit in one go, or any question about padding, "=" signs, or multiples of 4.
---

# Base64 binary payloads through string-only tool arguments

## The situation this exists for

Some tools accept a file only as an inline Base64 string — `attachments[].content`
on a mail tool, `base64Content` on a Drive-style upload. There is no path
parameter, no file id, no stream. The bytes have to travel through the model's
own output as a tool-call argument, which means a large file becomes a very long
literal string you have to produce exactly.

That constraint is what makes the usual "just base64 it" advice insufficient, and
it is where most corruption comes from.

## The arithmetic (yes, multiples of 4 — but know which claim you're making)

Base64 packs 3 bytes into 4 characters from `A–Z a–z 0–9 + /`, padding the final
group with `=` so the output length is always a multiple of 4. There are 0, 1, or
2 `=` characters, only ever at the very end.

For `n` input bytes, the encoded length is:

```
ceil(n / 3) * 4
```

Not `round(n * 4 / 3)` — that is off by up to three characters and will make you
chase a phantom bug. Example: 15,731 bytes → `ceil(15731/3)*4` = 5244 * 4 =
**20,976** characters.

The multiple-of-4 rule is a property of a *complete* encoded string. It is not a
rule that every fragment you handle must satisfy, and confusing the two leads
straight to the wrong conclusion in the next section.

## The distinction that actually matters

Two very different operations get called "splitting Base64". One is broken, one
is safe, and the difference is whether the encoder runs more than once.

**Broken — encoding chunks separately, then gluing the strings:**

```
b64(bytes[0:5000]) + b64(bytes[5000:10000])     # WRONG
```

Each `b64()` call pads its own tail independently, so `=` characters land in the
middle of the result and the 3-byte grouping restarts at the wrong offset. The
concatenation is not the encoding of the concatenated bytes. It decodes to
garbage, or fails outright.

**Safe — encoding once, then slicing the resulting string:**

```
s = b64(whole_file)          # encoder runs exactly once
s[0:8000] + s[8000:16000] + s[16000:]   # identical to s
```

String concatenation of adjacent slices is an identity operation. No padding is
created or moved, because no re-encoding happens. This is ordinary text handling,
and it is how you get a payload larger than one comfortable emission through a
string-only argument.

The rule to remember is therefore *"encode once"*, not *"never split"*. A blanket
"never split, declare the file too large" rule sounds safe but forecloses the only
technique that works, and pushes you toward the genuinely broken chunk-encode
pattern when you eventually need the size anyway.

## Building a large payload

Encode once to a file, then read back fixed-size slices and concatenate in order:

```bash
base64 -w0 report.pdf > /tmp/report.b64      # -w0: no line wrapping
wc -c < /tmp/report.b64                       # confirm ceil(n/3)*4
```

```bash
python3 -c "import sys; sys.stdout.write(open('/tmp/report.b64').read()[0:8000])"
python3 -c "import sys; sys.stdout.write(open('/tmp/report.b64').read()[8000:16000])"
```

Assemble the pieces in order into the single tool-call argument. Keep the slice
boundaries arbitrary if you like — they need not be multiples of 4, since only the
reassembled whole is ever decoded.

Two things to get right:

- **Order and completeness.** The failure mode here is not padding, it is a
  dropped or duplicated slice. Track offsets explicitly and make the last slice
  run to the end of the string rather than to a computed length.
- **No stray whitespace.** `-w0` matters; wrapped output introduces newlines that
  some decoders reject. Never insert whitespace of your own between slices.

## Size is a reliability budget, not a hard limit

In the environment where this was worked out, the tool never rejected a payload
for being long. What degrades with length is the fidelity of a single long
verbatim emission. Round-trips were verified byte-for-byte at 4,280 / 12,000 /
20,972 characters; roughly 22,000 characters was the point at which a one-shot
emission stopped feeling safe.

Treat those numbers as one measurement, not a universal constant — the honest
version of the constraint is "there is a practical ceiling per emission, find
yours by verifying". If a file exceeds what you can emit at once, slice it as
above rather than declaring it undeliverable.

## Verify the round-trip; never assume it worked

Corruption here is silent — you get a file of plausible size that no reader can
open. After uploading or sending, check:

1. **Exact byte count.** Compare the destination's reported `fileSize` against
   the local `stat -c %s`. Not "about right" — equal.
2. **Anchors at three positions.** Compare head, an interior window, and the tail
   of the round-tripped bytes against the original. Tail matters most: truncation
   and padding errors both land there.
3. **Format-level integrity.** For a PDF, confirm it still ends with `%%EOF` and
   that the `xref`/trailer parses (`python3 -c "import pypdf; pypdf.PdfReader('f.pdf')"`
   or `qpdf --check`). A structurally valid file is far stronger evidence than a
   matching length alone.

```bash
b64=$(base64 -w0 out.pdf)
[ "${#b64}" -eq $(( ( $(stat -c %s out.pdf) + 2 ) / 3 * 4 )) ] && echo "length ok"
```

## When the payload is too big, shrink the source — not the string

The encoded string is a fixed 4/3 of the file, so every byte you avoid producing
saves 1.33 characters of emission. Before resorting to slicing, look at what is
actually inside the file:

- Embedded font subsets and re-encoded images usually dominate a generated PDF
  and have nothing to do with how much content it shows. Switching to a renderer
  that uses the built-in base-14 fonts and draws vector primitives instead of
  rasterizing can cut the file several-fold in one move.
- Typographic tightening (smaller fonts, less padding) changes layout, not bytes.
  Shrinking every font and halving all padding once produced a byte-identical
  file. Measure before you spend effort there.
- Cutting whole sections of content does shrink the file, but proportionally to
  the text removed — usually a few percent. Report the real number rather than
  the hoped-for one.

If the payload still will not fit, fall back to uploading the file to storage and
sending a **link the recipient can actually open** — a Drive/S3 URL, not an
internal or AI-tool-specific URL that assumes the reader has the same tooling
you do.

## Quick reference

| Claim | Verdict |
|---|---|
| Encoded length is a multiple of 4 | True, for a complete string |
| Length = `ceil(n/3)*4` | Use this; `round(n*4/3)` is wrong |
| `=` appears only at the end, 0–2 of them | True |
| Encoding chunks separately and concatenating | Broken — corrupts the file |
| Encoding once and concatenating slices of the string | Safe — identity operation |
| Slice boundaries must be multiples of 4 | False — only the whole is decoded |
| Too big for one emission ⇒ undeliverable | False — slice it, or shrink the source |
