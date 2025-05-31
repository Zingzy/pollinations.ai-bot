<p align="center">
  <image src='https://raw.githubusercontent.com/Zingzy/pollinations.ai-bot/main/.github/previews/banner.png' width="800"/>
</p>

<h3 align="center">Pollinations.ai Discord Bot</h3>
<p align="center">Generate AI Images for free under 10 seconds using pollinations.ai 🤖🎨
</p>

<p align="center">
    <a href="#-features"><kbd>🔥 Features</kbd></a>
    <a href="#-whats-next"><kbd>💡 What's Next</kbd></a>
    <a href="#-getting-started"><kbd>🚀 Getting Started</kbd></a>
    <a href="https://discord.com/oauth2/authorize?client_id=1123551005993357342"><kbd>➕ Add to your server</kbd></a>
</p>


<p align="center">
<img src="https://img.shields.io/github/last-commit/zingzy/pollinations.ai-bot?logo=github" alt="GitHub last commit">
<img src="https://img.shields.io/github/commit-activity/m/zingzy/pollinations.ai-bot?logo=github" alt="GitHub commit activity">
<img src="https://img.shields.io/github/issues/zingzy/pollinations.ai-bot?logo=github" alt="GitHub issues">
<a href="https://discord.gg/k9F7SyTgqn"><img src="https://img.shields.io/discord/885844321461485618?logo=discord" alt="Discord"></a>
</p>


## ⚡ Introduction

🌸 **Pollinations.ai bot** is a discord bot which **generates AI images** using https://pollinations.ai. It is written in `Python` using the `discord.py` library and is currently used in **over 500 discord servers**.

---

### 🔥 Features

- Generate **AI images** using the `/pollinate` command
  - Users can also speicify whether they want to **AI enhance their prompt** or not.
  - Users can also specify the **width** and **height** of the image.
- Generate **multiple variations** of a prompt using the `/multi-pollinate` command
  - The bot will generate **4 different** variations of the prompt.

- Generate **random AI images** using the `/random` command

---

### 🚀 Getting Started

1. **Inviting the Bot**: Invite Pollinations.ai bot to your server using the following link: [Invite Pollinations.ai bot](https://discord.com/oauth2/authorize?client_id=1123551005993357342).

2. **Commands**: Use the various commands mentioned above to start generating AI Images.

---


### ⚙️ How to setup

#### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Discord Developer Account
- [Pollinations.ai token](https://auth.pollinations.ai)

#### Environment Setup

**1. Clone the repository**

```bash
git clone https://github.com/zingzy/pollinations.ai-bot.git
cd pollinations.ai-bot
```

**2. Install uv package manager**

```bash
pip install uv
```

**3. Install dependencies**

```bash
uv sync
```

**4. Setup environment files**

Rename the `.env.example` file to `.env`:

```bash
mv .env.example .env
```

Copy the configuration template:

```bash
cp config.template.toml config.toml
```

Now open the `.env` file and add your discord bot `TOKEN`. Also fill in the required values in `config.toml` file including your Pollinations.ai token.

#### Start the bot

```bash
uv run main.py
```

---

### 📝 Feedback / Issues

To give feedback, ask a question or make a feature request, you can either use the [Github Discussions](https://github.com/Zingzy/pollinations.ai-bot/discussions) or [JOIN OUR SUPPORT SERVER](https://discord.gg/k9F7SyTgqn) 🪬

Bugs are logged using the github issue system. To report a bug, simply [open a new issue](https://github.com/Zingzy/pollinations.ai-bot/issues/new) 🪲

---

### 🤝 Contributing

Contributions, issues and feature requests are welcome! Feel free to check [issues page](https://github.com/Zingzy/pollinations.ai-bot/issues).

Please read our [Contributing Guidelines](.github/contributing.md) for detailed information about:
- Development environment setup
- Code style guidelines
- Pull request process
- Testing procedures

---

Any Other suggestions would be appreciated ...

---

### Contributors

<a href="https://github.com/zingzy/pollinations.ai-bot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=zingzy/pollinations.ai-bot" />
</a>
