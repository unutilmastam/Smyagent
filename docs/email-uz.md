# Email yuborishni yoqish — `agent@itcode.uz` (telefondan, ~30 daqiqa)

Tartib: pochta → SPF/DKIM/DMARC → `.env` → **o'zingizga test xat** → yuborishni yoqish →
dashboard'da limit. Test o'tmaguncha mijozlarga hech narsa ketmaydi.

Belgilar: 👆 = cPanel'da bosiladigan joy, 📋 = Termius'ga nusxalanadigan buyruq.

---

## 1. Pochta yaratish (3 daqiqa)

1. 👆 cPanel → **Email Accounts** → **+ Create**.
2. **Domain**: `itcode.uz` · **Username**: `agent` · **Password**: **Generate** (kuchli parol)
   → parolni parol menejeriga yoki qog'ozga yozing (chatga yubormang).
   **Storage**: `1 GB` yetadi → **Create**.
3. Yaratilgan `agent@itcode.uz` qatorida 👆 **Connect Devices** → **Mail Client Manual
   Settings** bo'limidagi **SSL/TLS** qiymatlarini ko'ring:
   - Outgoing Server (SMTP): odatda `mail.itcode.uz`, port **465**
   - Incoming Server (IMAP): xuddi shu server, port **993**

   Server nomi boshqacha bo'lsa (masalan `hosting1.hostmaster.uz`) — 3-qadamda shuni yozasiz.

---

## 2. SPF, DKIM, DMARC — xatlar spamga tushmasligi uchun (10 daqiqa)

1. 👆 cPanel → **Email Deliverability** → `itcode.uz` qatori → **Manage**.
2. **DKIM**: "Problems exist" bo'lsa → **Install the suggested record** → ✅ "Valid".
3. **SPF**: "Problems exist" bo'lsa → **Install the suggested record** → ✅ "Valid".
   ⚠️ Ikkinchi SPF yozuvini qo'lda qo'shmang — cPanel mavjudini to'g'rilaydi.
4. **DMARC**: 👆 cPanel → **Zone Editor** → `itcode.uz` → **Manage** → **+ Add Record** →
   turi **TXT**:
   - **Name**: `_dmarc.itcode.uz.`
   - **Record**: 📋
     ```
     v=DMARC1; p=none; rua=mailto:agent@itcode.uz
     ```
   → **Save**. (2–3 hafta muammosiz ishlasa, `p=none` ni `p=quarantine` ga almashtiramiz.)
5. 5–10 daqiqa kuting, **Email Deliverability** sahifasini yangilang: SPF va DKIM ✅ bo'lsin.

> Agar "Install" tugmasi bo'lmasa yoki DNS boshqa joyda (Cloudflare va h.k.) bo'lsa —
> sahifadagi tavsiya qilingan yozuvlarni o'sha DNS panelga qo'shing, yoki hostmaster.uz
> qo'llab-quvvatlashiga yozing.

---

## 3. `.env` ga pochta sozlamalari (3 daqiqa)

📋 Termius'da (parolni faqat so'raganda, ekranda ko'rinmaydigan joyga kiritasiz):
```bash
cd ~/smyagent && source ~/virtualenv/smyagent/3.12/bin/activate && python scripts/setup_env.py --email
```
| Savol | Javob |
|---|---|
| Pochta serveri | Enter (`mail.itcode.uz`) yoki 1-qadamdagi server nomi |
| Pochta manzili | Enter (`agent@itcode.uz`) |
| Parol | 1-qadamdagi parol (avval Paste, keyin Enter) |

Skript `.env` ga o'zi yozadi: `SMTP_HOST`, `SMTP_PORT=465`, `SMTP_USE_SSL=true`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM=Mustafo — ITcoDe.Uz <agent@itcode.uz>`,
`IMAP_HOST`, `IMAP_PORT=993`, `IMAP_USERNAME`, `IMAP_PASSWORD` (javoblar, "STOP" va
qaytgan xatlarni o'qish uchun). `OUTBOUND_SENDING_ENABLED` **o'zgarmaydi** — hali `false`.

---

## 4. Avval o'zingizga test xat (2 daqiqa)

📋 O'zingizning shaxsiy manzilingizni yozing (masalan Gmail):
```bash
python -m app.cli email-test --to SIZNING@gmail.com
```
✅ Kutilgan natija:
```
✓ Test xat yuborildi: ...
✓ IMAP (javoblarni o'qish) ishlayapti: N ta o'qilmagan xat
Mijozlarga avtomatik yuborish: o'chiq (OUTBOUND_SENDING_ENABLED=false)
```
Gmail'da xatni oching → **⋮** → **Show original** (Asl nusxa): **SPF: PASS**,
**DKIM: PASS**, **DMARC: PASS** bo'lishi kerak.
- Xat **Spam**'ga tushsa → 2-qadamni tekshiring, 30 daqiqa kuting, testni qaytaring.
- `✗ Yuborilmadi: SMTP 535` → parol noto'g'ri: `python scripts/setup_env.py --email` ni qayta bajaring.
- `✗ ... OSError/timeout` → server nomi yoki port: 1-qadamdagi **Connect Devices** qiymatlarini oling.

---

## 5. Mijozlarga yuborishni yoqish (2 daqiqa)

Test ✅ bo'lgandan keyingina:
```bash
python scripts/setup_env.py --set OUTBOUND_SENDING_ENABLED
```
Javob: `true` → Enter. So'ng saytni qayta ishga tushiring:
```bash
bash scripts/deploy.sh --no-pull
```
Oxirgi 9-qadamda `✓ Email: sozlangan, yuborish YOQILGAN; javoblar o'qiladi` chiqadi.

---

## 6. Dashboard'da limit — kuniga 10 tadan boshlab (2 daqiqa)

👆 agent.itcode.uz → **⚙ Agent sozlamalari** → **Mustafo (suhbat)** → email bo'limi:

| Maydon | Qiymat |
|---|---|
| Birinchi kun nechta (qizdirish) | **10** |
| Har kuni qo'shiladi | **5** (har kuni 10 → 15 → 20 …) yoki **0** (doim 10) |
| Kuniga ko'pi bilan email | **30** (yoki 10 — hech qachon 10 dan oshmasin) |
| Xatlar orasida kamida (daqiqa) | **3** |
| Toza takliflarni mening tasdig'imsiz email qilish | Birinchi hafta **o'chiq** — har taklifni botda o'zingiz tasdiqlaysiz |

**Saqlash**. Tayyor: siz botda tasdiqlagan takliflar endi kompaniyaning ochiq email
manziliga (info@, sales@ …) kunlik limit ichida, xatlar orasida tanaffus bilan ketadi.

---

## Kuzatish va to'xtatish

- 👆 **📤 Yuborish** sahifasi: bugun nechta ketdi / limit, qaytgan xatlar, javoblar.
- Har xatda: Mustafo AI ekani, "STOP deb yozing" va bir bosishda obunadan chiqish havolasi.
- Qaytgan xatlar 5% dan oshsa yoki spam shikoyati kelsa — email **o'zi to'xtaydi**;
  sababini ko'rib, 📤 Yuborish'da qayta yoqasiz.
- ⛔ **STOP** (dashboard tepasi yoki botda `/stop_all`) — hammasi darhol to'xtaydi.
- Email ulanmasdan oldin tasdiqlangan takliflar Telegram/telefon vazifasiga aylangan bo'lishi
  mumkin — ular 📤 Yuborish sahifasida turadi.
- Istalgan payt umumiy tekshiruv: `python -m app.cli smoke-test`.
