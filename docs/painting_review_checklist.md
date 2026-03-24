# Painting Review Checklist

Use this file as the source of truth for recurring image-generation mistakes. Update it whenever a new failure pattern appears.

## 1. Identity Anchors

- Subject:
- Face or expression:
- Hair:
- Outfit:
- Props:
- Color palette:
- Style or medium:

## 2. Locked Constraints

- Composition:
- Camera angle:
- Pose:
- Background:
- Lighting:
- Count-critical items:
- Left/right assignments:
- Required text or symbols:

## 3. Repeated Mistakes Log

Add one block per recurring issue.

### Mistake Item

- Problem:
- Correction rule:
- Exact wording to add to the next prompt:
- Negative wording to add if needed:

## 4. Prompt Build Template

```text
Task:
Subject:
Scene:
Style:
Locked constraints:
- ...

Avoid:
- ...

Quality checks:
- anatomy is correct
- left/right is correct
- count-critical items are correct
- props are placed correctly
- no extra limbs, fingers, or duplicate accessories
```

## 5. Preflight Review

Check these before sending a final prompt or reviewing an image:

- The subject identity is stable and specific enough to reproduce.
- Count-critical details are explicitly written.
- Left/right orientation is explicitly written.
- The prompt names the props and where they belong.
- The prompt covers known repeated mistakes.
- The negative prompt blocks obvious failure modes.
- The expected style, camera, and lighting are not left vague.

## 6. Revision Loop

After each failed output:

1. Record the exact mistake in the mistake log.
2. Rewrite the correction as a positive requirement, not only a complaint.
3. Add a negative prompt only for failure modes that are truly recurring.
4. Keep the checklist lean and remove stale items that no longer matter.
