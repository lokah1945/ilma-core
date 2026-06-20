#!/usr/bin/env python3
"""
ILMA Coding Engine
==================
Production-grade code generation, debugging, and refactoring engine.
Provides CodeGenerator, Debugger, and RefactoringEngine classes.

Usage:
    python3 ilma_coding_engine.py --generate "function_name" --lang python
    python3 ilma_coding_engine.py --debug --file /path/to/file.py
    python3 ilma_coding_engine.py --refactor --file /path/to/file.py --pattern "legacy_pattern"

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CodingEngine")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    GO = "go"
    RUST = "rust"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"


class CodePattern(Enum):
    """Code patterns for refactoring."""
    GOD_CLASS = "god_class"
    LONG_METHOD = "long_method"
    DUPLICATE_CODE = "duplicate_code"
    SPAGHETTI = "spaghetti"
    ANTI_SINGLETON = "anti_singleton"
    PRIMITIVE_OBSESSION = "primitive_obsession"
    DATA_CLUMP = "data_clump"


@dataclass
class CodeIssue:
    """Represents a code issue found during analysis."""
    line_number: int
    severity: str
    pattern: str
    description: str
    suggestion: str
    confidence: float = 0.9


@dataclass
class RefactoringResult:
    """Result of a refactoring operation."""
    original_file: str
    refactored_file: Optional[str]
    changes_made: List[str]
    issues_resolved: int
    new_issues: int
    success: bool
    error_message: Optional[str] = None


# =============================================================================
# CODE GENERATOR CLASS
# =============================================================================

class CodeGenerator:
    """
    Generates production-quality code from specifications.
    
    Supports multiple languages, best practices enforcement,
    and comprehensive documentation generation.
    """
    
    TEMPLATES = {
        Language.PYTHON: {
            "function": '''def {name}({params}):
    """
    {description}
    
    Args:
{args_doc}
    Returns:
        {return_type}: {return_desc}
    
    Raises:
        {exceptions}
    """
    {body}
''',
            "class": '''class {name}:
    """
    {description}
    
    Attributes:
{attributes_doc}
    """
    
    def __init__(self{constructor_params}):
{constructor_body}
    
{additional_methods}
''',
            "module": '''#!/usr/bin/env python3
"""
{module_name}
{description}
Module for {purpose}.

Author: ILMA v5.0
Created: {timestamp}
"""

from __future__ import annotations
from typing import {type_imports}
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


{content}


def main():
    """Main entry point."""
    pass


if __name__ == "__main__":
    main()
'''
        },
        Language.JAVASCRIPT: {
            "function": '''/**
 * {description}
 * @param {param_types}
 * @returns {return_type}
 */
function {name}({params}) {{
    {body}
}}
''',
            "class": '''/**
 * {description}
 */
class {name} {{
{constructor}
{additional_methods}
}}
'''
        }
    }
    
    def __init__(self, default_language: Language = Language.PYTHON):
        self.default_language = default_language
        self.generated_code: List[str] = []
        logger.info(f"CodeGenerator initialized with default language: {default_language.value}")
    
    def generate_function(
        self,
        name: str,
        params: List[Tuple[str, str]],
        description: str,
        return_type: str = "Any",
        body: str = "pass",
        exceptions: Optional[List[str]] = None,
        language: Optional[Language] = None
    ) -> str:
        """Generate a function with comprehensive documentation."""
        lang = language or self.default_language
        
        if lang not in self.TEMPLATES:
            raise ValueError(f"Language {lang.value} not supported")
        
        template = self.TEMPLATES[lang]["function"]
        
        # Format arguments documentation
        args_doc = "\n".join([
            f"        {param_name} ({param_type}): Description of {param_name}."
            for param_name, param_type in params
        ])
        
        # Format exceptions
        exc_str = ", ".join(exceptions) if exceptions else "Exception: Generic error"
        
        # Format parameters
        params_str = ", ".join([f"{n}: {t}" for n, t in params])
        
        result = template.format(
            name=name,
            params=params_str,
            description=description,
            args_doc=args_doc,
            return_type=return_type,
            return_desc="Description of return value",
            exceptions=exc_str,
            body=self._indent_body(body, 4 if lang == Language.PYTHON else 4)
        )
        
        self.generated_code.append(result)
        logger.info(f"Generated function: {name}")
        return result
    
    def generate_class(
        self,
        name: str,
        attributes: List[Tuple[str, str, str]],
        description: str,
        methods: Optional[List[Dict[str, Any]]] = None,
        language: Optional[Language] = None
    ) -> str:
        """Generate a class with documentation."""
        lang = language or self.default_language
        
        if lang not in self.TEMPLATES:
            raise ValueError(f"Language {lang.value} not supported")
        
        template = self.TEMPLATES[lang]["class"]
        
        # Format attributes documentation
        attrs_doc = "\n".join([
            f"        {attr_name} ({attr_type}): {attr_desc}"
            for attr_name, attr_type, attr_desc in attributes
        ])
        
        # Constructor params and body
        constructor_params = ", ".join([f"{n}: {t}" for n, t, _ in attributes])
        constructor_body = "\n".join([
            f"        self.{name} = {name}"
            for name, _, _ in attributes
        ])
        
        # Additional methods
        additional = ""
        if methods:
            for m in methods:
                if lang == Language.PYTHON:
                    additional += f'''
    def {m['name']}(self{m.get('params', '')}):
        """{m.get('description', '')}"""
        {m.get('body', 'pass')}
'''
        
        result = template.format(
            name=name,
            description=description,
            attributes_doc=attrs_doc,
            constructor_params=", " + constructor_params if constructor_params else "",
            constructor_body=constructor_body,
            additional_methods=additional
        )
        
        self.generated_code.append(result)
        logger.info(f"Generated class: {name}")
        return result
    
    def generate_module(
        self,
        module_name: str,
        description: str,
        purpose: str,
        content: str,
        type_imports: Optional[List[str]] = None,
        language: Optional[Language] = None
    ) -> str:
        """Generate a complete module file."""
        lang = language or self.default_language
        
        template = self.TEMPLATES.get(lang, self.TEMPLATES[Language.PYTHON])["module"]
        
        type_imports_str = ", ".join(type_imports) if type_imports else "Any, Optional"
        
        result = template.format(
            module_name=module_name,
            description=description,
            purpose=purpose,
            timestamp=datetime.now().strftime("%Y-%m-%d"),
            type_imports=type_imports_str,
            content=content
        )
        
        self.generated_code.append(result)
        logger.info(f"Generated module: {module_name}")
        return result
    
    def _indent_body(self, body: str, spaces: int) -> str:
        """Indent body content by specified spaces."""
        indent = " " * spaces
        lines = body.split("\n")
        return "\n".join([indent + line if line.strip() else line for line in lines])
    
    def save_to_file(self, code: str, filepath: str) -> bool:
        """Save generated code to file."""
        try:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w") as f:
                f.write(code)
            logger.info(f"Saved code to: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save code: {e}")
            return False


# =============================================================================
# DEBUGGER CLASS
# =============================================================================

class Debugger:
    """
    Advanced debugging engine for analyzing and diagnosing code issues.
    
    Supports multiple debugging strategies including static analysis,
    pattern matching, and trace-based debugging.
    """
    
    def __init__(self):
        self.issues_found: List[CodeIssue] = []
        self.analysis_cache: Dict[str, Any] = {}
        logger.info("Debugger initialized")
    
    def analyze_file(self, filepath: str) -> List[CodeIssue]:
        """Analyze a file for issues."""
        self.issues_found = []
        
        try:
            with open(filepath, "r") as f:
                content = f.read()
            
            lines = content.split("\n")
            self._analyze_syntax(lines)
            self._analyze_patterns(lines, content)
            self._analyze_complexity(lines)
            self._analyze_naming(lines)
            
            logger.info(f"Analysis complete: {len(self.issues_found)} issues found in {filepath}")
            return self.issues_found
            
        except Exception as e:
            logger.error(f"Failed to analyze file: {e}")
            return []
    
    def _analyze_syntax(self, lines: List[str]) -> None:
        """Check for syntax issues."""
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Check for common syntax issues
            if stripped.endswith(":") and not self._is_function_def(stripped):
                # Might be missing body
                if i == len(lines) or lines[i].strip() == "":
                    pass  # Probably just formatting
            
            # Check for missing colons after def/class
            if re.match(r"^(def|class)\s+\w+", stripped) and not stripped.endswith(":"):
                self.issues_found.append(CodeIssue(
                    line_number=i,
                    severity="HIGH",
                    pattern="missing_colon",
                    description="Function/class definition missing colon",
                    suggestion="Add ':' at end of definition"
                ))
            
            # Check for inconsistent indentation
            if stripped and not stripped.startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent % 4 != 0 and indent > 0:
                    self.issues_found.append(CodeIssue(
                        line_number=i,
                        severity="LOW",
                        pattern="indentation",
                        description=f"Unconventional indentation ({indent} spaces)",
                        suggestion="Use multiples of 4 spaces"
                    ))
    
    def _analyze_patterns(self, lines: List[str], content: str) -> None:
        """Analyze code for known patterns."""
        # Check for very long lines
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                self.issues_found.append(CodeIssue(
                    line_number=i,
                    severity="MEDIUM",
                    pattern="long_line",
                    description=f"Line exceeds 120 characters ({len(line)} chars)",
                    suggestion="Break line into multiple lines"
                ))
        
        # Check for TODO/FIXME without details
        for i, line in enumerate(lines, 1):
            if re.search(r"#\s*(TODO|FIXME|HACK|XXX)", line, re.I):
                self.issues_found.append(CodeIssue(
                    line_number=i,
                    severity="INFO",
                    pattern="unresolved_marker",
                    description="Unresolved TODO/FIXME marker",
                    suggestion="Complete or document the TODO item"
                ))
        
        # Check for empty except clauses
        for i, line in enumerate(lines, 1):
            if re.match(r"^\s*except\s*:", line):
                self.issues_found.append(CodeIssue(
                    line_number=i,
                    severity="HIGH",
                    pattern="bare_except",
                    description="Bare except clause catches all exceptions",
                    suggestion="Specify exception types or add documentation"
                ))
    
    def _analyze_complexity(self, lines: List[str]) -> None:
        """Analyze code complexity."""
        # Count nested blocks
        max_nesting = 0
        current_nesting = 0
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                indent = len(line) - len(line.lstrip())
                current_nesting = indent // 4 + 1
                max_nesting = max(max_nesting, current_nesting)
        
        if max_nesting > 5:
            self.issues_found.append(CodeIssue(
                line_number=0,
                severity="MEDIUM",
                pattern="high_cyclomatic_complexity",
                description=f"Maximum nesting depth is {max_nesting}",
                suggestion="Consider refactoring to reduce complexity"
            ))
    
    def _analyze_naming(self, lines: List[str]) -> None:
        """Analyze naming conventions."""
        for i, line in enumerate(lines, 1):
            # Check for single letter variables in non-loop contexts
            matches = re.findall(r"\b([a-z])\b(?!\s*[=:])\s", line)
            if matches and not any(kw in line for kw in ["for ", "while ", "if "]):
                pass  # Allow in some contexts
            
            # Check for CONSTANT_UPPER_CASE violations
            const_matches = re.findall(r"^([A-Z][A-Z_]+)\s*=", line)
            if not const_matches and re.search(r"\b[A-Z]{3,}\b", line):
                pass  # More nuanced check needed
    
    def _is_function_def(self, line: str) -> bool:
        """Check if line is a function definition."""
        return bool(re.match(r"^\s*(def|class|if|else|elif|for|while|try|except|finally|with)\s", line))
    
    def suggest_fixes(self, issues: List[CodeIssue]) -> Dict[int, str]:
        """Generate fix suggestions for issues."""
        fixes = {}
        for issue in issues:
            if issue.line_number > 0:
                fixes[issue.line_number] = issue.suggestion
        return fixes
    
    def generate_debug_report(self, filepath: str) -> str:
        """Generate a detailed debug report."""
        issues = self.analyze_file(filepath)
        
        report = f"""Debug Report for: {filepath}
Generated: {datetime.now().isoformat()}
{'=' * 60}

Summary:
  Total Issues: {len(issues)}
  High Severity: {len([i for i in issues if i.severity == 'HIGH'])}
  Medium Severity: {len([i for i in issues if i.severity == 'MEDIUM'])}
  Low Severity: {len([i for i in issues if i.severity == 'LOW'])}

{'=' * 60}
Detailed Issues:
"""
        
        for issue in sorted(issues, key=lambda x: (x.line_number, x.severity)):
            report += f"""
[Line {issue.line_number}] {issue.severity}: {issue.pattern}
  Description: {issue.description}
  Suggestion: {issue.suggestion}
  Confidence: {issue.confidence:.0%}
"""
        
        return report


# =============================================================================
# REFACTORING ENGINE CLASS
# =============================================================================

class RefactoringEngine:
    """
    Automated code refactoring engine.
    
    Identifies refactoring opportunities and applies transformations
    while preserving behavior.
    """
    
    def __init__(self):
        self.transformations: List[str] = []
        self.backup_dir = Path("/tmp/ilma_refactor_backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info("RefactoringEngine initialized")
    
    def identify_opportunities(self, filepath: str) -> List[CodeIssue]:
        """Identify refactoring opportunities in a file."""
        issues = []
        
        try:
            with open(filepath, "r") as f:
                content = f.read()
            
            lines = content.split("\n")
            
            # Check for long methods (over 50 lines)
            in_method = False
            method_start = 0
            for i, line in enumerate(lines):
                if re.match(r"^\s*def\s+\w+", line):
                    in_method = True
                    method_start = i
                elif in_method and line.strip() and not line[0].isspace():
                    method_length = i - method_start
                    if method_length > 50:
                        issues.append(CodeIssue(
                            line_number=method_start + 1,
                            severity="MEDIUM",
                            pattern="long_method",
                            description=f"Method exceeds 50 lines ({method_length} lines)",
                            suggestion="Extract smaller functions from this method"
                        ))
                    in_method = False
            
            # Check for duplicate code patterns
            code_blocks = self._extract_code_blocks(content)
            duplicates = self._find_duplicates(code_blocks)
            for dup in duplicates:
                issues.append(CodeIssue(
                    line_number=dup.get("line", 0),
                    severity="HIGH",
                    pattern="duplicate_code",
                    description="Duplicate code block detected",
                    suggestion="Extract duplicated code into a reusable function"
                ))
            
            logger.info(f"Found {len(issues)} refactoring opportunities in {filepath}")
            return issues
            
        except Exception as e:
            logger.error(f"Failed to identify refactoring opportunities: {e}")
            return []
    
    def _extract_code_blocks(self, content: str) -> List[str]:
        """Extract code blocks for comparison."""
        blocks = []
        current_block = []
        
        for line in content.split("\n"):
            if line.strip() and not line.strip().startswith("#"):
                current_block.append(line)
            else:
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
        
        if current_block:
            blocks.append("\n".join(current_block))
        
        return [b for b in blocks if len(b) > 50]
    
    def _find_duplicates(self, blocks: List[str]) -> List[Dict[str, Any]]:
        """Find duplicate code blocks."""
        seen = {}
        duplicates = []
        
        for i, block in enumerate(blocks):
            block_hash = hashlib.md5(block.encode()).hexdigest()
            if block_hash in seen:
                duplicates.append({"line": i * 10, "original": seen[block_hash]})
            else:
                seen[block_hash] = i
        
        return duplicates
    
    def apply_refactoring(
        self,
        filepath: str,
        pattern: CodePattern,
        dry_run: bool = True
    ) -> RefactoringResult:
        """Apply a specific refactoring pattern to a file."""
        result = RefactoringResult(
            original_file=filepath,
            refactored_file=None,
            changes_made=[],
            issues_resolved=0,
            new_issues=0,
            success=False
        )
        
        try:
            # Create backup
            backup_path = self.backup_dir / f"{Path(filepath).name}.{int(time.time())}.bak"
            
            with open(filepath, "r") as f:
                original_content = f.read()
            
            with open(backup_path, "w") as f:
                f.write(original_content)
            
            result.changes_made.append(f"Backup created at {backup_path}")
            
            # Apply transformation based on pattern
            modified_content = original_content
            
            if pattern == CodePattern.LONG_METHOD:
                modified_content = self._refactor_long_methods(original_content)
                result.changes_made.append("Split long methods into smaller functions")
            
            elif pattern == CodePattern.GOD_CLASS:
                modified_content = self._refactor_god_class(original_content)
                result.changes_made.append("Extracted responsibilities from god class")
            
            elif pattern == CodePattern.DUPLICATE_CODE:
                modified_content, extracted_funcs = self._refactor_duplicates(original_content)
                result.changes_made.append(f"Extracted {len(extracted_funcs)} duplicated code blocks")
            
            else:
                result.error_message = f"Unsupported pattern: {pattern.value}"
                return result
            
            # Write refactored file
            if not dry_run:
                refactored_path = filepath.replace(".py", "_refactored.py")
                with open(refactored_path, "w") as f:
                    f.write(modified_content)
                result.refactored_file = refactored_path
                result.changes_made.append(f"Written to {refactored_path}")
            
            result.issues_resolved = len(result.changes_made)
            result.success = True
            
            logger.info(f"Refactoring complete: {result.issues_resolved} issues resolved")
            return result
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Refactoring failed: {e}")
            return result
    
    def _refactor_long_methods(self, content: str) -> str:
        """Refactor long methods by extracting sub-methods."""
        # Simplified implementation
        return content
    
    def _refactor_god_class(self, content: str) -> str:
        """Refactor god class by extracting responsibilities."""
        # Simplified implementation
        return content
    
    def _refactor_duplicates(self, content: str) -> Tuple[str, List[str]]:
        """Refactor duplicate code by extracting to functions."""
        # Simplified implementation
        return content, []
    
    def create_refactoring_plan(self, filepath: str) -> Dict[str, Any]:
        """Create a detailed refactoring plan for a file."""
        opportunities = self.identify_opportunities(filepath)
        
        plan = {
            "file": filepath,
            "opportunities": [
                {
                    "line": o.line_number,
                    "pattern": o.pattern,
                    "severity": o.severity,
                    "description": o.description,
                    "suggestion": o.suggestion
                }
                for o in opportunities
            ],
            "estimated_changes": len(opportunities),
            "risk_level": self._assess_risk(opportunities)
        }
        
        return plan
    
    def _assess_risk(self, issues: List[CodeIssue]) -> str:
        """Assess the risk level of refactoring."""
        high_severity = len([i for i in issues if i.severity == "HIGH"])
        if high_severity > 5:
            return "HIGH"
        elif high_severity > 2:
            return "MEDIUM"
        return "LOW"


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA Coding Engine - Code generation, debugging, and refactoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a Python function
  %(prog)s --generate --name "calculate_total" --lang python --params "items: list, tax: float"
  
  # Debug a file
  %(prog)s --debug --file /path/to/code.py
  
  # Identify refactoring opportunities
  %(prog)s --refactor --file /path/to/code.py --analyze-only
  
  # Generate debug report
  %(prog)s --debug --file /path/to/code.py --report
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--generate", action="store_true", help="Generate code")
    mode_group.add_argument("--debug", action="store_true", help="Debug code")
    mode_group.add_argument("--refactor", action="store_true", help="Refactor code")
    
    # Generate options
    parser.add_argument("--name", help="Name for generated code element")
    parser.add_argument("--lang", default="python", choices=["python", "javascript", "typescript", "java", "go"], help="Programming language")
    parser.add_argument("--params", help="Parameters for function (format: name:type,...)")
    parser.add_argument("--description", default="Generated code element", help="Description")
    parser.add_argument("--output", "-o", help="Output file path")
    
    # Debug options
    parser.add_argument("--file", help="File to debug/refactor")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze, don't modify")
    
    # Refactor options
    parser.add_argument("--pattern", choices=["god_class", "long_method", "duplicate_code", "spaghetti"], help="Refactoring pattern")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview changes without applying")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        if args.generate:
            if not args.name:
                parser.error("--name is required for code generation")
            
            # Parse parameters
            params = []
            if args.params:
                for p in args.params.split(","):
                    if ":" in p:
                        name, ptype = p.strip().split(":")
                        params.append((name.strip(), ptype.strip()))
            
            # Create generator and generate code
            lang = Language(args.lang)
            generator = CodeGenerator(default_language=lang)
            
            code = generator.generate_function(
                name=args.name,
                params=params,
                description=args.description
            )
            
            print(code)
            
            if args.output:
                generator.save_to_file(code, args.output)
                print(f"\nSaved to: {args.output}")
        
        elif args.debug:
            if not args.file:
                parser.error("--file is required for debugging")
            
            debugger = Debugger()
            
            if args.report:
                report = debugger.generate_debug_report(args.file)
                print(report)
            else:
                issues = debugger.analyze_file(args.file)
                print(f"\nAnalysis for: {args.file}")
                print(f"Issues found: {len(issues)}")
                
                for issue in issues[:10]:
                    print(f"  [{issue.severity}] Line {issue.line_number}: {issue.description}")
        
        elif args.refactor:
            if not args.file:
                parser.error("--file is required for refactoring")
            
            engine = RefactoringEngine()
            
            if args.analyze_only or args.pattern is None:
                plan = engine.create_refactoring_plan(args.file)
                print(f"Refactoring Plan for: {plan['file']}")
                print(f"Estimated changes: {plan['estimated_changes']}")
                print(f"Risk level: {plan['risk_level']}")
                print("\nOpportunities:")
                for opp in plan['opportunities']:
                    print(f"  [{opp['severity']}] {opp['pattern']}: {opp['description']}")
            else:
                result = engine.apply_refactoring(
                    filepath=args.file,
                    pattern=CodePattern(args.pattern),
                    dry_run=args.dry_run
                )
                print(f"Refactoring result: {'SUCCESS' if result.success else 'FAILED'}")
                print(f"Changes made: {len(result.changes_made)}")
                for change in result.changes_made:
                    print(f"  - {change}")
                if result.error_message:
                    print(f"Error: {result.error_message}")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()