/**
 * 🤖 BOT WHATSAPP IPTV - Lion TV
 * Servidor webhook que conecta WaSenderAPI con Claude AI
 * para automatizar ventas de IPTV con notificaciones al dueño.
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

const SYSTEM_PROMPT = `Eres un asesor de ventas experto en IPTV para Lion TV. Tu trabajo es atender clientes por WhatsApp, explicarles el servicio, ofrecerles demos gratuitas y cerrar ventas. Eres amable, entusiasta y conocedor. Hablas de forma natural y cercana.

## TU SERVICIO — Lion TV IPTV Premium
- 📺 +5,000 canales HD y Full HD — TV nacional e internacional
- 🎬 +50,000 películas en FHD y 4K — Netflix, HBO Max, Star+, Paramount, Disney+
- 📡 +8,000 series completas — estrenos actualizados
- ⚽ Deportes: Champions, LaLiga, Premier, Ligue 1, Liga Nacional, Tigo Sports, UFC, NBA, NFL, MLB, F1
- 📱 Compatible con: Windows, Mac, Android, iOS, Smart TV, TV Box, Firestick
- ✅ Hasta 3 dispositivos simultáneos
- 📲 App: https://hostinghn.com/v7.apk

## INSTALACIÓN (TV Box, Android TV, FireStick)
1. Buscar Downloader en la tienda de apps
2. Abrir Downloader e ingresar: https://hostinghn.com/v7.apk
3. Instalar y abrir la app
4. Ingresar usuario y contraseña

## PRECIOS
₡6,000 al mes. También planes trimestrales, semestrales y anuales con descuento.
Todos los planes incluyen hasta 3 dispositivos simultáneos.

Planes en dólares:
- 1 conexión: $10/mes | $30 (3m+15d) | $50 (5m+1 gratis) | $100 (10m+2 gratis)
- 2 conexiones: $11/mes | $33 | $55 | $110
- 3 conexiones: $12/mes | $36 | $60 | $120
- 5 conexiones: $16/mes | $48 | $80 | $160

## MÉTODOS DE PAGO
SINPE Móvil y transferencia bancaria.

## REGLAS
- Sé conciso y natural, usa emojis con moderación
- Siempre ofrece la demo ANTES de insistir con precios
- Las demos duran 6 horas y son gratuitas
- Cuando pidan demo escribe al final: [DEMO_SOLICITADA]
- Cuando quieran pagar escribe al final: [NOTIFICAR_DUEÑO]`;

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
    await axios.post(
      "https://wasenderapi.com/api/send-text-message",
      { sessionId: CONFIG.WASENDER_SESSION, to: to.includes("@") ? to.split("@")[0] : to, text },
      { headers: { Authorization: `Bearer ${CONFIG.WASENDER_API_KEY}`, "Content-Type": "application/json" } }
    );
  } catch (err) {
    console.error("Error enviando mensaje:", err.response?.data || err.message);
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

// Webhook — recibe mensajes de WaSenderAPI
app.post("/webhook", async (req, res) => {
  res.sendStatus(200);
  try {
    const body = req.body;
    console.log("Webhook recibido:", JSON.stringify(body).substring(0, 200));

    // Soportar ambos formatos de evento
    const event = body?.event;
    if (!event) return;
    if (!["messages.received", "messages.upsert", "message"].includes(event)) return;

    // Extraer datos según el formato
    let phone, texto, fromMe;

    if (body?.data?.messages) {
      // Formato nuevo WaSenderAPI
      const msg = body.data.messages;
      fromMe = msg?.key?.fromMe;
      if (fromMe) return;
      phone = msg?.key?.cleanedSenderPn || msg?.key?.remoteJid?.replace("@s.whatsapp.net", "").replace("@c.us", "");
      texto = msg?.messageBody || msg?.message?.conversation || msg?.message?.extendedTextMessage?.text;
    } else if (body?.data?.from) {
      // Formato alternativo
      fromMe = body?.data?.fromMe;
      if (fromMe) return;
      phone = body.data.from.replace("@c.us", "").replace("@s.whatsapp.net", "");
      texto = body.data.body || body.data.text;
    }

    if (!phone || !texto) return;
    console.log(`📩 Mensaje de +${phone}: ${texto}`);

    const respuesta = await procesarMensaje(phone, texto);

    if (respuesta.includes("[DEMO_SOLICITADA]")) {
      const limpia = respuesta.replace("[DEMO_SOLICITADA]", "").trim();
      await sendMessage(phone, limpia);
      await sendMessage(phone, "⏳ Activando tu demo ahora mismo. En unos minutos te mando tus credenciales. ¡Esperame tantito! 🙌");
      await notificarDuenio(phone, "🎯 *DEMO SOLICITADA*\nEste cliente quiere probar. Activale la demo de 6 horas.");
    } else if (respuesta.includes("[NOTIFICAR_DUEÑO]")) {
      const limpia = respuesta.replace("[NOTIFICAR_DUEÑO]", "").trim();
      await sendMessage(phone, limpia);
      await notificarDuenio(phone, "💰 *CLIENTE LISTO PARA COMPRAR*\nEscríbele para cerrar la venta.");
    } else {
      await sendMessage(phone, respuesta);
    }
  } catch (err) {
    console.error("❌ Error:", err.message);
  }
});

app.get("/", (req, res) => {
  res.json({ status: "🦁 Lion TV Bot activo", timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🦁 Lion TV Bot corriendo en puerto ${PORT}`));
