const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode');
const path = require('path');

const app = express();
app.use(express.json());
app.use(express.static('public'));

// ==================== اعدادات ====================
const EMPLOYEE_PASSWORD = '1234'; // غيّر الباسورد ده
const PORT = 3000;
// =================================================

let qrCodeData = null;
let isReady = false;
let statusMessage = 'جاري الاتصال...';

const puppeteerConfig = {
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-accelerated-2d-canvas',
    '--no-first-run',
    '--no-zygote',
    '--disable-gpu',
    '--single-process'
  ]
};

// لو على الكلاود (Railway) يستخدم Chrome المنصب على النظام
if (process.env.PUPPETEER_EXECUTABLE_PATH) {
  puppeteerConfig.executablePath = process.env.PUPPETEER_EXECUTABLE_PATH;
}

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: './session' }),
  puppeteer: puppeteerConfig
});

client.on('qr', async (qr) => {
  console.log('✅ QR Code جاهز - افتح المتصفح على http://localhost:' + PORT + '/admin');
  qrCodeData = await qrcode.toDataURL(qr);
  isReady = false;
  statusMessage = 'في انتظار مسح QR Code';
});

client.on('ready', () => {
  console.log('✅ الواتساب متصل وجاهز!');
  isReady = true;
  qrCodeData = null;
  statusMessage = 'متصل وجاهز للإرسال ✅';
});

client.on('disconnected', (reason) => {
  console.log('❌ انقطع الاتصال:', reason);
  isReady = false;
  statusMessage = 'انقطع الاتصال - يرجى إعادة تشغيل السيرفر';
});

client.initialize();

// ==================== API ====================

// تسجيل الدخول
app.post('/api/login', (req, res) => {
  const { password } = req.body;
  if (password === EMPLOYEE_PASSWORD) {
    res.json({ success: true });
  } else {
    res.json({ success: false, message: 'كلمة السر غلط' });
  }
});

// حالة الاتصال + QR
app.get('/api/status', (req, res) => {
  res.json({ isReady, statusMessage, hasQR: !!qrCodeData });
});

// QR Code صورة
app.get('/api/qr', (req, res) => {
  if (qrCodeData) {
    res.json({ qr: qrCodeData });
  } else {
    res.json({ qr: null });
  }
});

// إرسال رسالة
app.post('/api/send', async (req, res) => {
  const { password, phone, message } = req.body;

  if (password !== EMPLOYEE_PASSWORD) {
    return res.json({ success: false, message: 'غير مصرح' });
  }

  if (!isReady) {
    return res.json({ success: false, message: 'الواتساب مش متصل دلوقتي' });
  }

  if (!phone || !message) {
    return res.json({ success: false, message: 'ادخل الرقم والرسالة' });
  }

  try {
    // تنظيف الرقم - بيشيل الصفر الأول ويضيف كود مصر لو مش موجود
    let cleanPhone = phone.replace(/\D/g, '');
    if (cleanPhone.startsWith('0')) {
      cleanPhone = '2' + cleanPhone; // كود مصر
    }
    if (!cleanPhone.startsWith('20') && cleanPhone.length === 10) {
      cleanPhone = '20' + cleanPhone;
    }

    const chatId = cleanPhone + '@c.us';
    await client.sendMessage(chatId, message);
    console.log(`✅ رسالة اتبعتت لـ ${cleanPhone}`);
    res.json({ success: true, message: `✅ الرسالة اتبعتت بنجاح لـ ${cleanPhone}` });
  } catch (err) {
    console.error('خطأ في الإرسال:', err.message);
    res.json({ success: false, message: 'فشل الإرسال: ' + err.message });
  }
});

// صفحة الأدمن (لمسح QR)
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.listen(PORT, () => {
  console.log(`\n🚀 السيرفر شغال على http://localhost:${PORT}`);
  console.log(`👨‍💼 الموظف يدخل على: http://localhost:${PORT}`);
  console.log(`🔑 باسورد الموظف: ${EMPLOYEE_PASSWORD}`);
  console.log(`📱 صفحة QR Code: http://localhost:${PORT}/admin\n`);
});
