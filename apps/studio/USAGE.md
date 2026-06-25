# voxmap-studio — usage

How to annotate with voxmap-studio: the annotation loop and the keyboard /
mouse shortcuts. For installing and launching the app, see
[README.md](README.md).

## The annotation loop

1. **Load audio** and (optionally) **initialize** the canvas with the automatic
   diarization engine. The engine fills the timeline with a first hypothesis of
   "who spoke when" so you correct rather than draw from scratch.
2. **Listen and correct.** Play the audio, and fix the hypothesis by moving,
   resizing, splitting, deleting, creating, or reassigning speaker turns.
   Segments that the engine is unsure about are highlighted (see
   [Label assistance](#label-assistance)).
3. **Confirm** each segment once you have listened to its span (`C`). Export of
   the final RTTM/JSON is gated on every segment being confirmed.
4. **Export.** The Export button always saves your work in progress as a JSON
   sidecar; the final RTTM + JSON are emitted only once all segments are
   confirmed and all attention checks are resolved.

Throughout, the tool records annotation **cost** — counts of each edit
operation and active editing time — into the JSON sidecar.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Space` | Play / pause |
| `1`–`9` | Select speaker *N* and assign it to the selected segment(s) |
| `R` | Open the recommendation panel for the selected segment (ranks speakers by similarity) |
| `S` | Split the selected segment at the playback head |
| `C` | Confirm the selected segment(s) as listened-to (annotation mode) |
| `Delete` / `Backspace` | Delete the selected segment(s) |
| `Esc` | Close the recommendation panel, or clear the selection |
| `Cmd/Ctrl` + `Z` | Undo |
| `Cmd/Ctrl` + `Shift` + `Z` | Redo |

Shortcuts are ignored while a text input is focused.

## Mouse

| Gesture | Action |
|---|---|
| Click a segment | Select it |
| Drag on empty timeline | Create a new segment |
| Drag a segment body | Move it |
| Drag a segment edge | Resize (the cursor changes to `↔` near an edge) |
| Mouse wheel | Zoom in / out (anchored at the cursor) |
| `Shift` + wheel (or horizontal scroll) | Pan along the timeline |

## Label assistance

Both aids are computed from the speaker embeddings and cluster centroids that
the automatic engine already produces, and can be toggled on or off.

- **Uncertainty highlighting.** Each segment's embedding is compared by
  similarity to its own speaker centroid and to the nearest *other* speaker
  centroid. A segment that is in fact more similar to a different speaker is
  flagged in **red** (a likely intrusion); a borderline segment — more similar
  to its own speaker, but only by a small margin — in **amber**. This directs
  attention to the turns most likely to be mislabeled.
- **Cluster gallery + recommendation.** The cluster gallery groups candidate
  segments by speaker so many turns can be confirmed or relabeled in one action.
  Pressing `R` opens a candidate panel that ranks the existing speakers by their
  similarity to the current segment; the segment's representative embedding is
  the average of the pre-computed embeddings whose time windows overlap it, so
  resizing the segment before pressing `R` shifts the embedding toward whatever
  speech the new boundaries enclose. A segment is flagged as a possible new
  speaker when no existing centroid is similar enough.

## Confirmation-gated export and attention checks

To keep automatic output from leaking out unverified, every segment carries a
`human_confirmed` flag and the final export is blocked until all segments are
confirmed. To further discourage rubber-stamping, the tool can inject a small
number of **phantom** segments — short fake turns placed in silent gaps (about
one per five minutes of audio, capped at eight). An attentive annotator who
listens finds no speech and removes it; a phantom left untouched as unverified
automatic output blocks export until it is dealt with. Each phantom is scored as
*caught* (deleted), *kept* (listened to and judged real), or *missed* (left
untouched), and the counts are recorded in the sidecar.
