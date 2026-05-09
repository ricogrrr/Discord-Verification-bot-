import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import logging
import random
import string
from datetime import datetime, timedelta
import math
from database import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Database
db = Database()

# Load configuration (for bot token and global defaults only)
try:
    with open('config.json', 'r') as f:
        global_config = json.load(f)
except FileNotFoundError:
    logger.error("config.json not found. Please create it with your bot settings.")
    exit(1)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

class VerificationBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=self.get_custom_prefix,
            intents=intents
        )

    async def get_custom_prefix(self, bot, message):
        if not message.guild:
            return global_config.get('prefix', '!')
        settings = db.get_settings(message.guild.id)
        return settings['prefix'] if settings else global_config.get('prefix', '!')

    async def setup_hook(self):
        # We don't sync here to avoid rate limits on every restart
        logger.info("Bot setup hook completed.")

bot = VerificationBot()

# Verification data storage
# Key: (guild_id, user_id)
pending_verifications = {}

async def get_guild_settings(guild_id):
    settings = db.get_settings(guild_id)
    if not settings:
        db.update_settings(guild_id) # Initialize with defaults
        settings = db.get_settings(guild_id)
    return settings

async def complete_verification_logic(guild, user, method_name, attempts=1):
    """Standalone helper to complete verification without MockInteraction"""
    settings = await get_guild_settings(guild.id)

    try:
        # Check permissions
        if not guild.me.guild_permissions.manage_roles:
            return "❌ I don't have the 'Manage Roles' permission."

        # Role assignment
        verified_role = discord.utils.get(guild.roles, name=settings['verified_role_name'])
        if not verified_role:
            verified_role = await guild.create_role(
                name=settings['verified_role_name'],
                color=discord.Color.green(),
                reason="Verification bot setup"
            )

        # Check role hierarchy
        if guild.me.top_role.position <= verified_role.position:
            return f"❌ My role is not high enough to assign the '{verified_role.name}' role. Please move my role higher."

        await user.add_roles(verified_role, reason=f"User completed {method_name} verification")

        # Remove unverified role
        unverified_role = discord.utils.get(guild.roles, name=settings['unverified_role_name'])
        if unverified_role and unverified_role in user.roles:
            await user.remove_roles(unverified_role, reason="User completed verification")

        # Log to channel
        if settings.get('log_channel_id'):
            log_channel = bot.get_channel(settings['log_channel_id'])
            if log_channel:
                log_embed = discord.Embed(
                    title="New Verification",
                    description=f"{user.mention} (ID: {user.id}) has been verified",
                    color=0x00ff00,
                    timestamp=datetime.now()
                )
                log_embed.set_thumbnail(url=user.display_avatar.url)
                log_embed.add_field(name="Method", value=method_name, inline=True)
                log_embed.add_field(name="Attempts", value=str(attempts), inline=True)
                await log_channel.send(embed=log_embed)

        logger.info(f"User {user} ({user.id}) verified in {guild.name}")
        return True

    except discord.Forbidden:
        return "❌ I don't have permission to assign roles."
    except Exception as e:
        logger.error(f"Error in complete_verification_logic: {e}")
        return "❌ An unexpected error occurred."

class CaptchaModal(discord.ui.Modal, title='Verification Captcha'):
    answer_input = discord.ui.TextInput(
        label='Enter the answer',
        placeholder='Type your answer here...',
        required=True,
        min_length=1,
        max_length=50,
    )

    def __init__(self, correct_answer, guild_id, user_id, captcha_type):
        super().__init__()
        self.correct_answer = str(correct_answer).upper().strip()
        self.guild_id = guild_id
        self.user_id = user_id
        self.captcha_type = captcha_type

    async def on_submit(self, interaction: discord.Interaction):
        state_key = (self.guild_id, self.user_id)
        if state_key not in pending_verifications:
            await interaction.response.send_message("Verification expired. Please click the button again.", ephemeral=True)
            return

        data = pending_verifications[state_key]
        user_answer = self.answer_input.value.upper().strip()

        if user_answer == self.correct_answer:
            del pending_verifications[state_key]
            result = await complete_verification_logic(interaction.guild, interaction.user, self.captcha_type, data['attempts'] + 1)

            if result is True:
                success_embed = discord.Embed(
                    title="✅ Verification Successful!",
                    description=f"Welcome to {interaction.guild.name}! You now have full access.",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
            else:
                await interaction.response.send_message(result, ephemeral=True)
        else:
            data['attempts'] += 1
            settings = await get_guild_settings(self.guild_id)
            max_attempts = settings.get('max_captcha_attempts', 3)

            if data['attempts'] >= max_attempts:
                del pending_verifications[state_key]
                await interaction.response.send_message("❌ Maximum attempts exceeded. Please try again from the start.", ephemeral=True)
            else:
                remaining = max_attempts - data['attempts']
                await interaction.response.send_message(f"❌ Incorrect answer. You have {remaining} attempts remaining. Click the verify button to try again.", ephemeral=True)

class CustomCaptcha:
    """Custom captcha generator with multiple challenge types"""

    @staticmethod
    def generate_math_captcha():
        operations = ['+', '-', '*']
        operation = random.choice(operations)
        if operation == '+':
            a, b = random.randint(10, 50), random.randint(10, 50)
            answer = a + b
            question = f"{a} + {b}"
        elif operation == '-':
            a, b = random.randint(20, 80), random.randint(1, 19)
            answer = a - b
            question = f"{a} - {b}"
        else:
            a, b = random.randint(2, 12), random.randint(2, 12)
            answer = a * b
            question = f"{a} × {b}"
        return question, str(answer)

    @staticmethod
    def generate_word_puzzle():
        words = ["DISCORD", "VERIFY", "SECURE", "MEMBER", "SERVER", "CHANNEL", "WELCOME", "SAFETY"]
        word = random.choice(words)
        scrambled = ''.join(random.sample(word, len(word)))
        while scrambled == word: scrambled = ''.join(random.sample(word, len(word)))
        return f"Unscramble this word: **{scrambled}**", word

    @staticmethod
    def generate_ascii_captcha():
        ascii_numbers = {
            '0': [" ███ ","█   █","█   █","█   █"," ███ "],
            '1': ["  █  "," ██  ","  █  ","  █  "," ███ "],
            '2': [" ███ ","    █"," ███ ","█    ","█████"],
            '3': [" ███ ","    █"," ███ ","    █"," ███ "],
            '4': ["█   █","█   █","█████","    █","    █"],
            '5': ["█████","█    ","████ ","    █","████ "],
            '6': [" ███ ","█    ","████ ","█   █"," ███ "],
            '7': ["█████","    █","   █ ","  █  "," █   "],
            '8': [" ███ ","█   █"," ███ ","█   █"," ███ "],
            '9': [" ███ ","█   █"," ████","    █"," ███ "]
        }
        number = str(random.randint(10, 99))
        ascii_art = []
        for row in range(5):
            line = ""
            for digit in number:
                line += ascii_numbers[digit][row] + "  "
            ascii_art.append(line)
        return f"What 2-digit number is shown?\n```\n" + "\n".join(ascii_art) + "\n```", number

    @staticmethod
    def generate_emoji_sequence():
        emojis = ['🔥', '⭐', '🎯', '🚀', '💎', '🌟', '🎨', '🎭']
        sequence = random.choices(emojis, k=4)
        missing_index = random.randint(0, 3)
        missing_emoji = sequence[missing_index]
        display_sequence = sequence.copy()
        display_sequence[missing_index] = '❓'
        return f"Complete the sequence: {' '.join(display_sequence)}", missing_emoji

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @discord.ui.button(label='✅ Verify', style=discord.ButtonStyle.green, custom_id='verify_btn')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = await get_guild_settings(interaction.guild.id)

        # Check if already verified
        verified_role = discord.utils.get(interaction.guild.roles, name=settings['verified_role_name'])
        if verified_role and verified_role in interaction.user.roles:
            return await interaction.response.send_message("You are already verified!", ephemeral=True)

        v_type = settings['verification_type']
        state_key = (interaction.guild.id, interaction.user.id)

        if state_key not in pending_verifications:
            pending_verifications[state_key] = {'attempts': 0, 'timestamp': datetime.now()}

        if v_type == 'custom_captcha':
            generators = [CustomCaptcha.generate_math_captcha, CustomCaptcha.generate_word_puzzle,
                          CustomCaptcha.generate_ascii_captcha, CustomCaptcha.generate_emoji_sequence]
            question, answer = random.choice(generators)()
            pending_verifications[state_key].update({'answer': answer, 'type': 'custom_captcha'})

            modal = CaptchaModal(answer, interaction.guild.id, interaction.user.id, "Custom Captcha")
            embed = discord.Embed(title="🧩 Verification Challenge", description=question, color=0x00ff00)
            await interaction.response.send_modal(modal)

        elif v_type == 'captcha':
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            pending_verifications[state_key].update({'answer': code, 'type': 'simple_captcha'})
            modal = CaptchaModal(code, interaction.guild.id, interaction.user.id, "Simple Captcha")
            await interaction.response.send_modal(modal)

        elif v_type == 'reaction':
            reactions = ['👍', '✅', '🔥', '💎']
            chosen = random.choice(reactions)
            pending_verifications[state_key].update({'reaction': chosen, 'type': 'reaction'})

            # Use non-ephemeral message for reactions, but tell user where to look
            embed = discord.Embed(title="🎯 Reaction Verification", description=f"Please react with {chosen} to the message I just sent in this channel.", color=0x00ff00)
            await interaction.response.send_message(embed=embed, ephemeral=True)

            msg = await interaction.channel.send(f"{interaction.user.mention}, react with {chosen} to verify!")
            pending_verifications[state_key]['msg_id'] = msg.id
            await msg.add_reaction(chosen)

            # Clean up after timeout
            await asyncio.sleep(300)
            if state_key in pending_verifications and pending_verifications[state_key].get('msg_id') == msg.id:
                del pending_verifications[state_key]
                try: await msg.delete()
                except: pass
        else:
            result = await complete_verification_logic(interaction.guild, interaction.user, "Instant")
            await interaction.response.send_message(result if isinstance(result, str) else "✅ Verified!", ephemeral=True)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    # Add persistent view
    bot.add_view(VerificationView())

@bot.event
async def on_member_join(member):
    settings = await get_guild_settings(member.guild.id)
    if not settings['auto_role_on_join']: return

    unverified_role = discord.utils.get(member.guild.roles, name=settings['unverified_role_name'])
    if not unverified_role:
        try:
            unverified_role = await member.guild.create_role(name=settings['unverified_role_name'], color=discord.Color.red())
        except: pass

    if unverified_role:
        try: await member.add_roles(unverified_role)
        except: pass

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or not reaction.message.guild: return

    state_key = (reaction.message.guild.id, user.id)
    if state_key in pending_verifications:
        data = pending_verifications[state_key]
        if data.get('type') == 'reaction' and data.get('msg_id') == reaction.message.id:
            if str(reaction.emoji) == data['reaction']:
                del pending_verifications[state_key]
                await complete_verification_logic(reaction.message.guild, user, "Reaction")
                try: await reaction.message.delete()
                except: pass

@bot.tree.command(name="setup_verification", description="Setup verification system")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verification(interaction: discord.Interaction):
    embed = discord.Embed(title="🔐 Server Verification", description="Click the button below to verify.", color=0x0099ff)
    await interaction.response.send_message(embed=embed, view=VerificationView())
    db.update_settings(interaction.guild.id, verification_channel_id=interaction.channel.id)

@bot.tree.command(name="config_bot", description="Configure bot settings")
@app_commands.checks.has_permissions(administrator=True)
async def config_bot(interaction: discord.Interaction, verified_role: str = None, type: str = None):
    kwargs = {}
    if verified_role: kwargs['verified_role_name'] = verified_role
    if type: kwargs['verification_type'] = type
    db.update_settings(interaction.guild.id, **kwargs)
    await interaction.response.send_message("Settings updated!", ephemeral=True)

@bot.tree.command(name="sync", description="Sync slash commands (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("Commands synced!", ephemeral=True)

@bot.tree.command(name="verify_user", description="Manually verify a user")
@app_commands.checks.has_permissions(manage_roles=True)
async def verify_user(interaction: discord.Interaction, member: discord.Member):
    result = await complete_verification_logic(interaction.guild, member, f"Manual ({interaction.user})")
    await interaction.response.send_message(result if isinstance(result, str) else f"✅ {member} verified!")

@bot.tree.command(name="unverify_user", description="Remove verification")
@app_commands.checks.has_permissions(manage_roles=True)
async def unverify_user(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    settings = await get_guild_settings(interaction.guild.id)
    v_role = discord.utils.get(interaction.guild.roles, name=settings['verified_role_name'])
    if v_role in member.roles:
        await member.remove_roles(v_role, reason=reason)
        uv_role = discord.utils.get(interaction.guild.roles, name=settings['unverified_role_name'])
        if uv_role: await member.add_roles(uv_role)
        await interaction.response.send_message(f"🚫 {member} unverified.")
    else:
        await interaction.response.send_message("User not verified.", ephemeral=True)

if __name__ == "__main__":
    bot.run(global_config['bot_token'])
