/**
 * Bot WhatsApp IPTV - Lion TV
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

const SYSTEM_PROMPT = "Eres un asesor de ventas experto en IPTV para Lion TV. Atiendes clientes por WhatsApp. Eres amable y natural, como un costarricense.\n\n" +
"SERVICIO:\n" +
"- +5,000 canales HD/FHD de todos los paises\n" +
"- +50,000 peliculas (Netflix, HBO, Disney+, Star+, Prime)\n" +
"- +8,000 series completas y actualizadas\n" +
"- Deportes: LaLiga, Champions, Premier, Liga Nacional, UFC, NBA, NFL, F1\n" +
"- Compatible con Smart TV, TV Box, Firestick, celular, PC, iPhone\n" +
"- Hasta 3 dispositivos simultaneos en todos los planes\n" +
"- App: https://hostinghn.com/v7.apk\n\n" +
"INSTALACION TV Box/Firestick:\n" +
"1. Descargar Downloader\n" +
"2. Ingresar https://hostinghn.com/v7.apk\n" +
"3. Instalar y abrir la app\n" +
"4. Ingresar usuario y contrasena\n\n" +
"PRECIOS (todos incluyen 3 pantallas simultaneas):\n" +
"- 1 mes: 7,000 colones\n" +
"- 3 meses: 19,000 colones\n" +
"- 6 meses: 35,000 colones\n" +
"- 1 ano: 60,000 colones\n\n" +
"PAGO:\n" +
"- SINPE Movil al 6006-6642 (Emmanuel Barboza)\n" +
"- Pedile al cliente que ponga su nombre en la descripcion del SINPE\n" +
"- Cuando el cliente confirme el pago, avisa: [NOTIFICAR_DUENO]\n\n" +
"FLUJO PARA DEMO:\n" +
"1. Primero pregunta el nombre completo del cliente\n" +
"2. Una vez que digan el nombre, confirma que vas a crear la demo\n" +
"3. Escribe: [DEMO_SOLICITADA:NombreCompleto]\n\n" +
"REGLAS:\n" +
"- Se conciso y natural\n" +
"- Siempre ofrece la demo ANTES de hablar de precios\n" +
"- Demo dura 6 horas, es gratis y se crea automaticamente\n" +
"- Destaca el ahorro de los planes largos\n" +
"- NUNCA escribas [DEMO_SOLICITADA] sin tener el nombre completo\n" +
"- Cuando quieran pagar escribe al final: [NOTIFICAR_DUENO]";

const conversations = new Map();

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
      { headers: { Authorization: "Bearer " + CONFIG.WASENDER_API_KEY, "Content-Type": "application/json" } }
    );
    console.log("Enviado OK");
  } catch (err) {
    console.error("Error enviando:", err.response?.data || err.message);
  }
}

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
    const cookieStr = Object.entries(jar).map(([k,v]) => k + "=" + v).join('; ');
    if (cookieStr) config.headers['Cookie'] = cookieStr;
    return config;
  });
  return instance;
}

async function crearDemo(nombreCompleto) {
  const usuario = generarUsuario(nombreCompleto);
  console.log("Creando demo para:", nombreCompleto, "->", usuario);
  const http = crearSesionHttp();

  const loginPage = await http.get('/login');
  const csrfLogin = loginPage.data.match(/name="_token"[^>]+value="([^"]+)"/)?.[1];
  if (!csrfLogin) throw new Error("No CSRF token en login");

  await http.post('/login',
    new URLSearchParams({ _token: csrfLogin, username: CONFIG.LIONTV_USER, password: CONFIG.LIONTV_PASS }).toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': CONFIG.LIONTV_URL + '/login' } }
  );

  const dashCheck = await http.get('/dashboard');
  if (dashCheck.data?.includes('name="username"') && dashCheck.data?.includes('name="password"') && !dashCheck.data?.includes('Credits')) {
    throw new Error("Login fallido");
  }
  console.log("Login OK");

  const trialPage = await http.get('/lines/create/1/line');
  const csrfTrial = trialPage.data.match(/name="_token"[^>]+value="([^"]+)"/)?.[1];
  if (!csrfTrial) throw new Error("No CSRF token en trial");

  const params = new URLSearchParams();
  params.append('_token', csrfTrial);
  params.append('line_type', 'line');
  params.append('username', usuario);
  params.append('password', '');
  params.append('package', '107');
  params.append('connections', '1');
  params.append('expire_date', '');
  params.append('price', '0');
  params.append('description', 'Demo WhatsApp - ' + nombreCompleto);

  await http.post('/lines/create/1', params.toString(),
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': CONFIG.LIONTV_URL + '/lines/create/1/line' } }
  );
  console.log("Demo creada, buscando contrasena...");

  await new Promise(r => setTimeout(r, 1500));

  const linesPage = await http.get('/lines');
  const idMatch = linesPage.data.match(/\/lines\/edit\/(\d+)[^"]*"[^>]*>[^<]*<\/[^>]+>[^<]*<[^>]+>[^<]*<\/[^>]+>[^<]*<[^>]+>([^<]+)<\/[^>]+>[^<]*<[^>]+>([^<]+)</) ;

  let password = null;

  const editLinks = [...linesPage.data.matchAll(/href="[^"]*\/lines\/edit\/(\d+)"/g)];
  if (editLinks.length > 0) {
    const lastId = editLinks[0][1];
    console.log("Buscando en linea ID:", lastId);
    const editPage = await http.get('/lines/edit/' + lastId);
    const passMatch = editPage.data.match(/name="password"[^>]+value="([^"]+)"/);
    const userMatch = editPage.data.match(/name="username"[^>]+value="([^"]+)"/);
    if (userMatch?.[1] === usuario && passMatch) {
      password = passMatch[1];
    }
  }

  if (!password) {
    password = Math.random().toString(36).slice(-8);
    console.warn("Usando contrasena generada:", password);
  }

  console.log("Demo lista - usuario:", usuario, "pass:", password);
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
  await sendMessage(CONFIG.OWNER_PHONE, "🔔 " + mensaje + "\n\n📱 Cliente: +" + clientePhone);
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
    console.log("Procesando de", phone, ":", texto);

    const respuesta = await procesarMensaje(phone, texto);
    const demoMatch = respuesta.match(/\[DEMO_SOLICITADA:([^\]]+)\]/);

    if (demoMatch) {
      const nombreCliente = demoMatch[1].trim();
      const limpia = respuesta.replace(/\[DEMO_SOLICITADA:[^\]]+\]/, '').trim();
      await sendMessage(phone, limpia);
      await sendMessage(phone, "Creando tu demo, dame un momentito... 🦁");
      try {
        const demo = await crearDemo(nombreCliente);
        const msg = "Tu demo esta lista, " + nombreCliente.split(' ')[0] + "! ✅\n\n" +
          "App: https://hostinghn.com/v7.apk\n" +
          "Usuario: " + demo.usuario + "\n" +
          "Contrasena: " + demo.password + "\n" +
          "Valida por 6 horas\n\n" +
          "Cualquier consulta me avisas 😊";
        await sendMessage(phone, msg);
        await notificarDuenio(phone, "DEMO CREADA\nCliente: " + nombreCliente + "\nUsuario: " + demo.usuario + " / Pass: " + demo.password);
      } catch (err) {
        console.error("Fallo demo:", err.message);
        await sendMessage(phone, "En un momento te mando las credenciales 🙌");
        await notificarDuenio(phone, "DEMO SOLICITADA (crear manual)\nCliente: " + nombreCliente + "\nError: " + err.message);
      }
    } else if (respuesta.includes("[NOTIFICAR_DUENO]")) {
      const limpia = respuesta.replace("[NOTIFICAR_DUENO]", "").trim();
      await sendMessage(phone, limpia);
      await notificarDuenio(phone, "CLIENTE LISTO PARA COMPRAR\nEscribele para cerrar la venta.");
    } else {
      await sendMessage(phone, respuesta);
    }
  } catch (err) {
    console.error("Error general:", err.message);
  }
});

app.get("/", (req, res) => {
  res.json({ status: "Lion TV Bot activo", timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Lion TV Bot en puerto " + PORT));
