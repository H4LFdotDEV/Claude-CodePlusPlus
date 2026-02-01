# Security Policy

## Reporting Security Issues

If you discover a security vulnerability in Claude Code++, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email security concerns to the maintainers directly
3. Include details about the vulnerability and steps to reproduce

## Security Contact

Email: jeremiahk@halfservers.com

## Security Measures

Claude Code++ implements several security measures:

### Input Validation
- All user inputs are validated before processing
- SQL injection prevention with parameterized queries and LIKE pattern escaping
- Path traversal prevention for configuration file loading

### Memory Security
- Redis connections use authentication when configured
- Sensitive data is not logged
- Session data has configurable TTL for automatic expiration

### Code Security
- No hardcoded secrets or credentials
- Environment variables for all sensitive configuration
- Thread-safe operations with proper locking

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Security Updates

Security updates will be released as patch versions. Users are encouraged to keep their installations up to date.
