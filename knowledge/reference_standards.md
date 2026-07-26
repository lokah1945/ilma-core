# External Reference Standards for Reliable AI Knowledge Work

Machine-usable standards / rubric knowledge base. Every rule below is verified against a real, authoritative source (URL cited per item). Compiled 2026-06-22.

Conventions: **[auto]** = mechanically checkable by a tool; **[manual]** = requires human/agent judgment.

---

## DOMAIN 1 — ACADEMIC DOCUMENT STRUCTURES

### 1.1 IMRaD — Original research paper structure

De-facto standard for an empirical scientific article (endorsed by NLM/NIH and ICMJE).

**Full document order:**
1. **Title**
2. **Abstract** — after title, before Introduction. Should be a *structured abstract* mirroring IMRaD (Introduction/Objective, Methods, Results, Conclusions). Self-contained ("autonomous text").
3. **Introduction** — *Why was the study done?* Background, existing knowledge, the gap, the research question/hypothesis/objective. General → specific.
4. **Methods** (Materials and Methods) — *Who, when, where, how?* Design, materials, subjects/samples, procedures. Must permit replication.
5. **Results** — *What was found?* Data/outcomes (text, tables, figures). No interpretation.
6. **Discussion** — *What do findings mean and why do they matter?* Interpretation, comparison to prior work, limitations, future directions. Specific → general.
7. **References** — after Discussion.
8. **Acknowledgements / Appendices / supplementary** — last.

**Hourglass (wine-glass) model:** wide at top (Intro, general) → narrow in middle (Methods/Results, specific) → wide at bottom (Discussion, general). Top and bottom roughly symmetric.

Sources:
- NLM/NIH Structured Abstracts: https://www.nlm.nih.gov/bsd/policy/structured_abstracts.html
- IMRAD (section semantics, hourglass): https://en.wikipedia.org/wiki/IMRAD
- Sollaci & Pereira, 50-year survey: https://pubmed.ncbi.nlm.nih.gov/15243643/

### 1.2 Indonesian "Lima Bab" (5-chapter) format — Skripsi (S1) / Tesis (S2) / Disertasi (S3)

Canonical structure across Indonesian universities. Degree levels grounded in **Perpres RI No. 8 Tahun 2012 (KKNI)**. Detail below from the UGM Pedoman Penulisan Skripsi, Tesis, dan Disertasi (DTSL FT UGM, v1 Feb 2023).

**Degree levels (KKNI):**
| Karya | Jenjang | KKNI | Core competency | Min. refs | Similarity limit (UGM) |
|---|---|---|---|---|---|
| Skripsi | S1 | Lv 6 | Apply field knowledge to solve problems (applied) | 20 | ≤ 25% |
| Tesis | S2 | Lv 8 | Develop knowledge/tech via research; must show *kebaruan* | 40 | ≤ 20% |
| Disertasi | S3 | Lv 9 | Develop *new/original* theory/knowledge (novelty) | 80 | ≤ 15% |

Same 5-bab skeleton across all three; depth/originality/publication scope escalate (S1 internal → S2 national → S3 reputable international journal).

**BAB I — PENDAHULUAN:** (a) Latar belakang; (b) Rumusan masalah (research question); (c) Tujuan penelitian; (d) Batasan penelitian (scope/limits); (e) Manfaat penelitian.

**BAB II — TINJAUAN PUSTAKA / LANDASAN TEORI:** systematic review of prior research → "alur pikir"; state of the art from recent journals; **keaslian penelitian** (originality); for S2/S3 must demonstrate **kebaruan**. Landasan teori = fundamental theory/models/equations; **contains hipotesis if needed**. Common subsections: kajian teori, penelitian terdahulu, kerangka berpikir, hipotesis.

**BAB III — METODE PENELITIAN** (passive voice): (a) Lokasi; (b) Prosedur/rancangan + bagan alir; (c) Data (primer/sekunder); (d) Alat/instrumen; (e) Parameter; (f) Metode analisis. Other faculties add: jenis/rancangan, populasi & sampel, variabel, definisi operasional, teknik pengumpulan/analisis data.

**BAB IV — HASIL DAN PEMBAHASAN:** Hasil (text/tables/figures); Pembahasan (critical analysis referencing theory + literature, compared to prior research, answering the objectives).

**BAB V — PENUTUP (KESIMPULAN DAN SARAN):** (a) Kesimpulan (concise answers to objectives, in objective order); (b) Saran (follow-up/further research).

**Front/back matter:** sampul → pengesahan → pernyataan → kata pengantar → daftar isi/tabel/gambar/lampiran → **Intisari/Abstract** (250–300 words, 5 keywords) → BAB I–V → **Daftar Pustaka** (alphabetical, hanging indent) → **Lampiran**.

Naming variants by faculty: BAB II = Tinjauan/Kajian Pustaka / Landasan/Kajian Teori; BAB III = Metode vs Metodologi; BAB V = Penutup vs Kesimpulan dan Saran.

Sources:
- UGM Pedoman (primary, KKNI tables + per-BAB detail): https://tsipil.ugm.ac.id/wp-content/uploads/sites/4/2023/02/Pedoman-Penulisan-DTSL_2023_v1-Final.pdf
- UNJ FE Pedoman 2021: https://fe.unj.ac.id/wp-content/uploads/2022/12/Pedoman-Penulisan-Proposal-Skripsi-dan-Skripsi.pdf
- USD Pedoman 2022: https://web.usd.ac.id/fakultas/psikologi/f1l3/Universitas%20Sanata%20Dharma%20-%20Pedoman%20Skripsi%20USD%20(2022).pdf
- UIN Sunan Kalijaga (PGMI): https://pgmi.uin-suka.ac.id/id/dokumen/download_dokumen/244

### 1.3 PRISMA 2020 — Systematic review reporting

Page MJ et al. "The PRISMA 2020 statement." *BMJ* 2021;372:n71. **27-item checklist** (+ separate abstract checklist) and a **4-phase flow diagram**.

**27 items in 7 sections:**
- **TITLE:** 1 Title (identify as systematic review).
- **ABSTRACT:** 2 Abstract (per separate abstract checklist).
- **INTRODUCTION:** 3 Rationale; 4 Objectives.
- **METHODS:** 5 Eligibility criteria; 6 Information sources + dates; 7 Search strategy (full, reproducible); 8 Selection process; 9 Data collection process; 10a/b Data items; 11 Study risk-of-bias assessment; 12 Effect measures; 13a–f Synthesis methods; 14 Reporting bias assessment; 15 Certainty assessment.
- **RESULTS:** 16a/b Study selection (+flow diagram, exclusions w/ reasons); 17 Study characteristics; 18 Risk of bias in studies; 19 Results of individual studies; 20a–d Results of syntheses; 21 Reporting biases; 22 Certainty of evidence.
- **DISCUSSION:** 23a–d Interpretation; limitations of evidence; limitations of review process; implications.
- **OTHER:** 24a–c Registration & protocol; 25 Support/funding; 26 Competing interests; 27 Availability of data/code/materials.

**Flow diagram phases:** (1) **Identification** — records from databases/registers + other methods; duplicates/ineligible removed before screening. (2) **Screening** — records screened → excluded; reports sought → not retrieved; assessed for eligibility → excluded with reasons. (3) **Included** — studies included.

Sources:
- PRISMA 2020 (official): https://www.prisma-statement.org/prisma-2020
- BMJ 2021;372:n71 full text: https://pmc.ncbi.nlm.nih.gov/articles/PMC8005924/ — DOI https://doi.org/10.1136/bmj.n71
- Checklist PDF: https://www.prisma-statement.org/s/PRISMA_2020_checklist.pdf

---

## DOMAIN 2 — CITATION & REFERENCING STYLES

### 2.1 APA 7th edition

**In-text (author–date):** Parenthetical `(Author, Year)` or narrative `Author (Year)`. 1 author: name every time. 2 authors: both every time (`&` parenthetical, `and` narrative). 3+ authors: `First et al.` from first citation. Quote page: `(Grady, 2019, p. 207)`.

**Reference list:** alphabetical by author. Author form `Last, F. M.`; `&` before last; list up to **20** authors (21+: first 19, `…`, final author).

**Journal article:**
`Author, A. A., Author, B. B., & Author, C. C. (Year). Title in sentence case. *Journal Title in Title Case*, *Volume*(Issue), pp–pp. https://doi.org/xxxxx`
- Article title sentence case, plain. Journal Title Case, italic. Volume italic; `(Issue)` no space/no italic; always include issue. DOI as full URL, no trailing period.
- Example: Grady, J. S., Her, M., Moreno, G., Perez, C., & Yelinek, J. (2019). Emotions in storybooks: A comparison of storybooks that represent ethnic and racial groups in the United States. *Psychology of Popular Media Culture*, *8*(3), 207–217. https://doi.org/10.1037/ppm0000185

**Book:**
`Author, A. A. (Year). *Title in sentence case* (edition). Publisher.`
- Title italic, sentence case. **No publisher location/city** in APA 7. DOI as URL if present.
- Example: Fincher-Kiefer, R. (2019). *How the body shapes knowledge: Empirical support for embodied cognition*. American Psychological Association.

Sources: https://apastyle.apa.org/style-grammar-guidelines/references/examples/journal-article-references · https://apastyle.apa.org/style-grammar-guidelines/references/examples/book-references · https://apastyle.apa.org/style-grammar-guidelines/citations/basic-principles/author-date · https://apastyle.apa.org/blog/more-than-20-authors · https://apastyle.apa.org/blog/publisher-locations-in-book-references

### 2.2 IEEE

**In-text:** bracketed number `[1]`, assigned in order of first appearance, reused (not renumbered). Multiple: `[1], [3], [5]` or range `[1]–[3]`. Can be a grammatical noun: `as in [4]`.

**Reference list:** in citation order, each prefixed `[#]`. Author form `A. B. Last` (initials first); `and` before last; up to **6** authors, **>6** → first author + `et al.`

**Journal article:**
`[#] A. B. Last, C. D. Last, and E. F. Last, "Title of article," *Abbrev. Journal Title*, vol. x, no. x, pp. xxx–xxx, Abbrev. Month Year.`
- Title in double quotes, sentence case. Journal abbreviated + italic. `vol.`/`no.`/`pp.` lowercase. Abbrev. month + year.
- Example: [4] G. Liu, K. Y. Lee, and H. F. Jordan, "TDM and TWDM de Bruijn networks and shufflenets for optical communications," *IEEE Trans. Comp.*, vol. 46, pp. 695–701, Jun. 1997.

**Book:**
`[#] A. B. Last, *Title of Book*, xth ed. City, State/Country: Publisher, Year, pp. xxx–xxx.`
- Title italic, title case. Edition `2nd ed.,` if not first. **Includes city: publisher** (unlike journals).
- Example: [2] W.-K. Chen, *Linear Networks and Systems*. Belmont, CA: Wadsworth, 1993, pp. 123–135.

Sources: https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf · https://researchguides.njit.edu/ieee-citation/articles · https://pitt.libguides.com/citationhelp/ieee

### 2.3 Vancouver (ICMJE / NLM)

**In-text:** number in citation order, as `(1)` or superscript `¹` (journal house style). Reused on subsequent cites. Multiple `(1,2)` or range `(3–5)`. Authors never named in text.

**Reference list:** in citation order. Author form `Last FF` (surname + initials, **no periods**, max 2 initials). Comma-separated. List up to **6**; **≥7** → first 6 + `et al.` (ICMJE rule; strict NLM *Citing Medicine* lists all — make configurable per target journal).

**Journal article:**
`#. Last AA, Last BB, Last CC. Title in sentence case. Abbrev Journal Title. Year Mon DD;Volume(Issue):pp-pp.`
- Title plain, sentence case. Journal NLM-abbreviated, **not italic**. Date block has no spaces: `Year;Vol(Issue):pages.` Pages may be abbreviated (`284-7`).
- Example: 1. Halpern SD, Ubel PA, Caplan AL. Solid-organ transplantation in HIV-infected patients. N Engl J Med. 2002 Jul 25;347(4):284-7.

**Book:**
`#. Last AA, Last BB. Title of book. Edition. Place: Publisher; Year.`
- Title plain, sentence case. `City: Publisher; Year.` (semicolon before year). Includes place of publication.
- Example: 1. Murray PR, Rosenthal KS, Kobayashi GS, Pfaller MA. Medical microbiology. 4th ed. St. Louis: Mosby; 2002.

Sources: https://www.nlm.nih.gov/bsd/uniform_requirements.html · https://www.icmje.org/recommendations/browse/manuscript-preparation/preparing-for-submission.html

### 2.4 Style comparison (for a formatter)
| Feature | APA 7 | IEEE | Vancouver |
|---|---|---|---|
| In-text | `(Author, Year)` | `[1]` | `(1)` / superscript |
| Ref order | alphabetical | citation order | citation order |
| Author form | `Last, F. M.` | `F. M. Last` | `Last FM` (no periods) |
| Connector | `&` | `and` | `,` |
| Max authors (ref) | 20 (21+: 19…last) | 6 (>6: +et al.) | 6 (≥7: +et al.) |
| Article title | sentence, plain | sentence, **quotes** | sentence, plain |
| Journal | full, Title Case, *italic* | abbrev, *italic* | NLM-abbrev, plain |
| Vol/issue | `*Vol*(Iss), pp.` | `vol. x, no. x, pp.` | `Year;Vol(Iss):pp.` |
| Book publisher city | **omitted** | included | included |
| Book title | *italic* sentence | *italic* title case | plain sentence |

---

## DOMAIN 3 — SAFETY-CRITICAL / SECURE CODING STANDARDS

### 3.1 NASA/JPL "Power of Ten" (Holzmann, IEEE Computer, Jun 2006)

1. Simple control flow only — no `goto`, `setjmp`/`longjmp`, recursion. **[auto]**
2. All loops have a fixed, statically-provable upper bound (sole exception: intentionally non-terminating schedulers). **[auto]**
3. No dynamic memory allocation after initialization (no `malloc`/`free`). **[auto]**
4. Functions ≤ ~60 lines (one page). **[auto]**
5. ≥ 2 assertions per function on average; assertions side-effect-free and take recovery action. **[auto]**
6. Declare data at the smallest possible scope. **[auto]**
7. Check return value of every non-void function (or cast `(void)`); validate all parameters. **[auto]**
8. Limit preprocessor to includes + simple macros (no token-pasting, varargs, recursion; minimal `#ifdef`). **[auto]**
9. Limit pointers: ≤ 2 levels of dereference per expression; no function pointers. **[auto]**
10. Compile with all warnings on (zero warnings) + pass ≥1 static analyzer daily from day one. **[auto]**

Sources: https://spinroot.com/p10/ · https://spinroot.com/gerard/pdf/P10.pdf

### 3.2 MISRA C (C:2012; latest C:2025)

Guidelines for C in safety/critical embedded systems. C:2012 = **143 rules + 16 directives**. Rules are checkable from source; directives relate to process/interpretation.

**Compliance categories:** **Mandatory** (no deviation), **Required** (deviation only with formal documentation), **Advisory** (recommended). **Decidability** (rules only): **Decidable [auto]** (tool answers definitively); **Undecidable [manual-assisted]** (tool flags possible violation, needs review). Scope: Single TU vs System.

**Representative rules:** no dynamic memory; no recursion; restricted/no `goto` (no backward goto); structured control flow (`if…else if` ends in `else`; `switch` has `default`); no information-losing/sign-changing implicit conversions (essential-type model); fixed-width types where size matters; do not ignore failable return values.

Sources: https://misra.org.uk/ · https://en.wikipedia.org/wiki/MISRA_C

### 3.3 SEI CERT C/C++ Secure Coding

IDs `XYZnn-L`: `nn` 00–29 = recommendations, 30–99 = rules; `L` = `-C`/`-CPP`.

**Category sections:** PRE Preprocessor · DCL Declarations · EXP Expressions · INT Integers · FLP Floating Point · ARR Arrays · STR Strings · MEM Memory Mgmt · FIO I/O · ENV Environment · SIG Signals · ERR Error Handling · API · CON Concurrency · MSC Misc · POS POSIX · WIN Windows.

**Risk scoring (each axis 1–3):** Severity (1 Low / 2 Medium / 3 High=arbitrary code) × Likelihood (1 Unlikely / 2 Probable / 3 Likely) × Remediation Cost (1 High / 2 Medium / 3 Low) = **Priority 1–27**. Levels: **L1** = 12–27 (fix first); **L2** = 6–9; **L3** = 1–4.

Sources: https://wiki.sei.cmu.edu/confluence/display/c · https://cmu-sei.github.io/secure-coding-standards/sei-cert-c-coding-standard/front-matter/introduction/how-this-coding-standard-is-organized

### 3.4 OWASP Top 10 (2021) + ASVS

**Top 10:2021:** A01 Broken Access Control · A02 Cryptographic Failures · A03 Injection (incl. XSS) · A04 Insecure Design · A05 Security Misconfiguration · A06 Vulnerable & Outdated Components · A07 Identification & Authentication Failures · A08 Software & Data Integrity Failures · A09 Security Logging & Monitoring Failures · A10 Server-Side Request Forgery (SSRF). (Newer Top 10:2025 exists at https://owasp.org/Top10/2025/.)

**ASVS — verification levels:** **L1** opportunistic/minimum (only level fully human pen-testable without source) · **L2** standard, for apps with sensitive data (recommended for most) · **L3** advanced/high-assurance (critical apps). Mapped to NIST AAL1/2/3.

**ASVS v5.0 chapters (17):** V1 Encoding & Sanitization · V2 Validation & Business Logic · V3 Web Frontend · V4 API & Web Service · V5 File Handling · V6 Authentication · V7 Session Mgmt · V8 Authorization · V9 Self-contained Tokens · V10 OAuth/OIDC · V11 Cryptography · V12 Secure Communication · V13 Configuration · V14 Data Protection · V15 Secure Coding & Architecture · V16 Security Logging & Error Handling · V17 WebRTC.

Sources: https://owasp.org/Top10/2021/ · https://owasp.org/www-project-application-security-verification-standard/ · https://cheatsheetseries.owasp.org/IndexASVS.html

### 3.5 DO-178C — Airborne software certification

Design Assurance Level (DAL) set from failure-condition severity (system safety assessment). Higher DAL ⇒ more rigor (Level A includes MC/DC structural coverage).

| DAL | Failure condition | Effect | Failure-rate target | Approx. objectives |
|---|---|---|---|---|
| A | Catastrophic | Loss of aircraft / multiple fatalities | ≤ 1e-9 /flt-hr | 71 (30 w/ independence) |
| B | Hazardous/Severe-Major | Serious injuries / possibly 1 fatality | ≤ 1e-7 | 69 |
| C | Major | Significant safety-margin reduction | ≤ 1e-5 | 62 |
| D | Minor | Slight reduction; inconvenience | none | 26 |
| E | No Safety Effect | No effect | none | 0 |

Sources: https://en.wikipedia.org/wiki/DO-178C · https://thecloudstrap.com/design-assurance-level-dal-in-do-178c/

---

## DOMAIN 4 — NOVEL / FICTION CRAFT STRUCTURES

### 4.1 Three-act structure (~25% / 50% / 25%)
- **Act 1 Setup (~25%):** Exposition → **Inciting Incident** → **Plot Point 1** (~25%, protagonist commits).
- **Act 2 Confrontation (~50%):** Rising action → **Midpoint** (~50%, stakes raised, reactive→proactive) → **Plot Point 2** (resolve to confront antagonist).
- **Act 3 Resolution (~25%):** Pre-climax / dark night → **Climax** → **Denouement**.

Sources: https://reedsy.com/blog/guide/story-structure/three-act-structure/ · https://en.wikipedia.org/wiki/Three-act_structure

### 4.2 Save the Cat! beat sheet (Blake Snyder) — 15 beats
1 Opening Image (0–1%) · 2 Theme Stated (~5%) · 3 Set-Up (1–10%) · 4 Catalyst (10%) · 5 Debate (10–20%) · 6 Break into Two (20%) · 7 B Story (22%) · 8 Fun & Games (20–50%) · 9 Midpoint (50%) · 10 Bad Guys Close In (50–75%) · 11 All Is Lost (75%) · 12 Dark Night of the Soul (75–80%) · 13 Break into Three (80%) · 14 Finale (80–99%) · 15 Final Image (99–100%).

Sources: https://savethecat.com/get-started · https://reedsy.com/blog/guide/story-structure/save-the-cat-beat-sheet/

### 4.3 Hero's Journey (Vogler's 12 stages)
**Departure:** 1 Ordinary World · 2 Call to Adventure · 3 Refusal of the Call · 4 Meeting the Mentor · 5 Crossing the First Threshold.
**Initiation:** 6 Tests, Allies, Enemies · 7 Approach to the Inmost Cave · 8 The Ordeal · 9 Reward (Seizing the Sword).
**Return:** 10 The Road Back · 11 Resurrection · 12 Return with the Elixir.

Sources: https://www.movieoutline.com/articles/the-hero-journey-mythic-structure-of-joseph-campbell-monomyth.html · https://www.storyflint.com/blog/heros-journey-christopher-vogler

### 4.4 Snowflake Method (Randy Ingermanson) — 10 steps
1 One-sentence summary (~15 words) · 2 One-paragraph summary (setup + 3 disasters + ending) · 3 One-page character summaries (motivation/goal/conflict/epiphany) · 4 One-page synopsis (expand each step-2 sentence to a paragraph) · 5 Character synopses (1 page major / ½ page minor, character POV) · 6 Four-page synopsis · 7 Character charts/bibles · 8 Scene-list spreadsheet (POV, what happens, page count) · 9 Scene narrative/plan (optional) · 10 Write the first draft.

Source: https://www.advancedfictionwriting.com/articles/snowflake-method/

**Cross-map:** Break into Two ≈ Plot Point 1 ≈ Crossing the Threshold; Midpoint shared; All Is Lost / Dark Night ≈ the Ordeal; Break into Three ≈ Plot Point 2; Finale ≈ Climax/Resurrection.

---

## DOMAIN 5 — VERIFIABLE CODE-QUALITY TOOLING (open source)

| Tool | Lang(s) | Category | Catches | Command | URL |
|---|---|---|---|---|---|
| ruff | Python | Linter+Formatter | pyflakes(F)/pycodestyle(E,W)/isort(I)/pyupgrade(UP)/bugbear(B); formatting; 900+ rules; 10–100x faster | `ruff check [--fix]` / `ruff format` | https://docs.astral.sh/ruff/ |
| mypy | Python | Type checker | PEP 484 type errors (bad args/returns/operands); gradual typing | `mypy <pkg>` | https://mypy.readthedocs.io/ |
| bandit | Python | SAST | hardcoded creds (B105–107), `shell=True` (B602), weak crypto (B324/B505), unsafe yaml.load (B506), SQLi (B608), TLS issues (B501–504) | `bandit -r <dir>` | https://github.com/PyCQA/bandit |
| black | Python | Formatter | opinionated formatting (ruff predecessor) | `black <path>` | https://github.com/psf/black |
| flake8 | Python | Linter | pyflakes+pycodestyle+mccabe (ruff predecessor) | `flake8 <path>` | https://github.com/PyCQA/flake8 |
| ESLint | JS/TS | Linter | bugs, bad patterns, style (`no-unused-vars`, `no-undef`); extensible | `npx eslint <path>` | https://eslint.org/ |
| tsc | TS/JS | Type checker | type-safety errors; emits JS/.d.ts | `tsc --noEmit` | https://www.typescriptlang.org/ |
| Prettier | JS/TS/CSS/MD/+ | Formatter | reprints from AST for consistent formatting (not correctness) | `npx prettier --write .` | https://prettier.io/ |
| clang-tidy | C/C++ | Linter/analyzer | bugprone-, cppcoreguidelines-, modernize-, performance-, readability-, **cert-** (CERT), clang-analyzer- | `clang-tidy file.cpp` | https://clang.llvm.org/extra/clang-tidy/ |
| cppcheck | C/C++ | Analyzer | UB (null deref, div0, overflow, uninit), memory leaks, buffer overruns; **MISRA C/C++, CERT C/C++** rule sets | `cppcheck --enable=all <path>` | https://cppcheck.sourceforge.io/ |
| Semgrep | 30+ | SAST/pattern | security + bug patterns via registry rules (`p/default`, `p/python`); code-like rules | `semgrep scan --config auto` | https://semgrep.dev/ |
| CodeQL | 8 langs | SAST/semantic | vulnerabilities + variants via QL queries (code-as-data) | `codeql database create … && … analyze …` | https://codeql.github.com/ |
| SonarQube | 40+ | Quality+security platform | bugs, vulnerabilities, security hotspots, code smells (7000+ rules) | `sonar-scanner` | https://www.sonarsource.com/products/sonarqube/ |

**Standards bridge:** clang-tidy `cert-*` checks implement CERT C/C++; cppcheck implements MISRA + CERT directly — use either to demonstrate conformance to §3.2/§3.3.

---

## CAVEATS FOR IMPLEMENTERS
- Vancouver max-authors has two variants: ICMJE = first 6 + et al.; strict NLM *Citing Medicine* lists all. Make configurable per target journal.
- Indonesian BAB naming varies by faculty (see §1.2). Treat names as aliases, not fixed strings.
- DO-178C objective counts vary slightly by source (independence vs total); figures are widely-cited Annex A totals.
- OWASP / ASVS versions evolve (Top 10:2025, ASVS v5.0 17 chapters vs v4.0 14 chapters) — pin a version in config.
- MISRA rule IDs differ across C:2004/2012/2025; named examples used rather than IDs.
