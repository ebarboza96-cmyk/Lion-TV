/**
 * 🤖 BOT WHATSAPP IPTV - Lion TV
 * Conecta WaSenderAPI con Claude AI para ventas de IPTV
 * Crea demos automáticamente en el panel liontv.vip
 */

const express = require("express");
const axios = require("axios");
const Anthropic = require("@anthropic-ai/sdk");

const app = express();
app.use(express.json());

const CONFIG = {
  WASENDER_API_KEY: process.env.WASENDER_API_KEY,
  ANTHROPIC_KEY: process.env.ANTHROPIC_API_KEY,
  OWNER_PHONE: process.env.OWNER_PHONE,
  LIONTV_USER: process.env.LIONTV_USER,
  LIONTV_PASS: process.env.LIONTV_PASS,
  LIONTV_URL: "https://liontv.vip",
};

const SYSTEM_PROMPT = `Eres un asesor de ventas experto en IPTV para Lion TV. Atiendes clientes por WhatsApp. Eres amable y natural, como un costarricense.

SERVICIO:
- +5,000 canales HD/FHD de todos los países
- +50,000 películas (Netflix, HBO, Disney+, Star+, Prime)
- +8,000 series completas y actualizadas
- Deportes: LaLiga, Champions, Premier, Liga Nacional, UFC, NBA, NFL, F1
- Compatible con Smart TV, TV Box, Firestick, celular, PC, iPhone
- Hasta 3 dispositivos simultáneos en todos los planes
- App: https://hostinghn.com/v7.apk

INSTALACIÓN TV Box/Firestick:
1. Descargar Downloader
2. Ingresar https://hostinghn.com/v7.apk
3. Instalar y abrir la app
4. Ingresar usuario y contraseña

PRECIOS (todos incluyen 3 pantallas simultáneas):
- 1 mes: ₡7,000
- 3 meses: ₡19,000
- 6 meses: ₡35,000
- 1 año: ₡60,000

PAGO: SINPE Móvil o transferencia bancaria.

REGLAS:
- Sé conciso y natural
- Siempre ofrece la demo ANTES de hablar de precios
- Demo dura 24 horas, es gratis y se crea automáticamente
- Destaca el ahorro de los planes largos
- Cuando el cliente acepte la demo escribe al final: [DEMO_SOLICITADA]
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
    const phone = to.replace(/[@+]/g, '').replace('s.whatsapp.net','').replace('c.us','').trim();
    console.log("Enviando a:", phone, "| texto:", text.substring(0,60));
    const response = await axios.post(
      "https://wasenderapi.com/api/send-message",
      { to: phone, text },
      { headers: { Authorization: `Bearer ${CONFIG.WASENDER_API_KEY}`, "Content-Type": "application/json" } }
    );
    console.log("Enviado OK:", response.status);
  } catch (err) {
    console.error("Error enviando:", err.response?.data || err.message);
  }
}

// Crear demo en liontv.vip
async function crearDemo() {
  try {
    console.log("Creando demo en liontv.vip...");
    
    // Paso 1: Login para obtener cookies y token
    const loginPage = await axios.get(`${CONFIG.LIONTV_URL}/login`, {
      maxRedirects: 5,
      withCredentials: true,
    });
    
    // Extraer token CSRF del HTML
    const tokenMatch = loginPage.data.match(/name="_token"[^>]+value="([^"]+)"/);
    if (!tokenMatch) throw new Error("No se encontró el token CSRF en el login");
    const csrfToken = tokenMatch[1];
    const cookies = loginPage.headers['set-cookie']?.join('; ') || '';
    
    // Paso 2: Autenticarse
    const loginResp = await axios.post(`${CONFIG.LIONTV_URL}/login`, 
      new URLSearchParams({
        _token: csrfToken,
        username: CONFIG.LIONTV_USER,
        password: CONFIG.LIONTV_PASS,
      }).toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Cookie': cookies,
          'Referer': `${CONFIG.LIONTV_URL}/login`,
        },
        maxRedirects: 5,
        withCredentials: true,
      }
    );
    
    // Extraer cookies de sesión del login
    const sessionCookies = loginResp.headers['set-cookie']?.join('; ') || cookies;
    console.log("Login OK, obteniendo formulario trial...");
    
    // Paso 3: Obtener el formulario de trial para el token actualizado
    const trialPage = await axios.get(`${CONFIG.LIONTV_URL}/lines/create/1/line`, {
      headers: { 'Cookie': sessionCookies },
      maxRedirects: 5,
    });
    
    const trialTokenMatch = trialPage.data.match(/name="_token"[^>]+value="([^"]+)"/);
    if (!trialTokenMatch) throw new Error("No se encontró el token CSRF en trial");
    const trialToken = trialTokenMatch[1];
    
    // Paso 4: Crear el trial
    const trialResp = await axios.post(`${CONFIG.LIONTV_URL}/lines/create/1`,
      new URLSearchParams({
        _token: trialToken,
        line_type: 'line',
        username: '',
        password: '',
        package: '102', // 1 MES (3 PANTALLAS)
        connections: '3',
        expire_date: '',
        description: 'Demo creada por bot WhatsApp',
      }).toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Cookie': sessionCookies,
          'Referer': `${CONFIG.LIONTV_URL}/lines/create/1/line`,
        },
        maxRedirects: 5,
      }
    );
    
    // Extraer usuario y contraseña de la respuesta
    const userMatch = trialResp.data.match(/Username[^>]*>[^<]*<[^>]+>([^<]{3,30})<//) 
      || trialResp.data.match(/name="username"[^>]+value="([^"]+)"/)
      || trialResp.data.match(/"username":"([^"]+)"/);
    const passMatch = trialResp.data.match(/Password[^>]*>[^<]*<[^>]+>([^<]{3,30})<//)
      || trialResp.data.match(/name="password"[^>]+value="([^"]+)"/)
      || trialResp.data.match(/"password":"([^"]+)"/);
    
    if (userMatch && passMatch) {
      console.log("Demo creada:", userMatch[1], "/", passMatch[1]);
      return { usuario: userMatch[1], password: passMatch[1] };
    }
    
    // Si no podemos extraer, intentar buscar en la URL de redirección
    const finalUrl = trialResp.request?.res?.responseUrl || trialResp.config?.url || '';
    const idMatch = finalUrl.match(/\/lines\/(\d+)\/edit/);
    
    if (idMatch) {
      // Obtener los datos de la línea recién creada
      const lineData = await axios.get(`${CONFIG.LIONTV_URL}/lines/${idMatch[1]}/edit`, {
        headers: { 'Cookie': sessionCookies },
      });
      const u = lineData.data.match(/name="username"[^>]+value="([^"]+)"/);
      const p = lineData.data.match(/name="password"[^>]+value="([^"]+)"/);
      if (u && p) return { usuario: u[1], password: p[1] };
    }
    
    throw new Error("No se pudo extraer usuario/contraseña");
    
  } catch (err) {
    console.error("Error creando demo:", err.message);
    throw err;
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

function extraerMensaje(body) {
  const event = body?.event;
  const data = body?.data;
  if (['message.sent', 'messages.update', 'chats.update', 'messages.upsert', 'contacts.update'].includes(event)) return null;
  let phone, texto, fromMe;
  if (data?.messages) {
    const msg = data.messages;
    fromMe = msg?.key?.fromMe;
    if (fromMe) return null;
    phone = msg?.key?.cleanedSenderPn || msg?.key?.cleanedParticipantPn
      || msg?.key?.remoteJid?.replace('@s.whatsapp.net','').replace('@c.us','');
    texto = msg?.messageBody || msg?.message?.conversation || msg?.message?.extendedTextMessage?.text;
  } else if (data?.key) {
    fromMe = data?.key?.fromMe;
    if (fromMe) return null;
    phone = data?.key?.cleanedSenderPn
      || data?.key?.remoteJid?.replace('@s.whatsapp.net','').replace('@c.us','');
    texto = data?.messageBody || data?.message?.conversation || data?.message?.extendedTextMessage?.text;
  }
  if (!phone || !texto || typeof texto !== 'string' || texto.trim() === '') return null;
  return { phone, texto };
}

app.post("/webhook", async (req, res) => {
  res.sendStatus(200);
  try {
    const body = req.body;
    console.log("Evento:", body?.event);
    const result = extraerMensaje(body);
    if (!result) return;
    const { phone, texto } = result;
    console.log("✅ Procesando de", phone, ":", texto);
    const respuesta = await procesarMensaje(phone, texto);

    if (respuesta.includes("[DEMO_SOLICITADA]")) {
      const limpia = respuesta.replace("[DEMO_SOLICITADA]", "").trim();
      await sendMessage(phone, limpia);
      await sendMessage(phone, "⏳ Creando tu demo ahora mismo, dame un momento... 🦁");
      
      try {
        const demo = await crearDemo();
        const msg = `✅ ¡Tu demo está lista!\n\n` +
          `📱 App: https://hostinghn.com/v7.apk\n` +
          `👤 Usuario: ${demo.usuario}\n` +
          `🔑 Contraseña: ${demo.password}\n` +
          `⏰ Válida por 24 horas\n\n` +
          `Cualquier consulta me avisás 😊`;
        await sendMessage(phone, msg);
        await notificarDuenio(phone, `🎯 DEMO CREADA AUTOMÁTICAMENTE\nUsuario: ${demo.usuario}`);
      } catch (demoErr) {
        console.error("Fallo creando demo automática:", demoErr.message);
        await sendMessage(phone, "⏳ En un momento te mando las credenciales de tu demo 🙌");
        await notificarDuenio(phone, `🎯 DEMO SOLICITADA (crear manual)\nError automático: ${demoErr.message}`);
      }
      
    } else if (respuesta.includes("[NOTIFICAR_DUENO]")) {
      const limpia = respuesta.replace("[NOTIFICAR_DUENO]", "").trim();
      await sendMessage(phone, limpia);
      await notificarDuenio(phone, "💰 CLIENTE LISTO PARA COMPRAR\nEscríbele para cerrar la venta.");
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
app.listen(PORT, () => console.log(`🦁 Lion TV Bot en puerto ${PORT}`));
