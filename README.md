# Discord Verification Bot

A Discord bot with custom captcha verification system.

## Features
- Custom captcha challenges (math, word puzzles, ASCII art, emoji sequences, colors, patterns)
- Automatic role management
- Admin commands for user management

## Setup
1. Create `config.json` with your bot token and settings
2. Enable privileged intents in Discord Developer Portal
3. Run `python verification_bot.py`

## Commands
- `/setup_verification` - Configure verification channel
- `/verify_user` - Manually verify a user
- `/unverify_user` - Remove verification from a user
- `/verification_stats` - View verification statistics