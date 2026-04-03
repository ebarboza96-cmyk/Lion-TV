/**
 * 🤖 BOT WHATSAPP IPTV - Lion TV
 * Servidor webhook que conecta WaSenderAPI con Claude AI
 */

const express = require("express");
const axios = require("axios");
const Anthropic = require("@anthropic-ai/sdk");

const app = express();
app.use(express.json());

const CONFIG = {
  WASENDER_API_KEY: process.env.WASENDER_API_KEY,
  WASENDER_SESSION: process.env.WASENDER_SESSION,
  ANTHROPIC_KEY: process.env.ANTHROPIC_API_KEY,
  OWNER_PHONE: process.env.OWNER_PHONE,
};

const SYSTEM_PROMPT = `Eres un asesor de ventas experto en IPTV para Lion TV. Atiendes clientes por WhatsApp, les explicas el servicio, ofreces demos y cierras ventas. Eres amable y natural, como un costarricense.

SERVICIO:
- +5,000 canales HD/FHD de todos los países
- +50,000 películas (Netflix, HBO, Disney+, Star+, Prime)
- +8,000 series completas y actualizadas
- Deportes: LaLiga, Champions, Premier, Liga Nacional, UFC, NBA, NFL, F1
- Compatible con Smart TV, TV Box, Firestick, celular, PC, iPhone
- Hasta 3 dispositivos simultáneos
- App: https://hostinghn.com/v7.apk

INSTALACIÓN TV Box/Firestick:
1. Descargar Downloader
2. Ingresar https://hostinghn.com/v7.apk
3. Instalar y abrir la app
4. Ingresar usuario y contraseña

PRECIOS (todos incluyen 3 dispositivos):
- 1 mes: ₡6,000 / $10
- 3 meses + 15 días: $30
- 5 meses + 1 MES GRATIS: $50
- 10 meses + 2 MESES GRATIS: $100
También hay planes de 2, 3 y 5 conexiones.

PAGO: SINPE Móvil o transferencia bancaria.

REGLAS:
- Sé conciso y natural
- Siempre ofrece la demo ANTES de hablar de precios
- Demo dura 6 horas, es gratis
- Cuando pidan demo escribe al final: [DEMO_SOLICITADA]
- Cuando quieran pagar escribe al final: [NOTIFICAR_DUENO]`;

const conversations = new Map();

function getHistory(phone) {
  if (!conversations.has(phone)) conversations.set(phone, []);
  return conversations.get(phone);
}

function addMessage(phone, role, content) {
  const history = getHistory(phone);
  history.push({ role, content });
  if (history.length > 20) conversations.set(phone, history.slice(-20));
}

async function sendMessage(to, text) {
  try {
    const phone = to.replace("@s.whatsapp.net", "").replace("@c.us", "").replace("+", "");
    console.log("Enviando mensaje a:", phone);
    const response = await axios.post(
      "https://wasenderapi.com/api/send-message",
      { to: phone, text: { body: text } },
      { headers: { Authorization: `Bearer ${CONFIG.WASENDER_API_KEY}`, "Content-Type": "application/json" } }
    );
    console.log("Mensaje enviado:", response.status);
  } catch (err) {
    console.error("Error enviando:", err.response?.data || err.message);
  }
}

async function procesarMensaje(phone, mensaje) {
  const client = new Anthropic({ apiKey: CONFIG.ANTHROPIC_KEY });
  addMessage(phone, "user", mensaje);
  const response = await client.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1000,
    system: SYSTEM_PROMPT,
    messages: getHistory(phone),
  });
  const respuesta = response.content[0].text;
  addMessage(phone, "assistant", respuesta);
  return respuesta;
}

async function notificarDuenio(clientePhone, mensaje) {
  if (!CONFIG.OWNER_PHONE) return;
  await sendMessage(CONFIG.OWNER_PHONE, `🔔 ${mensaje}\n\n📱 Cliente: +${clientePhone}`);
}

app.post("/webhook", async (req, res) => {
  res.sendStatus(200);
  try {
    const body = req.body;
    console.log("Webhook recibido evento:", body?.event, "| datos:", JSON.stringify(body?.data || {}).substring(0, 150));

    const event = body?.event;
    if (!event) return;

    let phone, texto;

    if (body?.data?.messages) {
      const msg = body.data.messages;
      if (msg?.key?.fromMe) return;
      phone = msg?.key?.cleanedSenderPn || msg?.key?.remoteJid?.replace("@s.whatsapp.net","").replace("@c.us","");
      texto = msg?.messageBody;
    } else if (body?.data?.key) {
      if (body?.data?.key?.fromMe) return;
      phone = body?.data?.key?.cleanedSenderPn || body?.data?.key?.remoteJid?.replace("@s.whatsapp.net","").replace("@c.us","");
      texto = body?.data?.messageBody || body?.data?.message?.conversation;
    }

    if (!phone || !texto || typeof texto !== 'string' || texto.trim() === '') {
      console.log("Mensaje ignorado - phone:", phone, "texto:", texto);
      return;
    }

    console.log("Procesando mensaje de", phone, ":", texto);
    const respuesta = await procesarMensaje(phone, texto);
    console.log("Respuesta generada:", respuesta.substring(0, 100));

    if (respuesta.includes("[DEMO_SOLICITADA]")) {
      const limpia = respuesta.replace("[DEMO_SOLICITADA]", "").trim();
      await sendMessage(phone, limpia);
      await sendMessage(phone, "⏳ Activando tu demo ahora. En unos minutos te mando las credenciales 🙌");
      await notificarDuenio(phone, "🎯 DEMO SOLICITADA - Activale demo de 6h");
    } else if (respuesta.includes("[NOTIFICAR_DUENO]")) {
      const limpia = respuesta.replace("[NOTIFICAR_DUENO]", "").trim();
      await sendMessage(phone, limpia);
      await notificarDuenio(phone, "💰 CLIENTE LISTO PARA COMPRAR");
    } else {
      await sendMessage(phone, respuesta);
    }
  } catch (err) {
    console.error("Error general:", err.message);
  }
});

app.get("/", (req, res) => {
  res.json({ status: "🦁 Lion TV Bot activo", timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🦁 Lion TV Bot corriendo en puerto ${PORT}`));
