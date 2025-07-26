# Modern Cursor Rules System

This project now uses the **modern Cursor rules format** instead of the deprecated `.cursorrules` file.

## 📂 Directory Structure

```
.cursor/
├── rules/
│   └── core-rules/
│       └── properties-protection-always.mdc
└── README.md (this file)
```

## 🔧 Rule Types

Each `.mdc` file has YAML frontmatter with three fields:

### Frontmatter Fields:
- **`description`**: Comprehensive description for when to apply the rule
- **`globs`**: Comma-separated glob patterns for file matching
- **`alwaysApply`**: Boolean for global application

### Rule Categories:

| Type | Description | Globs | AlwaysApply | Filename Pattern |
|------|-------------|-------|-------------|------------------|
| **Always** | Applied to every chat/command | blank | `true` | `*-always.mdc` |
| **Auto** | Applied to matching files | patterns | `false` | `*-auto.mdc` |
| **Agent** | AI chooses when to apply | blank | `false` | `*-agent.mdc` |
| **Manual** | User must reference | blank | `false` | `*-manual.mdc` |

## 📝 Creating New Rules

### Always Rule (Global)
```yaml
---
description: 
globs: 
alwaysApply: true
---
```

### Auto Rule (File-based)
```yaml
---
description: 
globs: src/**/*.ts, test/**/*.ts
alwaysApply: false
---
```

### Agent Rule (AI-selected)
```yaml
---
description: Apply when working with API endpoints and security configurations
globs: 
alwaysApply: false
---
```

### Manual Rule (User-referenced)
```yaml
---
description: 
globs: 
alwaysApply: false
---
```

## 🛡️ Current Rules

### Properties Protection (`properties-protection-always.mdc`)
- **Type**: Always (Global)
- **Purpose**: Protects `.properties` files from unauthorized changes
- **Scope**: All `config/*.properties` files
- **Requires**: Explicit user permission for any modifications

## 🚀 Migration from `.cursorrules`

The old `.cursorrules` format is deprecated. Benefits of the new system:

✅ **File-specific rules** with glob patterns  
✅ **Better organization** with subdirectories  
✅ **More flexible triggering** (always, auto, agent, manual)  
✅ **Version control friendly** with individual files  
✅ **Path-specific configurations** for different project areas  

## 📚 References

- [Official Cursor Rules Documentation](https://cursor-docs.apidog.io/rules-for-ai-896238m0)
- [Project Rules vs Global Rules](https://cursor.com/docs/rules-for-ai)

## 🔄 Adding New Rules

1. Create new `.mdc` file in appropriate subdirectory
2. Add proper YAML frontmatter
3. Write clear, actionable markdown content
4. Use descriptive filenames with type suffix

Example directories:
- `core-rules/` - Cursor behavior and rule generation
- `security-rules/` - Security and access control
- `code-style/` - Language-specific formatting
- `testing-rules/` - Test requirements and standards 