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

FLUJO OBLIGATORIO PARA DEMO:
1. Primero preguntá el nombre completo del cliente (nombre y apellido)
2. Una vez que te digan el nombre, confirmá que vas a crear la demo
3. Entonces y solo entonces escribe: [DEMO_SOLICITADA:NombreCompleto]

REGLAS:
- Sé conciso y natural
- Siempre ofrece la demo ANTES de hablar de precios
- Demo dura 24 horas, es gratis y se crea automáticamente
- Destaca el ahorro de los planes largos
- NUNCA escribas [DEMO_SOLICITADA] sin tener el nombre completo del cliente
- Cuando quieran pagar escribe al final: [NOTIFICAR_DUENO]`;

const conversations = new Map();

// Generar usuario: primera letra nombre + apellido en minúsculas
// Ej: "Emmanuel Barboza" → "ebarboza"
function generarUsuario(nombreCompleto) {
  const partes = nombreCompleto.trim().toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // quitar tildes
    .replace(/[^a-z\s]/g, '')
    .split(/\s+/)
    .filter(p => p.length > 0);
  
  if (partes.length === 0) return 'demo' + Date.now().toString().slice(-4);
  if (partes.length === 1) return partes[0];
  
  // Primera letra del primer nombre + apellido completo
  return partes[0][0] + partes[partes.length - 1];
}

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

// Crear demo en liontv.vip con usuario basado en nombre del cliente
async function crearDemo(nombreCompleto) {
  const usuario = generarUsuario(nombreCompleto);
  console.log("Creando demo para:", nombreCompleto, "→ usuario:", usuario);
  
  try {
    // Paso 1: Obtener token CSRF del login
    const loginPage = await axios.get(`${CONFIG.LIONTV_URL}/login`, {
      maxRedirects: 5,
    });
    const tokenMatch = loginPage.data.match(/name="_token"[^>]+value="([^"]+)"/);
    if (!tokenMatch) throw new Error("No se encontró CSRF token en login");
    const csrfToken = tokenMatch[1];
    const cookies = loginPage.headers['set-cookie']?.map(c => c.split(';')[0]).join('; ') || '';

    // Paso 2: Hacer login
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
        },
        maxRedirects: 10,
        validateStatus: () => true,
      }
    );
    
    // Recopilar todas las cookies de sesión
    const allCookies = [
      ...loginPage.headers['set-cookie'] || [],
      ...loginResp.headers['set-cookie'] || [],
    ].map(c => c.split(';')[0]).join('; ');
    
    console.log("Login OK, obteniendo formulario trial...");

    // Paso 3: Obtener token CSRF del formulario trial
    const trialPage = await axios.get(`${CONFIG.LIONTV_URL}/lines/create/1/line`, {
      headers: { 'Cookie': allCookies },
      maxRedirects: 5,
    });
    const trialTokenMatch = trialPage.data.match(/name="_token"[^>]+value="([^"]+)"/);
    if (!trialTokenMatch) throw new Error("No se encontró CSRF token en trial form");
    const trialToken = trialTokenMatch[1];

    // Paso 4: Crear trial con usuario personalizado
    const createResp = await axios.post(`${CONFIG.LIONTV_URL}/lines/create/1`,
      new URLSearchParams({
        _token: trialToken,
        line_type: 'line',
        username: usuario,
        password: '',  // panel genera la contraseña automáticamente
        package: '102', // 1 MES (3 PANTALLAS)
        connections: '3',
        expire_date: '',
        description: `Demo WhatsApp - ${nombreCompleto}`,
      }).toString(),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Cookie': allCookies,
          'Referer': `${CONFIG.LIONTV_URL}/lines/create/1/line`,
        },
        maxRedirects: 10,
        validateStatus: () => true,
      }
    );

    // Paso 5: Extraer contraseña generada por el panel
    const html = createResp.data;
    
    // Buscar la contraseña en la respuesta o página de edición
    let password = null;
    const passInHtml = html.match(/name="password"[^>]+value="([^"]+)"/);
    if (passInHtml) password = passInHtml[1];
    
    // Si redireccionó a la página de edición, buscar ahí
    const finalUrl = createResp.request?.res?.responseUrl || '';
    if (!password && finalUrl.includes('/edit')) {
      const editPage = await axios.get(finalUrl, {
        headers: { 'Cookie': allCookies },
      });
      const p = editPage.data.match(/name="password"[^>]+value="([^"]+)"/);
      if (p) password = p[1];
    }
    
    // Buscar en líneas recientes si no encontramos contraseña
    if (!password) {
      const linesPage = await axios.get(`${CONFIG.LIONTV_URL}/lines`, {
        headers: { 'Cookie': allCookies },
      });
      // Buscar la fila con nuestro usuario
      const userRow = linesPage.data.match(new RegExp(usuario + '[^]*?<td[^>]*>([^<]{4,20})</td>'));
      if (userRow) password = userRow[1].trim();
    }

    if (!password) throw new Error("No se pudo obtener la contraseña generada");
    
    console.log("✅ Demo creada - usuario:", usuario, "pass:", password);
    return { usuario, password };
    
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

    // Detectar si tiene el tag de demo con nombre
    const demoMatch = respuesta.match(/\[DEMO_SOLICITADA:([^\]]+)\]/);

    if (demoMatch) {
      const nombreCliente = demoMatch[1].trim();
      const limpia = respuesta.replace(/\[DEMO_SOLICITADA:[^\]]+\]/, '').trim();
      await sendMessage(phone, limpia);
      await sendMessage(phone, "⏳ Creando tu demo ahora mismo, dame un momento... 🦁");

      try {
        const demo = await crearDemo(nombreCliente);
        const msg = `✅ ¡Tu demo está lista, ${nombreCliente.split(' ')[0]}!\n\n` +
          `📱 Descargá la app: https://hostinghn.com/v7.apk\n` +
          `👤 Usuario: ${demo.usuario}\n` +
          `🔑 Contraseña: ${demo.password}\n` +
          `⏰ Válida por 24 horas\n\n` +
          `Cualquier consulta me avisás 😊`;
        await sendMessage(phone, msg);
        await notificarDuenio(phone, `🎯 DEMO CREADA\nCliente: ${nombreCliente}\nUsuario: ${demo.usuario}`);
      } catch (err) {
        console.error("Fallo demo automática:", err.message);
        await sendMessage(phone, "⏳ En un momento te mando las credenciales de tu demo 🙌");
        await notificarDuenio(phone, `🎯 DEMO SOLICITADA (crear manual)\nCliente: ${nombreCliente}\nError: ${err.message}`);
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
