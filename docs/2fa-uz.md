# Ikki bosqichli kirish (2FA) — qisqa yo'riqnoma

Parolga qo'shimcha himoya: kirishda telefoningizdagi ilova ko'rsatgan 6 xonali kod so'raladi.
Parol o'g'irlansa ham, telefoningizsiz hech kim kira olmaydi.

## Yoqish (5 daqiqa, telefondan)

1. Telefonga **Google Authenticator** yoki **Microsoft Authenticator** o'rnating (App Store / Play Market).
2. 👆 agent.itcode.uz → **⚙ Sozlamalar** → **🔐 Ikki bosqichli kirish (2FA)** → **2FA ni yoqish**.
3. QR kodni skanerlang:
   - **iPad'da ochgan bo'lsangiz** — telefondagi ilovada «+» → «QR kodni skanerlash».
   - **Shu telefonning o'zida** — «ilovada ochish» havolasini bosing yoki ilovada «Kalitni kiritish»
     → hisob: `SMY Agent`, kalit: sahifadagi harflar (bo'sh joylarsiz ham bo'ladi).
4. Ilova ko'rsatgan **6 xonali kodni** kiriting → **Tasdiqlash va yoqish**.
5. **10 ta zaxira kod** chiqadi — faqat **bir marta** ko'rsatiladi.
   **Nusxa olish** → telefondan **boshqa** joyda saqlang: qog'ozga yozing yoki parol menejeriga.
   Chatga, Telegramga yubormang.

## Kirish

Login va parol → keyin **Tasdiqlash kodi** sahifasi → ilovadagi 6 xonali kod.
Kod har 30 soniyada yangilanadi; telefon soati to'g'ri bo'lsin (avtomatik vaqt yoqilgan).

## Telefon yo'qolsa

- **Zaxira kod bilan kiring** (masalan `abcde-fghjk`) — har biri **bir marta** ishlaydi.
  Keyin Sozlamalar → 2FA → **2FA ni o'chirish** → yangi telefonda qayta yoqing.
- **Zaxira kodlar ham yo'q bo'lsa** — 📋 Termius / cPanel Terminal'da:
  ```bash
  cd ~/smyagent && source ~/virtualenv/smyagent/3.12/bin/activate && python -m app.cli disable-totp --username bahrullo
  ```
  ✅ `2FA o'chirildi` → faqat parol bilan kiring → 2FA ni darhol qayta yoqing.
  @direktorsmybot'ga ham xabar keladi.

## Bilib qo'ying

- Zaxira kodlar 3 tadan kam qolsa — Sozlamalarda **Yangi zaxira kodlar** oling (eski kodlar bekor bo'ladi).
- 2FA ni yoqish / o'chirish va zaxira kod ishlatilishi jurnalga yoziladi; yoqish va o'chirishda botga xabar keladi.
- 5 marta noto'g'ri kod → 15 daqiqa kutish.
- `.env` dagi `APP_SECRET_KEY` o'zgartirilsa, 2FA ishlamay qoladi — yuqoridagi `disable-totp` buyrug'i bilan o'chirib, qayta yoqing.
