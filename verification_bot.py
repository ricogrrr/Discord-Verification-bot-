import discord
from discord.ext import commands
import asyncio
import json
import logging
import random
import string
from datetime import datetime, timedelta
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    logger.error("config.json not found. Please create it with your bot settings.")
    exit(1)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix=config.get('prefix', '!'), intents=intents)

# Verification data storage
pending_verifications = {}

class CustomCaptcha:
    """Custom captcha generator with multiple challenge types"""
    
    @staticmethod
    def generate_math_captcha():
        """Generate a math problem captcha"""
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
        else:  # multiplication
            a, b = random.randint(2, 12), random.randint(2, 12)
            answer = a * b
            question = f"{a} × {b}"
        
        return question, str(answer)
    
    @staticmethod
    def generate_word_puzzle():
        """Generate a word unscrambling puzzle"""
        words = [
            "DISCORD", "VERIFY", "SECURE", "MEMBER", "SERVER", "CHANNEL", 
            "MESSAGE", "WELCOME", "SAFETY", "COMMUNITY", "GAMING", "CHAT",
            "FRIEND", "ONLINE", "DIGITAL", "CONNECT", "SOCIAL", "NETWORK"
        ]
        
        word = random.choice(words)
        scrambled = ''.join(random.sample(word, len(word)))
        
        # Make sure it's actually scrambled
        while scrambled == word:
            scrambled = ''.join(random.sample(word, len(word)))
        
        return f"Unscramble this word: **{scrambled}**", word
    
    @staticmethod
    def generate_ascii_captcha():
        """Generate ASCII art number captcha"""
        ascii_numbers = {
            '0': [
                " ███ ",
                "█   █",
                "█   █",
                "█   █",
                " ███ "
            ],
            '1': [
                "  █  ",
                " ██  ",
                "  █  ",
                "  █  ",
                " ███ "
            ],
            '2': [
                " ███ ",
                "    █",
                " ███ ",
                "█    ",
                "█████"
            ],
            '3': [
                " ███ ",
                "    █",
                " ███ ",
                "    █",
                " ███ "
            ],
            '4': [
                "█   █",
                "█   █",
                "█████",
                "    █",
                "    █"
            ],
            '5': [
                "█████",
                "█    ",
                "████ ",
                "    █",
                "████ "
            ],
            '6': [
                " ███ ",
                "█    ",
                "████ ",
                "█   █",
                " ███ "
            ],
            '7': [
                "█████",
                "    █",
                "   █ ",
                "  █  ",
                " █   "
            ],
            '8': [
                " ███ ",
                "█   █",
                " ███ ",
                "█   █",
                " ███ "
            ],
            '9': [
                " ███ ",
                "█   █",
                " ████",
                "    █",
                " ███ "
            ]
        }
        
        # Generate 2-digit number
        number = str(random.randint(10, 99))
        
        # Create ASCII art
        ascii_art = []
        for row in range(5):
            line = ""
            for digit in number:
                line += ascii_numbers[digit][row] + "  "
            ascii_art.append(line)
        
        ascii_display = "```\n" + "\n".join(ascii_art) + "\n```"
        return f"What number is shown in ASCII art?\n{ascii_display}", number
    
    @staticmethod
    def generate_emoji_sequence():
        """Generate emoji sequence captcha"""
        emojis = ['🔥', '⭐', '🎯', '🚀', '💎', '🎪', '🌟', '🎨', '🎭', '🎪', '🎲', '🎸']
        sequence_length = random.randint(3, 5)
        sequence = random.choices(emojis, k=sequence_length)
        
        # Remove one emoji from the middle
        missing_index = random.randint(1, len(sequence) - 2)
        missing_emoji = sequence[missing_index]
        display_sequence = sequence.copy()
        display_sequence[missing_index] = '❓'
        
        sequence_str = ' '.join(display_sequence)
        return f"Complete the sequence: {sequence_str}", missing_emoji
    
    @staticmethod
    def generate_color_code():
        """Generate color code captcha"""
        colors = {
            'RED': '🔴', 'BLUE': '🔵', 'GREEN': '🟢', 'YELLOW': '🟡',
            'PURPLE': '🟣', 'ORANGE': '🟠', 'BLACK': '⚫', 'WHITE': '⚪'
        }
        
        color_name = random.choice(list(colors.keys()))
        color_emoji = colors[color_name]
        
        return f"What color is this? {color_emoji}", color_name
    
    @staticmethod
    def generate_pattern_captcha():
        """Generate pattern recognition captcha"""
        patterns = [
            (['🔺', '🔻', '🔺', '🔻', '❓'], '🔺'),
            (['⬆️', '⬇️', '⬆️', '⬇️', '❓'], '⬆️'),
            (['🌙', '☀️', '🌙', '☀️', '❓'], '🌙'),
            (['❄️', '🔥', '❄️', '🔥', '❓'], '❄️'),
            (['🎵', '🎶', '🎵', '🎶', '❓'], '🎵')
        ]
        
        pattern, answer = random.choice(patterns)
        pattern_str = ' '.join(pattern)
        
        return f"Complete the pattern: {pattern_str}", answer

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes timeout
    
    @discord.ui.button(label='✅ Verify', style=discord.ButtonStyle.green, emoji='✅')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_verification(interaction)
    
    async def handle_verification(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        
        # Check if user is already verified
        verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
        if verified_role in user.roles:
            await interaction.response.send_message("You are already verified!", ephemeral=True)
            return
        
        # Start verification process
        verification_type = config.get('verification_type', 'button')
        
        if verification_type == 'custom_captcha':
            await self.start_custom_captcha_verification(interaction)
        elif verification_type == 'captcha':
            await self.start_captcha_verification(interaction)
        elif verification_type == 'reaction':
            await self.start_reaction_verification(interaction)
        else:
            await self.complete_verification(interaction)
    
    async def start_custom_captcha_verification(self, interaction: discord.Interaction):
        """Start custom captcha verification with random challenge type"""
        captcha_types = [
            CustomCaptcha.generate_math_captcha,
            CustomCaptcha.generate_word_puzzle,
            CustomCaptcha.generate_ascii_captcha,
            CustomCaptcha.generate_emoji_sequence,
            CustomCaptcha.generate_color_code,
            CustomCaptcha.generate_pattern_captcha
        ]
        
        # Choose random captcha type
        captcha_generator = random.choice(captcha_types)
        question, answer = captcha_generator()
        
        pending_verifications[interaction.user.id] = {
            'answer': answer.upper() if isinstance(answer, str) else answer,
            'timestamp': datetime.now(),
            'attempts': 0,
            'type': 'custom_captcha'
        }
        
        embed = discord.Embed(
            title="🧩 Custom Verification Challenge",
            description=f"{question}\n\n⏰ You have 5 minutes to complete this verification.\n🔄 You have 3 attempts.",
            color=0x00ff00
        )
        embed.set_footer(text="Type your answer in this channel")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def start_captcha_verification(self, interaction: discord.Interaction):
        # Generate random captcha
        captcha_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        pending_verifications[interaction.user.id] = {
            'code': captcha_code,
            'timestamp': datetime.now(),
            'attempts': 0,
            'type': 'simple_captcha'
        }
        
        embed = discord.Embed(
            title="🔐 Captcha Verification",
            description=f"Please type the following code to verify: `{captcha_code}`\n\nYou have 5 minutes to complete this verification.",
            color=0x00ff00
        )
        embed.set_footer(text="Type the code in this channel")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def start_reaction_verification(self, interaction: discord.Interaction):
        reactions = ['👍', '✅', '🎉', '🔥', '💯']
        chosen_reaction = random.choice(reactions)
        
        pending_verifications[interaction.user.id] = {
            'reaction': chosen_reaction,
            'timestamp': datetime.now(),
            'type': 'reaction'
        }
        
        embed = discord.Embed(
            title="🎯 Reaction Verification",
            description=f"Please react with {chosen_reaction} to this message to verify!",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        message = await interaction.followup.send("React here:", ephemeral=True)
        await message.add_reaction(chosen_reaction)
    
    async def complete_verification(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        
        try:
            # Add verified role
            verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
            if not verified_role:
                # Create verified role if it doesn't exist
                verified_role = await guild.create_role(
                    name=config['verified_role_name'],
                    color=discord.Color.green(),
                    reason="Verification bot setup"
                )
            
            await user.add_roles(verified_role, reason="User completed verification")
            
            # Remove unverified role if specified
            if config.get('unverified_role_name'):
                unverified_role = discord.utils.get(guild.roles, name=config['unverified_role_name'])
                if unverified_role and unverified_role in user.roles:
                    await user.remove_roles(unverified_role, reason="User completed verification")
            
            # Send success message
            success_messages = [
                "🎉 Verification Complete! Welcome to the server!",
                "✅ Successfully verified! You now have full access!",
                "🚀 Verification successful! Enjoy your stay!",
                "🌟 Welcome aboard! You're now a verified member!",
                "🎊 Congratulations! You've passed the verification!"
            ]
            
            embed = discord.Embed(
                title=random.choice(success_messages),
                description=f"Welcome to {guild.name}! You now have access to all channels.",
                color=0x00ff00
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Log verification
            logger.info(f"User {user.name} ({user.id}) completed verification in {guild.name}")
            
            # Send to log channel if configured
            if config.get('log_channel_id'):
                log_channel = bot.get_channel(config['log_channel_id'])
                if log_channel:
                    log_embed = discord.Embed(
                        title="New Verification",
                        description=f"{user.mention} has been verified",
                        color=0x00ff00,
                        timestamp=datetime.now()
                    )
                    log_embed.set_thumbnail(url=user.display_avatar.url)
                    await log_channel.send(embed=log_embed)
        
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to assign roles. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            await interaction.response.send_message(
                "❌ An error occurred during verification. Please try again or contact an administrator.",
                ephemeral=True
            )

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_member_join(member):
    """Handle new member joins"""
    guild = member.guild
    
    # Add unverified role if configured
    if config.get('unverified_role_name'):
        unverified_role = discord.utils.get(guild.roles, name=config['unverified_role_name'])
        if not unverified_role:
            # Create unverified role if it doesn't exist
            unverified_role = await guild.create_role(
                name=config['unverified_role_name'],
                color=discord.Color.red(),
                reason="Verification bot setup"
            )
        
        try:
            await member.add_roles(unverified_role, reason="New member - needs verification")
        except discord.Forbidden:
            logger.warning(f"Cannot add unverified role to {member.name}")
    
    # Send welcome message to verification channel
    if config.get('verification_channel_id'):
        channel = bot.get_channel(config['verification_channel_id'])
        if channel:
            embed = discord.Embed(
                title=f"Welcome to {guild.name}!",
                description=f"Hello {member.mention}! Please click the button below to verify your account and gain access to the server.",
                color=0x0099ff
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name="📋 Verification Process",
                value="Click the verify button below to start the verification process.",
                inline=False
            )
            
            view = VerificationView()
            await channel.send(embed=embed, view=view)

@bot.event
async def on_message(message):
    """Handle captcha verification responses"""
    if message.author.bot:
        return
    
    user_id = message.author.id
    if user_id in pending_verifications:
        verification_data = pending_verifications[user_id]
        
        # Check if verification has expired (5 minutes)
        if datetime.now() - verification_data['timestamp'] > timedelta(minutes=5):
            del pending_verifications[user_id]
            await message.reply("❌ Verification expired. Please try again.")
            return
        
        # Handle custom captcha verification
        if verification_data.get('type') == 'custom_captcha':
            user_answer = message.content.upper().strip()
            correct_answer = str(verification_data['answer']).upper().strip()
            
            if user_answer == correct_answer:
                del pending_verifications[user_id]
                
                # Complete verification
                guild = message.guild
                user = message.author
                
                try:
                    # Add verified role
                    verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
                    if not verified_role:
                        verified_role = await guild.create_role(
                            name=config['verified_role_name'],
                            color=discord.Color.green(),
                            reason="Verification bot setup"
                        )
                    
                    await user.add_roles(verified_role, reason="User completed custom captcha verification")
                    
                    # Remove unverified role if specified
                    if config.get('unverified_role_name'):
                        unverified_role = discord.utils.get(guild.roles, name=config['unverified_role_name'])
                        if unverified_role and unverified_role in user.roles:
                            await user.remove_roles(unverified_role, reason="User completed verification")
                    
                    # Success message with celebration
                    success_emojis = ['🎉', '🎊', '✨', '🌟', '🚀', '💫', '🎯', '🏆']
                    success_emoji = random.choice(success_emojis)
                    
                    success_messages = [
                        f"{success_emoji} Excellent! Custom captcha solved!",
                        f"{success_emoji} Brilliant! You've cracked the code!",
                        f"{success_emoji} Outstanding! Challenge completed!",
                        f"{success_emoji} Perfect! You're now verified!",
                        f"{success_emoji} Amazing! Welcome to the server!"
                    ]
                    
                    embed = discord.Embed(
                        title=random.choice(success_messages),
                        description=f"🎯 **Challenge Type:** Custom Captcha\n✅ **Status:** Verified Successfully\n🏠 **Welcome to:** {guild.name}",
                        color=0x00ff00
                    )
                    embed.add_field(
                        name="🎊 What's Next?",
                        value="You now have full access to all server channels and features!",
                        inline=False
                    )
                    
                    await message.reply(embed=embed)
                    
                    # Log verification
                    logger.info(f"User {user.name} ({user.id}) completed custom captcha verification in {guild.name}")
                    
                    # Send to log channel if configured
                    if config.get('log_channel_id'):
                        log_channel = bot.get_channel(config['log_channel_id'])
                        if log_channel:
                            log_embed = discord.Embed(
                                title="🧩 Custom Captcha Verification",
                                description=f"{user.mention} completed custom captcha verification",
                                color=0x00ff00,
                                timestamp=datetime.now()
                            )
                            log_embed.set_thumbnail(url=user.display_avatar.url)
                            log_embed.add_field(name="Challenge Type", value="Custom Captcha", inline=True)
                            log_embed.add_field(name="Attempts", value=str(verification_data['attempts'] + 1), inline=True)
                            await log_channel.send(embed=log_embed)
                
                except discord.Forbidden:
                    await message.reply("❌ I don't have permission to assign roles. Please contact an administrator.")
                except Exception as e:
                    logger.error(f"Error during custom captcha verification: {e}")
                    await message.reply("❌ An error occurred during verification. Please contact an administrator.")
            
            else:
                # Wrong answer
                verification_data['attempts'] += 1
                max_attempts = config.get('max_captcha_attempts', 3)
                
                if verification_data['attempts'] >= max_attempts:
                    del pending_verifications[user_id]
                    
                    fail_messages = [
                        "❌ Maximum attempts exceeded! Please try verification again.",
                        "🚫 Too many incorrect attempts! Please start over.",
                        "⛔ Verification failed! Please try the verification process again."
                    ]
                    
                    embed = discord.Embed(
                        title="🔒 Verification Failed",
                        description=random.choice(fail_messages),
                        color=0xff0000
                    )
                    embed.add_field(
                        name="💡 What to do next?",
                        value="Click the verification button again to get a new challenge!",
                        inline=False
                    )
                    
                    await message.reply(embed=embed)
                else:
                    remaining_attempts = max_attempts - verification_data['attempts']
                    
                    wrong_messages = [
                        f"❌ Incorrect answer! You have {remaining_attempts} attempts remaining.",
                        f"🤔 Not quite right! {remaining_attempts} attempts left.",
                        f"💭 Try again! {remaining_attempts} more chances."
                    ]
                    
                    embed = discord.Embed(
                        title="🎯 Try Again!",
                        description=random.choice(wrong_messages),
                        color=0xffaa00
                    )
                    embed.add_field(
                        name="💡 Hint",
                        value="Double-check your answer and try again. Make sure to type exactly what's asked!",
                        inline=False
                    )
                    
                    await message.reply(embed=embed)
        
        # Handle simple captcha verification
        elif verification_data.get('type') == 'simple_captcha':
            if message.content.upper() == verification_data['code']:
                del pending_verifications[user_id]
                
                # Complete verification (similar to custom captcha but simpler)
                guild = message.guild
                user = message.author
                
                try:
                    verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
                    if not verified_role:
                        verified_role = await guild.create_role(
                            name=config['verified_role_name'],
                            color=discord.Color.green(),
                            reason="Verification bot setup"
                        )
                    
                    await user.add_roles(verified_role, reason="User completed captcha verification")
                    
                    if config.get('unverified_role_name'):
                        unverified_role = discord.utils.get(guild.roles, name=config['unverified_role_name'])
                        if unverified_role and unverified_role in user.roles:
                            await user.remove_roles(unverified_role, reason="User completed verification")
                    
                    await message.reply("✅ Captcha verified! Welcome to the server!")
                    logger.info(f"User {user.name} ({user.id}) completed captcha verification in {guild.name}")
                
                except Exception as e:
                    logger.error(f"Error during captcha verification: {e}")
                    await message.reply("❌ An error occurred during verification.")
            
            else:
                verification_data['attempts'] += 1
                max_attempts = config.get('max_captcha_attempts', 3)
                
                if verification_data['attempts'] >= max_attempts:
                    del pending_verifications[user_id]
                    await message.reply("❌ Too many incorrect attempts. Please try verification again.")
                else:
                    remaining = max_attempts - verification_data['attempts']
                    await message.reply(f"❌ Incorrect code. You have {remaining} attempts remaining.")
    
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """Handle reaction verification"""
    if user.bot:
        return
    
    user_id = user.id
    if user_id in pending_verifications:
        verification_data = pending_verifications[user_id]
        
        if 'reaction' in verification_data:
            if str(reaction.emoji) == verification_data['reaction']:
                del pending_verifications[user_id]
                
                # Complete verification
                view = VerificationView()
                interaction_mock = type('MockInteraction', (), {
                    'user': user,
                    'guild': reaction.message.guild,
                    'response': type('MockResponse', (), {
                        'send_message': lambda embed, ephemeral: reaction.message.channel.send(f"{user.mention}", embed=embed)
                    })()
                })()
                
                await view.complete_verification(interaction_mock)

@bot.tree.command(name="setup_verification", description="Setup verification system in current channel")
@commands.has_permissions(administrator=True)
async def setup_verification(interaction: discord.Interaction):
    """Setup verification system"""
    embed = discord.Embed(
        title="🔐 Server Verification",
        description="Welcome to the server! Please verify your account to gain access to all channels.",
        color=0x0099ff
    )
    embed.add_field(
        name="📋 How to Verify",
        value="Click the **Verify** button below to start the verification process.",
        inline=False
    )
    embed.add_field(
        name="❓ Need Help?",
        value="If you're having trouble, please contact a staff member.",
        inline=False
    )
    embed.set_footer(text="This verification helps keep our server safe!")
    
    view = VerificationView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="verify_user", description="Manually verify a user")
@commands.has_permissions(manage_roles=True)
async def verify_user(interaction: discord.Interaction, member: discord.Member):
    """Manually verify a user"""
    guild = interaction.guild
    
    try:
        # Add verified role
        verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
        if not verified_role:
            verified_role = await guild.create_role(
                name=config['verified_role_name'],
                color=discord.Color.green(),
                reason="Verification bot setup"
            )
        
        await member.add_roles(verified_role, reason=f"Manually verified by {interaction.user}")
        
        # Remove unverified role if specified
        if config.get('unverified_role_name'):
            unverified_role = discord.utils.get(guild.roles, name=config['unverified_role_name'])
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="Manually verified")
        
        embed = discord.Embed(
            title="✅ User Verified",
            description=f"{member.mention} has been manually verified.",
            color=0x00ff00
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Log verification
        logger.info(f"User {member.name} ({member.id}) was manually verified by {interaction.user.name}")
        
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to manage roles.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error during manual verification: {e}")
        await interaction.response.send_message(
            "❌ An error occurred during verification.",
            ephemeral=True
        )

@bot.tree.command(name="verification_stats", description="Show verification statistics")
@commands.has_permissions(manage_guild=True)
async def verification_stats(interaction: discord.Interaction):
    """Show verification statistics"""
    guild = interaction.guild
    
    verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
    unverified_role = discord.utils.get(guild.roles, name=config.get('unverified_role_name', 'Unverified'))
    
    verified_count = len(verified_role.members) if verified_role else 0
    unverified_count = len(unverified_role.members) if unverified_role else 0
    total_members = guild.member_count
    
    embed = discord.Embed(
        title="📊 Verification Statistics",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    embed.add_field(name="✅ Verified Members", value=verified_count, inline=True)
    embed.add_field(name="❌ Unverified Members", value=unverified_count, inline=True)
    embed.add_field(name="👥 Total Members", value=total_members, inline=True)
    embed.add_field(name="📈 Verification Rate", value=f"{(verified_count/total_members*100):.1f}%" if total_members > 0 else "0%", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unverify_user", description="Remove verification from a user")
@commands.has_permissions(manage_roles=True)
async def unverify_user(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    """Remove verification from a user"""
    guild = interaction.guild
    
    try:
        # Check if user is verified
        verified_role = discord.utils.get(guild.roles, name=config['verified_role_name'])
        if not verified_role:
            await interaction.response.send_message(
                "❌ Verified role not found. Please set up verification first.",
                ephemeral=True
            )
            return
        
        if verified_role not in member.roles:
            await interaction.response.send_message(
                f"❌ {member.mention} is not currently verified.",
                ephemeral=True
            )
            return
        
        # Remove verified role
        await member.remove_roles(verified_role, reason=f"Unverified by {interaction.user.name}: {reason}")
        
        # Add unverified role if configured
        if config.get('unverified_role_name'):
            unverified_role = discord.utils.get(guild.roles, name=config['unverified_role_name'])
            if not unverified_role:
                # Create unverified role if it doesn't exist
                unverified_role = await guild.create_role(
                    name=config['unverified_role_name'],
                    color=discord.Color.red(),
                    reason="Verification bot setup"
                )
            
            await member.add_roles(unverified_role, reason=f"Unverified by {interaction.user.name}")
        
        # Success embed
        embed = discord.Embed(
            title="🚫 User Unverified",
            description=f"Successfully removed verification from {member.mention}",
            color=0xff6b6b
        )
        embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="🛡️ Moderator", value=f"{interaction.user.mention}", inline=True)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.timestamp = datetime.now()
        
        await interaction.response.send_message(embed=embed)
        
        # Log the unverification
        logger.info(f"User {member.name} ({member.id}) was unverified by {interaction.user.name} ({interaction.user.id}) in {guild.name}. Reason: {reason}")
        
        # Send to log channel if configured
        if config.get('log_channel_id'):
            log_channel = bot.get_channel(config['log_channel_id'])
            if log_channel:
                log_embed = discord.Embed(
                    title="🚫 User Unverified",
                    description=f"{member.mention} was unverified by {interaction.user.mention}",
                    color=0xff6b6b,
                    timestamp=datetime.now()
                )
                log_embed.set_thumbnail(url=member.display_avatar.url)
                log_embed.add_field(name="👤 User", value=f"{member.name}#{member.discriminator}", inline=True)
                log_embed.add_field(name="🛡️ Moderator", value=f"{interaction.user.name}#{interaction.user.discriminator}", inline=True)
                log_embed.add_field(name="📝 Reason", value=reason, inline=False)
                await log_channel.send(embed=log_embed)
        
        # Try to notify the user (if they allow DMs)
        try:
            dm_embed = discord.Embed(
                title=f"🚫 Verification Removed - {guild.name}",
                description=f"Your verification has been removed from **{guild.name}**.",
                color=0xff6b6b
            )
            dm_embed.add_field(name="📝 Reason", value=reason, inline=False)
            dm_embed.add_field(
                name="🔄 What's Next?",
                value="You can re-verify by going to the verification channel and clicking the verify button again.",
                inline=False
            )
            dm_embed.set_footer(text=f"Action performed by: {interaction.user.name}#{interaction.user.discriminator}")
            
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            # User has DMs disabled, that's okay
            pass
    
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to manage roles. Please check my permissions.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Error during unverification: {e}")
        await interaction.response.send_message(
            "❌ An error occurred while removing verification. Please try again.",
            ephemeral=True
        )

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore command not found errors
    else:
        logger.error(f"Command error: {error}")
        await ctx.send("❌ An error occurred while processing the command.")

# Run the bot
if __name__ == "__main__":
    try:
        bot.run(config['bot_token'])
    except KeyError:
        logger.error("Bot token not found in config.json")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")