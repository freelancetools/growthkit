# CLI Print Statement Styling Tutorial

Based on our conversation about creating clean, coherent CLI output, here's a comprehensive guide for formatting print statements with ANSI colors.

## Core Principles

### 1. **Selective Keyword Highlighting**
- **Don't color entire lines** - only highlight key terms and values
- **Preserve readability** - most text should remain normal/white
- **Focus attention** - colors should guide the eye to important information

### 2. **Coherent Color Scheme**
Each type of information gets a consistent, logical color:

```python
# Status Actions
Processing → magenta
Completed → green  
Skipping → yellow (warning)

# Analysis Types (each gets unique color)
shill → yellow
rating → cyan
tags → lilac/blue

# Technical Operations
Commands/CLI execution → grey
Model names → cyan
File paths → cyan
Timing/durations → yellow
Technical parameters (CRF, bitrate) → lilac

# AI/API Operations
Input tokens → lilac
Output tokens → rose
Prompts → grey

# Results & Success
All results/counts/grades → green
Progress totals (finish line) → green
Successful operations → green

# Infrastructure  
Separators → blue
Errors → red
Retries/warnings → yellow
Command output → cyan (success) / red (errors)
```

### 3. **Progress Indicator Format**
```python
# Clean format: current/total
print(f"{ansi.magenta}Processing {file_index}{ansi.reset}/{ansi.green}{total_files}{ansi.reset}: {filename}...")

# NOT: "Processing 3 out of 41" (too verbose)
# YES: "Processing 3/41" (clean and scannable)
```

## Styling Patterns

### **Main Processing Flow**
```python
# Start
print(f"Starting talk transcript evaluation...")  # No color needed

# Progress with meaningful colors
print(f"\n{ansi.magenta}Processing {file_index}{ansi.reset}/{ansi.green}{total_files}{ansi.reset}: {filename}...")

# Completion with success colors
print(f"  {ansi.green}Completed{ansi.reset} {ansi.green}{file_index}{ansi.reset}/{ansi.green}{total_files}{ansi.reset}: {filename}")
```

### **Analysis Steps Pattern**
```python
# Action messages - highlight only the analysis type
print(f"  Getting {ansi.yellow}shill{ansi.reset} analysis for {filename[:20]}...")
print(f"  Getting {ansi.cyan}rating{ansi.reset} for {filename[:20]}...")  
print(f"  Extracting {ansi.lilac}tags{ansi.reset} for {filename[:20]}...")

# Result messages - highlight analysis type and results
print(f"  {ansi.yellow}Shill{ansi.reset} analysis for {filename[:20]}: {ansi.green}{count}{ansi.reset} shills - {details}")
print(f"  {ansi.cyan}Rating{ansi.reset} for {filename[:20]}: {ansi.green}{grade}{ansi.reset}")
print(f"  {ansi.lilac}Tags{ansi.reset} for {filename[:20]}: {tags}")
```

### **Error/Warning Pattern**
```python
# Highlight error type and actual error
print(f"    {ansi.red}Non-retryable{ansi.reset} Gemini API error: {ansi.red}{e}{ansi.reset}")
print(f"    Could not {ansi.yellow}parse tags{ansi.reset} from response: '{response_text}'")
```

## Key Rules

### ✅ **DO:**
- Truncate long filenames: `{filename[:20]}`
- Use consistent colors for same information types
- Keep progress indicators clean: `3/41` not `3 out of 41`
- Color only keywords and results, not entire sentences
- Use green for success/completion/totals (finish line concept)
- Remove all `ansi.bold` - it creates visual clutter

### ❌ **DON'T:**
- Color entire lines with `print(f"{ansi.color}{entire_message}{ansi.reset}")`
- Mix color schemes - stick to the established pattern
- Use bold text - it makes output heavy and cluttered
- Show repetitive progress indicators on sub-steps
- Use inconsistent formatting for similar information

## Example Before/After

### Before (cluttered):
```python
print(f"{ansi.cyan}Getting shill analysis for {filename} ({file_index}/{total_files})...{ansi.reset}")
print(f"{ansi.green}Shill analysis for {filename}: 2 shills - Company X, Product Y{ansi.reset}")
```

### After (clean):
```python
print(f"  Getting {ansi.yellow}shill{ansi.reset} analysis for {filename[:20]}...")
print(f"  {ansi.yellow}Shill{ansi.reset} analysis for {filename[:20]}: {ansi.green}2{ansi.reset} shills - Company X, Product Y")
```

## Color Psychology & Usage Patterns

- **Green**: Success, completion, "finish line" - use for totals and results
- **Yellow**: Warnings, timing/duration values, file sizes, attention-grabbing info
- **Cyan**: Information, file paths, model names, resolution specs (neutral but visible)  
- **Magenta**: Processing status, voice names (distinct for main actions)
- **Lilac**: Technical parameters (CRF, bitrate), input token counts
- **Rose**: Output token counts (distinguishes from input)
- **Grey**: Command execution, prompts, file inputs (subdued)
- **Red**: Errors, failures (universal warning color)

### **AI/API Specific Patterns**
```python
# Model operations
print(f"Model name: {ansi.cyan}{model_choice}{ansi.reset}")

# Token counting (input/output distinction)
print(f"{ansi.lilac}{token_count:,}{ansi.reset} {prompt_type} tokens in")
print(f"{ansi.rose}{response_tokens:,}{ansi.reset} {prompt_type} tokens out")

# Command execution
print(f"{ansi.grey}{' '.join(command)}{ansi.reset}")

# Command output
print(f"{ansi.cyan}> {ansi.reset}{output}")  # Success output
print(f"{ansi.red}> {ansi.reset}{error}")    # Error output
```

### **Technical Operations Patterns**
```python
# File operations
print(f"Output file: {ansi.cyan}{filepath}{ansi.reset}")
print(f"Video output path: {ansi.cyan}{video_path}{ansi.reset}")

# Timing/performance
print(f"Operation completed in {ansi.yellow}{duration:.2f}{ansi.reset} seconds")
print(f"Video size: {ansi.yellow}{size_mb:.2f}{ansi.reset} MB")

# Technical parameters
print(f"Generating video with CRF {ansi.lilac}{crf_value}{ansi.reset}")
print(f"Target bitrate: {ansi.yellow}{bitrate/1000:.0f}{ansi.reset} kbps")
```

This creates a **visual hierarchy** where users can quickly scan for:
- Progress (magenta processing, green completion)
- Analysis types (yellow/cyan/blue keywords)
- Results (green values)
- Technical details (cyan paths, yellow timing, lilac parameters)
- AI operations (lilac input, rose output, grey commands)
- Problems (red errors, yellow warnings)

The key is **consistency** and **restraint** - use colors to enhance readability, not overwhelm it.