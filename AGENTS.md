# Workspace Instructions

## Image And Illustration Tasks

When the user asks for image generation, prompt writing, prompt revision, or drawing critique:

1. Externalize constraints first. Do not rely on memory from prior image tasks.
2. Build a compact constraint pack before drafting the final prompt:
   - Subject identity anchors: face, hair, outfit, props, palette, style
   - Composition: framing, camera angle, pose, environment, lighting
   - Non-negotiable facts: counts, left/right orientation, object placement, text
   - Known failure modes from prior attempts
3. If reference images or prior failed outputs are available, compare them explicitly and list the differences instead of guessing.
4. If the user reports repeated mistakes, treat those mistakes as locked constraints and reuse them in every later image-task response in this workspace.
5. Before finalizing, run a self-check against:
   - Anatomy and counts
   - Left/right correctness
   - Character consistency across images
   - Prop placement and scale
   - Background perspective and continuity
   - Unwanted duplicates, merged limbs, missing parts, unreadable text
6. The default response structure for image tasks should be:
   - Brief task summary
   - Locked constraints
   - Avoid list or negative prompt
   - Final prompt
   - Short self-check note
7. Ask a concise clarifying question only when an ambiguity would materially change the output. Otherwise, state the assumption and continue.

## Reusable Source Of Truth

For repeated image-task issues in this workspace, use `docs/painting_review_checklist.md` as the running checklist and mistake log.
