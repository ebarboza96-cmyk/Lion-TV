/**
 * 🤖 BOT WHATSAPP IPTV - Lion TV
 * Servidor webhook que conecta WaSenderAPI con Claude AI
 * para automatizar ventas de IPTV con notificaciones al dueño.
 *
 * Stack: Node.js + Express + Anthropic SDK + Axios
 * Deploy: Railway.app
 */

const express = require("express");
const axios = require("axios");
const Anthropic = require("@anthropic-ai/sdk");

const app = express();
app.use(express.json());

// ============================================================
// ⚙️ CONFIGURACIÓN — Rellena estas variables en Railway
// ============================================================
const CONFIG = {
  // WaSenderAPI
  WASENDER_API_KEY: process.env.WASENDER_API_KEY,   // Tu API Key de WaSenderAPI
  WASENDER_SESSION: process.env.WASENDER_SESSION,   // Tu Session ID (ej: 75080)

  // Claude AI
  ANTHROPIC_KEY: process.env.ANTHROPIC_API_KEY,

  // Tu número de WhatsApp para recibir notificaciones
  OWNER_PHONE: process.env.OWNER_PHONE,   // Ej: 50688887777 (sin +)
};

// ============================================================
// 🧠 SYSTEM PROMPT — Personalidad y conocimiento del bot
// ============================================================
const SYSTEM_PROMPT = `Eres un asesor de ventas experto en IPTV para Lion TV. Tu trabajo es atender clientes por WhatsApp, explicarles el servicio, ofrecerles demos gratuitas y cerrar ventas. Eres amable, entusiasta y conocedor. Hablas de forma natural y cercana, como un costarricense/hondureño.

## TU SERVICIO — Lion TV IPTV Premium

### ¿Qué ofrecemos?
- 📺 +5,000 canales HD y Full HD — TV nacional e internacional de todos los países
- 🎬 +50,000 películas en FHD y 4K — incluye contenido de Netflix, HBO Max, Star+, Paramount, Disney+ y más
- 📡 +8,000 series completas — estrenos muy actualizados, ¡y tomamos pedidos de películas y series!
- ⚽ Todos los deportes en vivo: Champions, LaLiga, Premier, Ligue 1, Liga Nacional, Tigo Sports, FUTV, Star+ exclusivos, UFC, NBA, NFL, MLB, Fórmula 1
- 🎯 Calidad HD, Full HD y 4K
- 📱 Compatible con: Windows, Mac, Web, Android, iOS, Smart TV, TV Box, Firestick, Consolas
- ✅ Hasta 3 dispositivos simultáneos incluidos en todos los planes
- 📲 App propia: se instala fácil con el link https://hostinghn.com/v7.apk

### INSTALACIÓN (TV Box, Android TV, FireStick)
1. Abrir la tienda de apps y buscar *Downloader*
2. Descargar e instalar Downloader
3. Abrir Downloader e ingresar: https://hostinghn.com/v7.apk
4. Descargar e instalar la app
5. Abrir la app e ingresar usuario y contraseña

### PLANES Y PRECIOS
El precio base es ₡6,000 al mes (también hay planes trimestrales, semestrales y anuales con descuento).
Todos los planes incluyen hasta 3 dispositivos simultáneos.

Si el cliente pregunta por precios en dólares, usa los siguientes planes:

**🖥️ Plan 1 Conexión**
- 1 mes → $10
- 3 meses + 15 días gratis → $30
- 5 meses + 1 MES GRATIS → $50 ⭐
- 10 meses + 2 MESES GRATIS → $100

**🖥️🖥️ Plan 2 Conexiones**
- 1 mes → $11 | 3 meses → $33 | 5+1 → $55 | 10+2 → $110

**🖥️🖥️🖥️ Plan 3 Conexiones**
- 1 mes → $12 | 3 meses → $36 | 5+1 → $60 | 10+2 → $120

**🖥️🖥️🖥️🖥️🖥️ Plan 5 Conexiones**
- 1 mes → $16 | 3 meses → $48 | 5+1 → $80 | 10+2 → $160

### MÉTODOS DE PAGO
- SINPE Móvil (Costa Rica)
- Transferencia bancaria
- (El dueño les dará el número/cuenta al confirmar el pedido)

## FLUJO DE CONVERSACIÓN

Cuando alguien escribe por primera vez:
1. Salúdalos calurosamente
2. Pregunta qué dispositivo tienen y cuántas pantallas necesitan
3. Ofréceles la demo GRATIS de 24 horas
4. Cuando quieran la demo, diles que la estás activando (el sistema la crea automáticamente)
5. Cuando quieran comprar, di que vas a conectarlos con el equipo para el pago y escribe: [NOTIFICAR_DUEÑO]

### MÉTODOS DE PAGO
- SINPE Móvil (Costa Rica)
- Transferencia bancaria
- El dueño les dará los detalles al confirmar

## REGLAS IMPORTANTES
- Sé conciso, usa emojis con moderación pero de forma natural
- Siempre destaca el valor de las promociones (meses gratis)
- Cuando alguien dude, ofrece la demo ANTES de insistir con precios
- Si preguntan por canales específicos, confirma que sí los tenemos
- No inventes información técnica que no sabes
- Las demos duran 6 horas, son gratuitas, y las activa el dueño manualmente
- Cuando el cliente pida la demo, escribe exactamente al final: [DEMO_SOLICITADA]
- Cuando el cliente esté listo para pagar, escribe exactamente al final: [NOTIFICAR_DUEÑO]

## EJEMPLOS DE RESPUESTAS

Cliente: "hola me interesa"
Tú: "¡Hola! 👋 Bienvenido a Lion TV — servicio de TV premium por internet. Tenemos +5,000 canales, +50,000 películas y +8,000 series, todo en HD y 4K 🔥

¿En qué dispositivo lo querés ver? (Smart TV, TV Box, Firestick, celular...) y ¿cuántas pantallas necesitás?"

Cliente: "quiero ver el partido del Real Madrid"
Tú: "¡Claro! ⚽ Tenemos LaLiga, Champions League, Premier y todos los partidos en vivo. También Star+ exclusivos, ESPN, Tigo Sports y mucho más.

¿Querés probar con una demo GRATIS de 6 horas para ver la calidad tú mismo? 🎁"

Cliente: "cuánto cuesta?"
Tú: "Solo ₡6,000 al mes, con planes trimestrales, semestrales y anuales con meses de regalo 🎁 Incluye hasta 3 dispositivos simultáneos.

¿Querés que te active una demo gratis de 6 horas primero para que lo pruebes sin compromiso?"`;

// ============================================================
// 💬 Memoria de conversaciones (en RAM — simple y funcional)
// ============================================================
const conversations = new Map(); // phone -> [{role, content}]

function getHistory(phone) {
  if (!conversations.has(phone)) {
    conversations.set(phone, []);
  }
  return conversations.get(phone);
}

function addMessage(phone, role, content) {
  const history = getHistory(phone);
  history.push({ role, content });
  // Mantener solo los últimos 20 mensajes para no exceder el contexto
  if (history.length > 20) {
    conversations.set(phone, history.slice(-20));
  }
}

// ============================================================
// 📨 Enviar mensaje por WhatsApp (WaSenderAPI)
// ============================================================
async function sendMessage(to, text) {
  try {
    await axios.post(
      `https://wasenderapi.com/api/send-message`,
      {
        session_id: CONFIG.WASENDER_SESSION,
        to: `${to}@c.us`,
        text,
      },
      {
        headers: {
          Authorization: `Bearer ${CONFIG.WASENDER_API_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );
  } catch (err) {
    console.error("Error enviando mensaje:", err.response?.data || err.message);
  }
}

// ============================================================
// 🤖 Procesar mensaje con Claude AI
// ============================================================
async function procesarMensaje(phone, mensaje) {
  const client = new Anthropic({ apiKey: CONFIG.ANTHROPIC_KEY });

  addMessage(phone, "user", mensaje);
  const history = getHistory(phone);

  const response = await client.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1000,
    system: SYSTEM_PROMPT,
    messages: history,
  });

  const respuesta = response.content[0].text;
  addMessage(phone, "assistant", respuesta);

  return respuesta;
}

// ============================================================
// 🔔 Notificar al dueño cuando alguien quiere comprar
// ============================================================
async function notificarDuenio(clientePhone, mensaje) {
  if (!CONFIG.OWNER_PHONE) return;
  await sendMessage(
    CONFIG.OWNER_PHONE,
    `🔔 ${mensaje}\n\n📱 Número cliente: +${clientePhone}`
  );
}

// ============================================================
// 🌐 WEBHOOK — Recibir mensajes de WaSenderAPI
// ============================================================

// WaSenderAPI envía los mensajes entrantes vía POST al webhook
app.post("/webhook", async (req, res) => {
  res.sendStatus(200); // Responder rápido

  try {
    const body = req.body;

    // WaSenderAPI formato: { event: "message", data: { from, body, type } }
    if (body?.event !== "message") return;
    if (body?.data?.type !== "chat") return; // Solo texto

    // Ignorar mensajes propios (los que envía el bot)
    if (body?.data?.fromMe) return;

    const phone = body.data.from.replace("@c.us", "");
    const texto = body.data.body;

    console.log(`📩 Mensaje de +${phone}: ${texto}`);

    // Obtener respuesta de Claude
    const respuesta = await procesarMensaje(phone, texto);

    // Detectar comandos especiales en la respuesta
    if (respuesta.includes("[DEMO_SOLICITADA]")) {
      const respuestaLimpia = respuesta.replace("[DEMO_SOLICITADA]", "").trim();
      await sendMessage(phone, respuestaLimpia);
      await sendMessage(
        phone,
        `⏳ Estoy activando tu demo ahora mismo. En unos minutos te mando tus credenciales para que pruebes. ¡Esperate tantito! 🙌`
      );
      // Notificar al dueño para activar la demo manualmente
      await notificarDuenio(phone, "🎯 *DEMO SOLICITADA*\n\nEste cliente quiere probar el servicio. Activale la demo de 6 horas y mandales las credenciales.");
    } else if (respuesta.includes("[NOTIFICAR_DUEÑO]")) {
      const respuestaLimpia = respuesta.replace("[NOTIFICAR_DUEÑO]", "").trim();
      await sendMessage(phone, respuestaLimpia);
      await notificarDuenio(phone, "💰 *CLIENTE LISTO PARA COMPRAR*\n\nEscríbele para cerrar la venta y cobrar.");
    } else {
      await sendMessage(phone, respuesta);
    }
  } catch (err) {
    console.error("❌ Error procesando mensaje:", err);
  }
});

// Health check
app.get("/", (req, res) => {
  res.json({ status: "🦁 Lion TV Bot activo", timestamp: new Date().toISOString() });
});

// ============================================================
// 🚀 INICIAR SERVIDOR
// ============================================================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🦁 Lion TV Bot corriendo en puerto ${PORT}`);
  console.log(`📡 Webhook URL: https://TU-DOMINIO.railway.app/webhook`);
});
