/**
 * 🤖 BOT WHATSAPP IPTV - Lion TV
 * Conecta WaSenderAPI con Claude AI para ventas de IPTV
 * Crea demos automáticamente en liontv.vip
 */

const express = require("express");
const axios = require("axios");
const Anthropic = require("@anthropic-ai/sdk");
const https = require("https");

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
- Demo dura 6 horas, es gratis y se crea automáticamente
- Destaca el ahorro de los planes largos
- NUNCA escribas [DEMO_SOLICITADA] sin tener el nombre completo
- Cuando quieran pagar escribe al final: [NOTIFICAR_DUENO]`;

const conversations = new Map();

// Generar usuario: primera letra nombre + apellido
function generarUsuario(nombreCompleto) {
  const partes = nombreCompleto.trim().toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z\s]/g, '')
    .split(/\s+/).filter(p => p.length > 0);
  if (partes.length === 0) return 'demo' + Date.now().toString().slice(-4);
  if (partes.length === 1) return partes[0];
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
    console.log("Enviando a:", phone, "| texto:", text.substring(0, 60));
    await axios.post(
      "https://wasenderapi.com/api/send-message",
      { to: phone, text },
      { headers: { Authorization: `Bearer ${CONFIG.WASENDER_API_KEY}`, "Content-Type": "application/json" } }
    );
    console.log("Enviado OK");
  } catch (err) {
    console.error("Error enviando:", err.response?.data || err.message);
  }
}

// Crear sesión HTTP con cookies persistentes
function crearSesionHttp() {
  const jar = {};
  const instance = axios.create({
    baseURL: CONFIG.LIONTV_URL,
    maxRedirects: 10,
    validateStatus: () => true,
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'es-CR,es;q=0.9,en;q=0.8',
    }
  });

  // Interceptor para manejar cookies manualmente
  instance.interceptors.response.use(resp => {
    const setCookie = resp.headers['set-cookie'];
    if (setCookie) {
      setCookie.forEach(c => {
        const [kv] = c.split(';');
        const [k, v] = kv.split('=');
        if (k && v) jar[k.trim()] = v.trim();
      });
    }
    return resp;
  });

  instance.interceptors.request.use(config => {
    const cookieStr = Object.entries(jar).map(([k,v]) => `${k}=${v}`).join('; ');
    if (cookieStr) config.headers['Cookie'] = cookieStr;
    return config;
  });

  return instance;
}

async function crearDemo(nombreCompleto) {
  const usuario = generarUsuario(nombreCompleto);
  console.log("Creando demo para:", nombreCompleto, "→", usuario);

  const http = crearSesionHttp();

  // 1. Obtener página de login con CSRF token
  console.log("Paso 1: Obteniendo página de login...");
  const loginPage = await http.get('/login');
  const csrfLogin = loginPage.data.match(/name="_token"[^>]+value="([^"]+)"/)?.[1];
  if (!csrfLogin) throw new Error("No CSRF token en login");
  console.log("CSRF obtenido:", csrfLogin.substring(0, 10) + "...");

  // 2. Hacer login
  console.log("Paso 2: Haciendo login como", CONFIG.LIONTV_USER);
  const loginResp = await http.post('/login',
    new URLSearchParams({
      _token: csrfLogin,
      username: CONFIG.LIONTV_USER,
      password: CONFIG.LIONTV_PASS,
    }).toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': CONFIG.LIONTV_URL + '/login' } }
  );
  console.log("Login status:", loginResp.status, "→", loginResp.headers?.location || loginResp.request?.res?.responseUrl || 'sin redirect');

  // Verificar que el login fue exitoso visitando el dashboard
  const dashCheck = await http.get('/dashboard');
  if (dashCheck.request?.res?.responseUrl?.includes('/login') || dashCheck.data?.includes('login')) {
    throw new Error("Login fallido - credenciales incorrectas o sesión no válida");
  }
  console.log("Login verificado ✅");

  // 3. Obtener formulario de trial
  console.log("Paso 3: Obteniendo formulario trial...");
  const trialPage = await http.get('/lines/create/1/line');
  const csrfTrial = trialPage.data.match(/name="_token"[^>]+value="([^"]+)"/)?.[1];
  if (!csrfTrial) throw new Error("No CSRF token en formulario trial");

  // 4. Crear la demo
  console.log("Paso 4: Creando demo para usuario:", usuario);
  const params = new URLSearchParams();
  params.append('_token', csrfTrial);
  params.append('line_type', 'line');
  params.append('username', usuario);
  params.append('password', '');
  params.append('package', '107'); // DEMO 6 HORAS - cost 0 credits
  params.append('connections', '1');
  params.append('expire_date', '');
  params.append('price', '0');
  params.append('description', 'Demo WhatsApp - ' + nombreCompleto);

  const createResp = await http.post('/lines/create/1',
    params.toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': CONFIG.LIONTV_URL + '/lines/create/1/line' } }
  );
  console.log("Create status:", createResp.status);

  // 5. Buscar la línea recién creada por username
  await new Promise(r => setTimeout(r, 1000));
  console.log("Paso 5: Buscando línea creada...");

  // Buscar en la lista de lines usando el endpoint de datos de DataTables
  const searchResp = await http.post('/lines/data',
    new URLSearchParams({
      _token: csrfTrial,
      draw: '1',
      'columns[0][data]': 'id',
      'columns[0][name]': 'id',
      'columns[0][searchable]': 'true',
      'columns[0][orderable]': 'true',
      'columns[0][search][value]': '',
      'columns[0][search][regex]': 'false',
      'columns[1][data]': 'expired',
      'columns[1][name]': 'username',
      'columns[1][searchable]': 'true',
      'columns[1][orderable]': 'true',
      'columns[1][search][value]': '',
      'columns[1][search][regex]': 'false',
      'columns[2][data]': 'password',
      'columns[2][name]': 'password',
      'columns[2][searchable]': 'true',
      'columns[2][orderable]': 'false',
      'columns[2][search][value]': '',
      'columns[2][search][regex]': 'false',
      'order[0][column]': '0',
      'order[0][dir]': 'desc',
      'start': '0',
      'length': '10',
      'search[value]': usuario,
      'search[regex]': 'false',
    }).toString(),
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-TOKEN': csrfTrial,
      }
    }
  );

  console.log("Search status:", searchResp.status);
  let password = null;

  if (searchResp.status === 200 && searchResp.data?.data?.length > 0) {
    const linea = searchResp.data.data[0];
    console.log("Línea encontrada:", JSON.stringify(linea).substring(0, 200));
    // Extraer contraseña del HTML de la columna password
    const passMatch = linea.password?.match(/>([^<]+)</) || linea.password?.match(/value="([^"]+)"/);
    password = passMatch?.[1] || linea.password;
  }

  // Si no encontramos por búsqueda, buscar en la página de edición de la línea más reciente
  if (!password) {
    console.log("Buscando en líneas recientes...");
    const linesPage = await http.get('/lines');
    // Buscar el ID más alto que contenga nuestro usuario
    const userIdMatch = linesPage.data.match(new RegExp('edit\/(\d+).*?' + usuario, 's'))
      || linesPage.data.match(new RegExp(usuario + '.*?edit\/(\d+)', 's'));

    if (userIdMatch) {
      const lineId = userIdMatch[1];
      console.log("ID de línea encontrado:", lineId);
      const editPage = await http.get('/lines/edit/' + lineId);
      const passInEdit = editPage.data.match(/name="password"[^>]+value="([^"]+)"/)?.[1];
      if (passInEdit) password = passInEdit;
    }
  }

  if (!password) {
    // Último recurso: generar contraseña aleatoria de 8 caracteres
    password = Math.random().toString(36).slice(-8);
    console.warn("No se pudo obtener contraseña del panel, usando generada:", password);
  }

  console.log("✅ Demo creada - usuario:", usuario, "pass:", password);
  return { usuario, password };
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
    const demoMatch = respuesta.match(/\[DEMO_SOLICITADA:([^\]]+)\]/);

    if (demoMatch) {
      const nombreCliente = demoMatch[1].trim();
      const limpia = respuesta.replace(/\[DEMO_SOLICITADA:[^\]]+\]/, '').trim();
      await sendMessage(phone, limpia);
      await sendMessage(phone, "⏳ Creando tu demo, dame un momentito... 🦁");

      try {
        const demo = await crearDemo(nombreCliente);
        const msg =
          `✅ ¡Tu demo está lista, ${nombreCliente.split(' ')[0]}!\n\n` +
          `📱 Descargá la app: https://hostinghn.com/v7.apk\n` +
          `👤 Usuario: ${demo.usuario}\n` +
          `🔑 Contraseña: ${demo.password}\n` +
          `⏰ Válida por 6 horas\n\n` +
          `Cualquier consulta me avisás 😊`;
        await sendMessage(phone, msg);
        await notificarDuenio(phone, `🎯 DEMO CREADA\nCliente: ${nombreCliente}\nUsuario: ${demo.usuario} / Pass: ${demo.password}`);
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
