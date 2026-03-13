# Contributing to Adhara Engine

Thank you for your interest in contributing to Adhara Engine!

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a feature branch from `main`
4. Make your changes
5. Run `make init` to set up the development environment
6. Test your changes thoroughly
7. Submit a pull request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/adhara-engine.git
cd adhara-engine

# Set up the development environment
make init

# Start the services
make up
```

## Pull Request Process

1. Update documentation if your change affects public APIs or configuration
2. Add tests for new functionality
3. Ensure all existing tests pass
4. Keep PRs focused — one feature or fix per PR
5. Write a clear PR description explaining what and why

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add webhook retry logic
fix: resolve race condition in task scheduler
docs: update API reference for /v1/sites
```

## Code Style

- Follow existing patterns in the codebase
- Use meaningful variable and function names
- Add comments for non-obvious logic only

## Contributor License Agreement (CLA)

By submitting a pull request, you agree that your contributions will be
licensed under the same license as the project (Business Source License 1.1,
converting to Apache 2.0 on the Change Date specified in the LICENSE file).

You certify that:
- The contribution is your original work, OR
- You have the right to submit it under the project license
- You grant EIM Global Solutions, LLC a perpetual, irrevocable license to use
  your contribution

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests
- Use the provided issue templates
- Include reproduction steps for bugs
- Check existing issues before creating new ones

## Questions?

Open a Discussion on GitHub or reach out to the maintainers.
