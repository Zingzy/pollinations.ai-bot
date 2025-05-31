# Contributing to Pollinations.ai Discord Bot

Thank you for your interest in contributing to the Pollinations.ai Discord Bot! This document provides guidelines and best practices for contributing to this project.

## 📋 Table of Contents

- [Getting Started](#-getting-started)
- [Development Environment](#-development-environment)
- [Project Structure](#-project-structure)
- [Code Style Guidelines](#-code-style-guidelines)
- [Configuration Management](#-configuration-management)
- [Testing](#-testing)
- [Submitting Changes](#-submitting-changes)
- [Issue Reporting](#-issue-reporting)
- [Code Review Process](#-code-review-process)

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Discord Developer Account
- [Pollinations.ai token](https://auth.pollinatiins.ai)
- Git

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/zingzy/pollinations.ai-bot.git
   cd pollinations.ai-bot
   ```

## 🛠️ Development Environment

### Package Management

This project uses **uv** for package management. Do not use pip, pipenv, or poetry.

Firstly install uv: `pip install uv`

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Running the bot
uv run main.py
```

### Code Formatting and Linting

We use **Ruff** for both linting and formatting. Run it via `uvx`:

```bash
# Format code
uvx ruff format

# Lint code
uvx ruff check

# Fix auto-fixable lint issues
uvx ruff check --fix
```

**Important**: Always run formatting and linting before committing your changes.

### Environment Setup

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Copy the configuration template:
   ```bash
   cp config.template.toml config.toml
   ```

3. Fill in the required values in both `.env` and `config.toml` files.

## 📁 Project Structure

```
pollinations.ai-bot/
├── .github/                 # GitHub workflows and templates
├── cogs/                    # Discord bot command modules
│   ├── imagine_cog.py      # Main image generation commands
│   ├── multi_pollinate_cog.py  # Multi-model generation
│   └── random_cog.py       # Random image generation
├── utils/                   # Utility modules
│   ├── embed_utils.py      # Discord embed utilities
│   ├── image_gen_utils.py  # Image generation utilities
│   ├── logger.py           # Logging utilities
│   ├── error_handler.py    # Error handling utilities
│   └── models.py           # Model management utilities
├── config.py               # Configuration management
├── exceptions.py           # Custom exception classes
├── main.py                 # Bot entry point
├── pyproject.toml          # Project metadata and dependencies
└── uv.lock                 # Dependency lock file
```

### Key Components

- **Cogs**: Discord.py command modules that handle specific functionality
- **Utils**: Reusable utility functions and classes
- **Configuration**: TOML-based configuration with environment variable support
- **Logging**: Structured logging with different levels and contexts

## 🎨 Code Style Guidelines

### General Python Style

- Follow PEP 8 standards (enforced by Ruff)
- Use type hints for all function parameters and return values
- Maximum line length: 88 characters (Black/Ruff default)
- Use descriptive variable and function names

### Naming Conventions

```python
# Variables and functions: snake_case
user_id: int = 12345
async def generate_image() -> None:

# Classes: PascalCase
class ImageGenerator:

# Constants: UPPER_SNAKE_CASE
MAX_PROMPT_LENGTH: int = 2000

# Private methods: _leading_underscore
def _internal_method(self) -> None:
```

### Type Annotations

Always use type hints:

```python
from typing import Optional, Dict, List, Any
import discord

async def process_command(
    interaction: discord.Interaction,
    prompt: str,
    width: int = 1000,
    height: int = 1000,
    private: bool = False
) -> Optional[discord.File]:
    """Process image generation command."""
    pass
```

### Discord.py Patterns

#### Embed Creation
Use the `SafeEmbed` class for all embeds to prevent character limit issues:

```python
from utils.embed_utils import SafeEmbed

embed = SafeEmbed(
    title="Image Generated",
    description="Your image has been generated successfully!",
    color=int(config.ui.colors.success, 16)
)
embed.add_field(name="Prompt", value=f"```{prompt}```", inline=False)
```

#### Error Handling
Use the centralized error handling pattern:

```python
from utils.error_handler import send_error_embed
from exceptions import PromptTooLongError

try:
    # Your code here
    pass
except PromptTooLongError as e:
    await send_error_embed(
        interaction,
        "Prompt Too Long",
        f"```\n{str(e)}\n```"
    )
```

#### Command Structure
Follow the established cog pattern:

```python
from discord.ext import commands
from discord import app_commands
import discord

class YourCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.command_config = config.commands["your_command"]

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        # Initialization code here

    @app_commands.command(name="your-command", description="Command description")
    @app_commands.checks.cooldown(
        config.commands["your_command"].cooldown.rate,
        config.commands["your_command"].cooldown.seconds,
    )
    @app_commands.guild_only()
    async def your_command(
        self,
        interaction: discord.Interaction,
        # Parameters here
    ) -> None:
        # Command implementation
        pass

    @your_command.error
    async def your_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        # Error handling
        pass

async def setup(bot) -> None:
    await bot.add_cog(YourCog(bot))
```

### Logging

Use the structured logging system:

```python
from utils.logger import discord_logger

# Log bot events
discord_logger.log_bot_event(
    action="command_executed",
    status="success",
    details={"command": "pollinate", "user_id": user.id}
)

# Log errors
discord_logger.log_error(
    error_type="api_error",
    error_message=str(error),
    traceback=traceback.format_exc(),
    context={"user_id": user.id, "command": "pollinate"}
)

# Log commands
discord_logger.log_command(
    command_name="pollinate",
    execution_time=123.45,
    status="success"
)
```

### Async/Await Patterns

- Always use `async`/`await` for I/O operations
- Use `asyncio.gather()` for concurrent operations
- Handle timeouts appropriately:

```python
import asyncio

try:
    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=config.commands["command_name"].timeout_seconds
    )
except asyncio.TimeoutError:
    # Handle timeout
    pass
```

## ⚙️ Configuration Management

### Configuration Structure

The project uses TOML configuration with Pydantic validation:

- `config.template.toml`: Template with empty/default values
- `config.toml`: Actual configuration (gitignored)
- `config.py`: Pydantic models for validation

### Adding New Configuration

1. Add the field to the appropriate Pydantic model in `config.py`:
   ```python
   class CommandConfig(BaseModel):
       new_field: int = 100  # with default value
   ```

2. Add it to `config.template.toml`:
   ```toml
   [commands.your_command]
   new_field = 100
   ```

3. Update your actual `config.toml` file

### Environment Variables

Use environment variables for sensitive data:

```toml
# In config.toml
api_key = "${API_KEY}"
```

```bash
# In .env
API_KEY=your_secret_key_here
```

## 🧪 Testing

### Manual Testing

1. Test your changes locally with a test Discord server
2. Verify all command interactions work as expected
3. Test error scenarios and edge cases
4. Ensure proper logging output


## 📝 Submitting Changes

### Commit Guidelines

Use conventional commit messages:

```
feat: add new image style parameter
fix: resolve timeout issue in multi-pollinate command
docs: update configuration documentation
refactor: improve error handling in image generation
style: format code with ruff
test: add tests for embed utilities
```

### Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the guidelines above

3. **Test thoroughly** in your development environment

4. **Format and lint your code**:
   ```bash
   uvx ruff format
   uvx ruff check --fix
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** with:
   - Clear title and description
   - Screenshots/examples if applicable
   - Reference any related issues

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tested locally
- [ ] All commands work as expected
- [ ] Error handling tested
- [ ] Code formatted with ruff

## Screenshots (if applicable)
Add screenshots here

## Related Issues
Fixes #(issue number)
```

## 👀 Code Review Process

### For Contributors

- Be responsive to feedback
- Make requested changes promptly
- Ask questions if feedback is unclear
- Test changes after addressing feedback

### Review Criteria

Code will be reviewed for:

- **Functionality**: Does it work as intended?
- **Code quality**: Follows style guidelines and best practices
- **Performance**: Efficient and doesn't introduce bottlenecks
- **Security**: No security vulnerabilities
- **Documentation**: Code is well-documented
- **Testing**: Adequate testing coverage

## 🤝 Community Guidelines

- Be respectful and constructive in discussions
- Help other contributors when possible
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md)
- Join our [Discord server](https://discord.gg/k9F7SyTgqn) for discussions

## 📚 Additional Resources

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Pollinations.ai API](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## ❓ Questions?

If you have questions about contributing:

1. Check existing issues and discussions
2. Join our [Discord server](https://discord.gg/k9F7SyTgqn)
3. Create a new issue with the "question" label

Thank you for contributing to the Pollinations.ai Discord Bot! 🎨🤖
