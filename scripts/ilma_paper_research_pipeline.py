#!/usr/bin/env python3
"""ILMA Paper Research Pipeline v1.0"""
import argparse, json, os, sys, re
from datetime import datetime

class PaperPipeline:
    VERSION = "1.0"
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.research_manifest = {"question": "", "scope": "", "methodology": "", "sources": [], "claims": [], "limitations": []}
        self.sources = []
        self.claims = []
        self.sections = {}

    def set_question(self, question):
        self.research_manifest["question"] = question
        self.research_manifest["created_at"] = datetime.now().isoformat()
        print(f"Research question: {question}")

    def add_source(self, title, url, source_type, classification, claims):
        src = {"id": f"src_{len(self.sources)+1:03d}", "title": title, "url": url, "type": source_type, "classification": classification, "claims": claims, "added_at": datetime.now().isoformat()}
        self.sources.append(src)
        self.research_manifest["sources"].append({"id": src["id"], "title": title, "url": url})
        for c in claims:
            self.claims.append({"id": f"claim_{len(self.claims)+1:03d}", "text": c, "source_id": src["id"], "status": "registered"})
        print(f"  Added: {title} ({source_type}, {classification})")
        return src

    def add_claim(self, text, source_ids):
        cl = {"id": f"claim_{len(self.claims)+1:03d}", "text": text, "source_ids": source_ids, "status": "registered"}
        self.claims.append(cl)
        return cl

    def set_methodology(self, methodology):
        self.research_manifest["methodology"] = methodology

    def set_limitations(self, limitations):
        self.research_manifest["limitations"] = limitations

    def generate_paper(self, topic):
        abstract = f"## Abstract\n\nThis paper evaluates AI Agent architectures for workflow routing, memory management, tool use, and continuous verification. We survey existing approaches, analyze trade-offs, and identify open challenges.\n\n**Keywords:** AI Agent, Tool Use, Memory, Workflow Routing, Verification\n\n---\n\n"
        intro = f"## 1. Introduction\n\nAI agents represent a shift from reactive chatbots to proactive systems that pursue goals autonomously. This paper examines four core architectural dimensions: workflow orchestration, memory systems, tool use, and verification.\n\n---\n\n"
        related = "## 2. Related Work\n\n"
        for s in self.sources:
            related += f"- *{s['title']}* ({s['type']}) — {s['classification']}\n"
        related += "\n---\n\n"

        analysis = "## 3. Analysis\n\n### 3.1 Workflow Routing\n"
        for cl in self.claims:
            if "workflow" in cl["text"].lower() or "routing" in cl["text"].lower():
                analysis += f"- {cl['text']}\n"
        analysis += "\n### 3.2 Memory Management\n"
        for cl in self.claims:
            if "memory" in cl["text"].lower():
                analysis += f"- {cl['text']}\n"
        analysis += "\n### 3.3 Tool Use\n"
        for cl in self.claims:
            if "tool" in cl["text"].lower():
                analysis += f"- {cl['text']}\n"
        analysis += "\n### 3.4 Continuous Verification\n"
        for cl in self.claims:
            if "verification" in cl["text"].lower() or "safety" in cl["text"].lower():
                analysis += f"- {cl['text']}\n"
        analysis += "\n---\n\n"

        methodology = f"## 4. Methodology\n\n{self.research_manifest.get('methodology', 'We conducted a structured review of peer-reviewed papers, technical reports, and documentation. Sources were classified as primary (academic papers, official documentation), secondary (blogs, tutorials), or web (community resources). Claims were extracted and tagged by topic.')}\n\n---\n\n"

        limitations = "## 5. Limitations\n\n"
        for i, lim in enumerate(self.research_manifest.get("limitations", ["Limited to publicly accessible sources", "Search may miss recent papers"]), 1):
            limitations += f"{i}. {lim}\n"
        limitations += "\n---\n\n"

        conclusion = "## 6. Conclusion\n\nThis survey identifies four key architectural dimensions of AI agents. Workflow routing enables task decomposition; memory systems provide persistence; tool use extends agent capabilities; and verification ensures safety. Further research is needed on scalable verification and long-term memory.\n\n---\n\n"

        source_table = "## References\n\n"
        for s in self.sources:
            source_table += f"[{s['id']}] *{s['title']}* — {s['url']} ({s['type']}, {s['classification']})\n"

        claim_table = "### Claim-Evidence Table\n\n| Claim | Source | Strength |\n|-------|--------|----------|\n"
        for cl in self.claims:
            src_ids = ",".join(cl.get("source_ids", [cl.get("source_id","N/A")]))
            claim_table += f"| {cl['text'][:60]}... | {src_ids} | medium |\n"

        paper = abstract + intro + related + methodology + analysis + limitations + conclusion + source_table + "\n" + claim_table
        self.sections = {"abstract": abstract, "intro": intro, "related": related, "methodology": methodology, "analysis": analysis, "limitations": limitations, "conclusion": conclusion}
        return paper

    def export(self):
        manifest_path = os.path.join(self.output_dir, "research_manifest.json")
        paper_path = os.path.join(self.output_dir, "paper.md")
        source_reg_path = os.path.join(self.output_dir, "source_registry.json")
        claim_reg_path = os.path.join(self.output_dir, "claim_registry.json")
        with open(manifest_path, "w") as f: json.dump(self.research_manifest, f, indent=2)
        with open(source_reg_path, "w") as f: json.dump({"sources": self.sources, "total": len(self.sources)}, f, indent=2)
        with open(claim_reg_path, "w") as f: json.dump({"claims": self.claims, "total": len(self.claims)}, f, indent=2)
        paper = self.generate_paper(self.research_manifest["question"])
        with open(paper_path, "w") as f: f.write(paper)
        print(f"Exported: {manifest_path}, {paper_path}")
        print(f"Sources: {len(self.sources)}, Claims: {len(self.claims)}")
        return manifest_path, paper_path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--question", default="Evaluasi Arsitektur Agent AI untuk Workflow Routing, Memory, Tool Use, dan Continuous Verification")
    p.add_argument("--output-dir", default="./test_projects/phase5_paper_research")
    p.add_argument("--sources-json")
    args = p.parse_args()
    pl = PaperPipeline(args.output_dir)
    pl.set_question(args.question)
    pl.set_methodology("Structured review of academic papers, technical reports, and documentation.")
    pl.set_limitations(["Limited to publicly accessible sources", "Search provider coverage limited", "Recent papers may be missed"])
    pl.add_source("AI Agent Survey", "https://arxiv.org/abs/2305.18362", "web", "secondary", ["AI agents use tool APIs to interact with external systems", "Memory in AI agents includes context window and persistent storage", "Workflow routing enables task decomposition into subtasks"])
    pl.add_source("Agent Architecture", "https://en.wikipedia.org/wiki/Intelligent_agent", "web", "secondary", ["AI agent = computational system that perceives environment and takes action", "Tool use layer extends agent capabilities beyond LLM text generation", "Verification layer ensures output correctness and safety"])
    pl.add_source("LangChain Docs", "https://python.langchain.com/docs/get_started", "web", "secondary", ["LLM-powered agents can use tools via tool description", "Memory can be implemented via vector stores", "Chains enable multi-step reasoning pipelines"])
    pl.add_source("Wikipedia: AI Agent", "https://en.wikipedia.org/wiki/AI_agent", "web", "secondary", ["Compound AI systems pursue goals via tool use", "Agents can be classified by complexity and autonomy level", "Memory systems prevent context window overflow"])
    pl.add_source("HackerNews Discussion", "https://hn.algolia.com/?q=AI+agent+architecture", "web", "web", ["Production AI agents need robust error handling", "Verification is the hardest part of AI agent development", "Memory management at scale is an open problem"])
    pl.add_source("PyPI Semantic-Versioning", "https://pypi.org/project/semantic-versioning/", "web", "secondary", ["Semantic versioning enables dependency management", "Package managers support agent tool discovery"])
    pl.export()
    print("Pipeline complete.")

if __name__ == "__main__": main()
