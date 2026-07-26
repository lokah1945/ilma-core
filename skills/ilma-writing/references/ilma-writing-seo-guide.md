# ILMA Blog Writing — SEO Guide

## Title Optimization

### Rules
- Max 60 characters
- Primary keyword at the BEGINNING
- Power words: cara, tips, rahasia, panduan, lengkap, terbaru, mudah, cepat
- Indonesian language for Indonesian audience
- Numbered lists perform well: "7 Cara X"

### Good Examples
```
"Cara Install Python di Ubuntu 22.04 — Step by Step" (52 chars)
"7 Tips Coding Lebih Cepat di VS Code" (38 chars)
"Error Git yang Sering Developer Indonesia Skip" (47 chars)
```

### Bad Examples
```
"How to Install Python on Ubuntu" (33 chars — English, no power word)
"Panduan Lengkap untuk Install Python di Ubuntu untuk Pemula" (67 chars — too long)
```

## Meta Description

### Rules
- Exactly 150-160 characters (Google truncates at ~155)
- Include primary keyword naturally
- Compelling CTA (learn, find out, discover, try)
- Mirror the search intent — what will reader get?

### Template
```
[Hook/benefit stat]. [What problem you solve]. [Specific promise + CTA].

Example:
"3 jam stuck di error yang sama? Ini 7 cara mengatasi Python Error yang langsung bisa kamu coba — dari SyntaxError sampai ModuleNotFoundError." (156 chars)
```

### Good Examples
```
"Pelajari 7 cara mengatasi error di Python dari yang paling umum sampai advanced. 
ZeroDivisionError, TypeError, ImportError — semua ada solusinya di sini." (156 chars)
```

### Bad Examples
```
"Python error handling guide" (28 chars — too short, no CTA, no benefit)
"Di artikel ini kita akan belajar tentang Python error handling dan beberapa cara untuk mengatasinya." (117 chars — too passive, no numbers, no benefit)
```

## Header Hierarchy

```
<h1> — TITLE (only one per page, contains primary keyword)
  <h2> — Main sections (3-5 per article)
    <h3> — Sub-points within sections
```

### Header Rules
- H1: Primary keyword + power word
- H2: Secondary keywords + benefit-driven
- H3: Specific topics within section
- Use parallel structure: all H2s start with verbs or nouns consistently

### Example
```markdown
# Cara Install Python di Windows — Lengkap 2024

## Kenapa Python 3.12?
[Explain the version choice]

## Download Python 3.12
[Download link + checksum verification]

## Install Python — Step by Step
[Detailed installation steps]

## Setup Virtual Environment
[Why and how]

## Verifikasi Installation
[Commands to run]
```

## Keyword Density

- Primary keyword: 1-2% (once in first 100 words, once in last 100 words, 1-2 times in body)
- Secondary keywords: once each
- DO NOT keyword stuff — Google penalizes
- Natural integration: in headers, first paragraph, last paragraph, image alt text

### Density Calculation
```
1000 word article → 10-20 primary keyword mentions max
2000 word article → 20-40 primary keyword mentions max
```

## Internal Linking

### Rules
- 2-5 internal links per article
- Link to related articles within the same category
- Use descriptive anchor text (not "click here")
- Links should be contextual, not just a list at the bottom

### Good Anchor Text
```
"Seperti yang aku jelaskan di panduan setup VS Code"
"Bagi yang masih bingung, tutorial Flask ini lebih detail"
"Error yang sama pernah aku bahas di post sebelumnya"
```

### Bad Anchor Text
```
"Click here"
"Read more"
"Learn more here"
```

## Featured Image

### Description Template
```
[Subject] — [Action/Pose] — [Style/Mood] — [Color Palette]

Example: "Developer di depan laptop, focus coding, candid office setting, 
warm lighting with blue monitor glow, professional but approachable"
```

## URL Slug

### Rules
- Lowercase, hyphens only
- Max 50 characters
- Include primary keyword
- Remove stopwords (di, yang, untuk, dengan, dari, ini, itu)
- Date optional (not required for Google)

### Good
```
cara-install-python-windows-lengkap
7-tips-vscode-untuk-developer
error-git-paling-sering-dan-solusi
```

### Bad
```
cara-install-python-di-windows-untuk-pemula-yang-mau-belajar (67 chars)
how-to-install-python (English, no power word)
```

## Reading Time & Structure

- Target: 5-7 minute read (800-1200 words) for listicles
- Target: 8-12 minute read (1500-2000 words) for how-to/tutorials
- Short paragraphs (2-4 sentences) for web reading
- Lists and bullet points break up text
- Code blocks for technical articles
- Images every 400-600 words

## SEO Checklist

```
□ Title: max 60 chars, primary keyword first, power word
□ Meta description: 150-160 chars, CTA included
□ H1: Primary keyword, one per page
□ H2: 3-5 sections, parallel structure
□ H3: Sub-points within sections
□ Primary keyword density: 1-2%
□ Internal links: 2-5 with descriptive anchor
□ External links: 2-3 to authoritative sources
□ Featured image: described + alt text
□ URL slug: lowercase, hyphens, primary keyword
```