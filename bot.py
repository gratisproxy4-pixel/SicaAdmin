import discord
from discord import app_commands
from discord.ext import commands
import base64
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric import ed25519
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= CONFIGURACIÓN =================
DISCORD_TOKEN = "MTU3NDE1MjUwMzY4NjIwNTQ4MQ.GWia9R._rWzmeozt-wGcfUhLpPQegogEAly7Z2boerHVM"

# Déjalo vacío la primera vez, usa /generar_llaves en Discord y luego pega aquí tu LLAVE PRIVADA:
PRIVATE_KEY_B64 = ""
# =================================================

class SicaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = SicaBot()

# Vista con únicamente el botón Copy
class LicenciaView(discord.ui.View):
    def __init__(self, autor_id: int, licencia_real: str):
        super().__init__(timeout=None)
        self.autor_id = autor_id
        self.licencia_real = licencia_real

    @discord.ui.button(label="Copy", emoji="📋", style=discord.ButtonStyle.secondary)
    async def copy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "⛔ Solo quien generó la licencia tiene acceso a ella.",
                ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"🔑 **Tu licencia (mantén presionado para copiar):**\n```{self.licencia_real}```",
            ephemeral=True
        )

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# 1. Comando para crear tus llaves criptográficas (se usa 1 sola vez)
@bot.tree.command(name="generar_llaves", description="Crea tu Llave Privada (Bot) y Llave Pública (App)")
@app_commands.checks.has_permissions(administrator=True)
async def generar_llaves(interaction: discord.Interaction):
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    
    priv_b64 = base64.b64encode(priv.private_bytes_raw()).decode()
    pub_b64 = base64.b64encode(pub.public_bytes_raw()).decode()
    
    mensaje = (
        f"🔐 **LLAVE PRIVADA (Pégala dentro de `bot.py`):**\n```{priv_b64}```\n"
        f"📱 **LLAVE PÚBLICA (Pégala dentro de tu app iOS):**\n```{pub_b64}```"
    )
    await interaction.response.send_message(mensaje, ephemeral=True)

# 2. Comando /getkey con solo el botón Copy
@bot.tree.command(name="getkey", description="Genera una licencia única vinculada a un dispositivo")
@app_commands.describe(
    device_id="El ID único que muestra la app (ej. A8F9-21C4)",
    dias="Cantidad de días de duración (ej. 1, 7, 30)"
)
@app_commands.checks.has_permissions(administrator=True)
async def getkey(interaction: discord.Interaction, device_id: str, dias: int):
    if not PRIVATE_KEY_B64:
        await interaction.response.send_message(
            "⚠️ Primero ejecuta `/generar_llaves` y pega tu Llave Privada en `bot.py`.",
            ephemeral=True
        )
        return

    try:
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(PRIVATE_KEY_B64)
        )
        ahora = datetime.now(timezone.utc)
        expiracion = ahora + timedelta(days=dias)
        exp_timestamp = int(expiracion.timestamp())
        fecha_exp_str = expiracion.strftime("%Y-%m-%d")

        # Firmar Device ID + Fecha
        payload = f"{device_id.strip().upper()}|{fecha_exp_str}".encode("utf-8")
        firma = private_key.sign(payload)
        token = base64.urlsafe_b64encode(payload + b"::" + firma).decode("utf-8")
        licencia_real = f"SICA-{token}"

        texto_dia = "1 día" if dias == 1 else f"{dias} días"

        embed = discord.Embed(
            title="Licencia generada",
            description=(
                f"✅ {interaction.user.mention} generó una licencia de {texto_dia}.\n\n"
                f"**Licencia**\n`SICA-XXXXXXXX`\n"
                f"**Duración**\n{texto_dia}\n"
                f"**Dispositivos**\n1 (`{device_id.upper()}`)\n"
                f"**Vencimiento**\n<t:{exp_timestamp}:F>\n<t:{exp_timestamp}:R>"
            ),
            color=discord.Color.from_rgb(43, 45, 49)
        )
        embed.set_footer(text="Pulsa Copy para copiar la licencia. Solo la persona que generó la licencia tiene acceso a ella.")

        view = LicenciaView(
            autor_id=interaction.user.id,
            licencia_real=licencia_real
        )

        await interaction.response.send_message(embed=embed, view=view)

    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", 8000), HealthHandler).serve_forever(),
    daemon=True
).start()

bot.run(DISCORD_TOKEN)
