# Prompts MCP

Role-based prompting with the awesome-chatgpt-prompts library.

## Overview

The Prompts MCP server integrates the [awesome-chatgpt-prompts](https://github.com/f/awesome-chatgpt-prompts) library, providing Claude with access to a curated collection of role-based prompts.

This enables Claude to adopt specialized personas on demand - code reviewer, architect, debugger, and more.

## Configuration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "prompts": {
      "command": "npx",
      "args": ["-y", "prompts.chat", "mcp"]
    }
  }
}
```

## Available Tools

### List Prompts

Browse available prompts:

```
mcp__prompts__list_prompts()
```

Returns all available prompt names and descriptions.

### Get Prompt

Retrieve a specific prompt:

```
mcp__prompts__get_prompt(name="Linux Terminal")
```

Returns the full prompt text for the specified role.

### Search Prompts

Find prompts by keyword:

```
mcp__prompts__search_prompts(query="developer")
```

Returns prompts matching the search query.

## Popular Prompts

### Development

| Prompt | Use Case |
|--------|----------|
| Linux Terminal | Shell command simulation |
| JavaScript Console | JS REPL simulation |
| SQL Terminal | SQL query execution |
| Git Commit Generator | Generate commit messages |
| Senior Developer | Code review perspective |
| Software Architect | System design |

### Review & Analysis

| Prompt | Use Case |
|--------|----------|
| Code Reviewer | Thorough code review |
| Security Researcher | Security analysis |
| Performance Optimizer | Performance review |
| UX/UI Developer | UI/UX feedback |

### Specialized Roles

| Prompt | Use Case |
|--------|----------|
| Tech Writer | Documentation |
| Regex Generator | Create regex patterns |
| Diagram Generator | Generate diagrams |
| Commit Message Generator | Git commits |

## Usage Patterns

### Adopting a Role

```
User: "Review this code as a senior developer"

Claude: [calls mcp__prompts__get_prompt("Senior Developer")]
        [applies the prompt's persona]
        "As a senior developer, here's my review..."
```

### Combining with Memory

```
User: "Debug this issue"

Claude: [searches memory for project context]
        [gets "Debugger" prompt]
        [applies both context and persona]
```

### Switching Roles

```
User: "Now review the security"

Claude: [gets "Security Researcher" prompt]
        [switches to security perspective]
        "From a security standpoint..."
```

## Examples

### Code Review

```
User: "Act as a code reviewer for this PR"

Claude: [mcp__prompts__get_prompt("Code Reviewer")]
Response: "I'll review this code focusing on:
- Code quality and readability
- Potential bugs and edge cases
- Performance implications
- Security concerns
..."
```

### Architecture Discussion

```
User: "Help me design the database schema"

Claude: [mcp__prompts__get_prompt("Software Architect")]
Response: "Let's approach this systematically:
1. Identify entities and relationships
2. Consider normalization
3. Plan for scalability
..."
```

### Documentation

```
User: "Write documentation for this API"

Claude: [mcp__prompts__get_prompt("Tech Writer")]
Response: "I'll create clear, user-focused documentation:
## Overview
## Quick Start
## API Reference
..."
```

## Custom Prompts

You can combine prompts with your own context:

```
User: "Use the debugger prompt but focus on React"

Claude: [gets "Debugger" prompt]
        [adds React-specific context]
        "I'll debug this React component..."
```

## Best Practices

### When to Use Prompts

- **Specialized reviews**: Security, performance, accessibility
- **Role-playing**: Act as a specific type of expert
- **Structured tasks**: Following established methodologies
- **Teaching**: Explaining from a specific perspective

### When Not to Use

- Simple questions (don't need a persona)
- Already have clear context
- Memory provides sufficient guidance

### Combining with Memory

1. Search memory for project context
2. Get relevant prompt for the task
3. Apply both to the response

This gives Claude both knowledge (from memory) and perspective (from prompt).

## Troubleshooting

### Prompts MCP Not Available

1. Check configuration:
```bash
cat ~/.claude.json | jq '.mcpServers.prompts'
```

2. Verify npx works:
```bash
npx -y prompts.chat --help
```

3. Check MCP debug:
```bash
claude --mcp-debug
```

### Prompt Not Found

Some prompts may have different names. Try:
```
mcp__prompts__search_prompts(query="partial name")
```

## Related Pages

- [[Configuration]] - MCP setup
- [[Memory-MCP]] - Memory integration
- [[Memory-MCP-Behavioral-Guidelines]] - Combining memory and prompts
