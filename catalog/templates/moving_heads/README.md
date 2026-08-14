# Moving-head template data

This directory is the tracked data home for strict JSON `TemplateDoc` documents. It
shares the repository's `catalog/templates/` root with display `EffectRecipe` data,
while the two models remain intentionally distinct.

Python builtins load first. A configured data directory loads second, and normalized
ID/name/alias collisions fail loudly unless an override targets that exact template
ID. Overrides never steal another template's alias. These three documents are the
progressive-migration proof for P2P-T2's color, shutter, and gobo axes; tests require
each document to remain model-equal and render-byte-identical to its current Python
authoring form.

Export deterministic JSON with:

```bash
twinklr template-export --out /tmp/mh-templates
```

Validate and lint a directory with:

```bash
twinklr template-validate --template-dir catalog/templates/moving_heads
```
