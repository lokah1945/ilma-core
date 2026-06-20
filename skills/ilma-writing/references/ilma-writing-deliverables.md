# ILMA Blog Writing — Mandatory Deliverables

Every blog writing session MUST produce these fields. Missing any = incomplete delivery.

## Complete Output Package

```json
{
  "title": "[SEO-optimized title, max 60 chars, primary keyword front]",
  "meta_description": "[Exactly 150-160 chars, compelling snippet for Google]",
  "slug": "[url-friendly, lowercase, hyphens, max 50 chars]",
  "content_markdown": "[Full article in Markdown format]",
  "content_html": "[HTML version — h2/h3 headers, ul/ol lists, strong, blockquote]",
  "featured_image_suggestion": "[Detailed description for featured image, include style/color/mood]",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "categories": ["category1"],
  "internal_links_suggested": [
    "/previous-post-1",
    "/previous-post-2"
  ],
  "publish_checklist": {
    "wordpress": "✅ READY",
    "medium": "✅ READY", 
    "notion": "✅ READY"
  },
  "metadata": {
    "word_count": 0,
    "reading_time": "X min",
    "quality_score": 0.0,
    "grounded_level": "GROUNDED|PARTIALLY|FLAGGED",
    "revision_count": 0,
    "sources_used": 0
  }
}
```

## Title Rules

- Max 60 characters (SEO)
- Primary keyword first
- Power words: cara, tips, rahasia, guide, lengkap, terbaru
- NO: how to, guide to (use Indonesian: cara, panduan)

**Good:** "Cara Mengatasi Error di Python — 7 Metode Teruji" (55 chars)
**Bad:** "Panduan Lengkap Cara Memperbaiki Error di Python untuk Pemula" (72 chars)

## Meta Description Rules

- Exactly 150-160 characters
- Include primary keyword
- Compelling CTA (learn, find out, discover)
- No clickbait (overpromising)

**Good:** "Temukan 7 cara mengatasi error di Python yang sering bikin developer stuck. Dari ZeroDivisionError sampai ModuleNotFoundError — solusi praktis langsung bisa dicoba." (156 chars)
**Bad:** "Error di Python? Jangan panic! Ini dia semua solusinya!" (58 chars)

## Slug Rules

- Lowercase
- Hyphens between words
- Max 50 chars
- Include primary keyword
- No stopwords (di, yang, untuk, dengan)

**Good:** "cara-mengatasi-error-python-7-metode"
**Bad:** "cara-mengatasi-error-di-python-untuk-pemula-yang-sering-stuck"

## Content HTML Template

```html
<article>
  <h1>[TITLE]</h1>
  <p class="meta"><em>[meta_description]</em></p>
  
  <h2>[Section 1 Heading]</h2>
  <p>Opening paragraph with strong hook...</p>
  
  <h3>[Sub-point A]</h3>
  <p>Detail paragraph...</p>
  
  <h3>[Sub-point B]</h3>
  <p>Detail paragraph...</p>
  
  <blockquote>
    [Power quote or statistic from source]
  </blockquote>
  
  <h2>[Section 2 Heading]</h2>
  <p>...</p>
  
  <h2>[Section 3 Heading]</h2>
  <p>...</p>
  
  <h2>Kesimpulan</h2>
  <p>[Summary + specific CTA — NOT generic]</p>
  
  <p><strong>Tags:</strong> [tag1], [tag2], [tag3]</p>
</article>
```

## Quality Scoring

| Score | Criteria |
|-------|---------|
| 9-10 | Strong hook, comprehensive, well-sourced, clear CTA |
| 7-8 | Good but missing one element (hook/CTA/sources) |
| 5-6 | Partial, needs significant revision |
| <5 | Major gaps, re-write required |

**Minimum threshold: 8.** Below 8 → revision loop before delivery.

## Grounding Levels

| Level | Meaning | Action |
|-------|---------|--------|
| GROUNDED | All facts verified against sources | ✅ Deliver |
| PARTIALLY | Some facts unverified or estimated | ⚠️ Deliver with note |
| FLAGGED | Major fact gaps or hallucinations | ❌ Revise before delivery |