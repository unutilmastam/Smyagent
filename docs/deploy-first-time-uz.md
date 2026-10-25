# SMY Agent — birinchi deploy (telefondan, cPanel)

Bu yo'riqnomani telefonda ochib, qadamlarni ketma-ket bajaring. Har bir buyruqni
**to'liq nusxalab**, cPanel **Terminal**ga joylang (barmoq bilan bosib turing → *Paste*)
va **Enter** ni bosing. Taxminiy vaqt: 30–40 daqiqa.

> 🔐 **Parol va tokenlarni hech kimga yubormang** — chatga ham, GitHub'ga ham.
> Ularni faqat Terminal so'raganda o'zingiz kiritasiz.
>
> 🚫 **smy.itcode.uz**, **smarthome-api** ilovasi va `smy-api` virtualenviga tegilmaydi —
> barcha buyruqlar faqat `~/smyagent` papkasida ishlaydi.
>
> Tartib: MySQL baza → Python App 3.12 → git clone → env (`.env`) → migratsiya (deploy) →
> create-owner → webhooklar → cron. Email (`agent@itcode.uz`, SPF/DKIM/DMARC) deploydan keyin.

Belgilar: 👆 = cPanel'da bosiladigan joy, 📋 = Terminalga nusxalanadigan buyruq,
✅ = to'g'ri natija.

---

## 0. Tayyor bo'lishi kerak (siz qilgansiz)

- [x] `agent.itcode.uz` subdomeni (o'z papkasi bilan)
- [ ] **SSL**: 👆 cPanel → **SSL/TLS Status** → `agent.itcode.uz` yonida **yashil qulf**
      bo'lsin. Hali "Adding…" bo'lsa, 10–15 daqiqa kuting. Telegram faqat ishlaydigan
      HTTPS bilan ishlaydi.
- [x] Botlar: **@direktorsmybot** (siz uchun) va **@mustafosmybot** (mijozlar uchun),
      tokenlar va sizning raqamli Telegram ID'ingiz qo'lingizda.

---

## 1. MySQL baza yaratish (5 daqiqa)

1. 👆 cPanel → **Manage My Databases** (yoki **Database Wizard**).
2. **Yangi baza**: nom `smyagent` → *Create Database*.
   cPanel uning oldiga foydalanuvchi nomingizni qo'shadi, masalan `cpuser_smyagent`.
   **To'liq nomni yozib qo'ying.**
3. **Yangi foydalanuvchi**: nom `smy` → *Password Generator* bilan kuchli parol → parolni
   telefon eslatmalariga saqlang → *Create User*. To'liq nom masalan `cpuser_smy`.
4. **Foydalanuvchini bazaga qo'shish** (*Add User To Database*): `cpuser_smy` →
   `cpuser_smyagent` → **ALL PRIVILEGES** ✔ → *Make Changes*.

---

## 2. Python ilovani yaratish (5 daqiqa)

> ⚠️ Ro'yxatdagi **smarthome-api** (`smy.itcode.uz/api`) ilovasiga **tegmang** — uni
> tahrirlamang, to'xtatmang, qayta ishga tushirmang. Faqat yangi ilova yaratamiz.

1. 👆 cPanel → **Setup Python App** → **Create Application**.
2. To'ldiring:
   - **Python version**: `3.12` (3.12.x)
   - **Application root**: `smyagent`
   - **Application URL**: `agent.itcode.uz` (yo'l qismi bo'sh)
   - **Application startup file**: `passenger_wsgi.py`
   - **Application Entry point**: `application`
   - **Passenger log file**: bo'sh qoldiring
3. **Environment variables** bo'limiga **hech narsa qo'shmang** — sozlamalar 4-qadamda
   `.env` fayliga yoziladi. Sababi: bu ekrandagi o'zgaruvchilarni faqat sayt ko'radi,
   Terminal buyruqlari (migratsiya, webhook) va cron esa ko'rmaydi; `.env` ni uchalasi
   ham o'qiydi.
4. **Create** ni bosing.
5. Sahifa tepasida shunday buyruq chiqadi (o'zingizniki):
   `source /home/<login>/virtualenv/smyagent/3.12/bin/activate && cd /home/<login>/smyagent`
   👉 **Shu buyruqni nusxalab oling** — keyingi qadamlarda kerak bo'ladi.

---

## 3. Kodni serverga olish — git clone (2 daqiqa)

cPanel 2-qadamda `smyagent` papkasini yaratdi, shuning uchun kodni Terminal orqali
**shu papkaga** olamiz (cPanel'ning o'z `passenger_wsgi.py` fayli bizniki bilan almashadi).

1. 👆 cPanel → **Terminal**.
2. 📋 Joylang (bir qator):
   ```bash
   cd ~/smyagent && git init -q && (git remote add origin https://github.com/unutilmastam/Smyagent.git 2>/dev/null || git remote set-url origin https://github.com/unutilmastam/Smyagent.git) && git fetch -q origin main && git checkout -q -f -B main origin/main && git log -1 --format='✅ %h %s'
   ```
   ✅ Oxirida `✅ <kod> ...` qatori chiqadi.
3. 📋 Virtualenvga kiring (2-qadamdagi buyruq, masalan):
   ```bash
   source ~/virtualenv/smyagent/3.12/bin/activate && cd ~/smyagent
   ```

---

## 4. Env o'zgaruvchilar — `.env` (5 daqiqa)

1. Terminal ochiq va virtualenvda bo'lsin (3-qadam, 3-band). Yangi Terminal ochsangiz,
   o'sha `source ... && cd ~/smyagent` buyrug'ini qayta joylang.
2. 📋 Sozlash ustasini ishga tushiring:
   ```bash
   python scripts/setup_env.py
   ```
   U birma-bir so'raydi:
   | Savol | Nima kiritasiz |
   |---|---|
   | MySQL baza nomi | `cpuser_smyagent` (1-qadamdagi to'liq nom) |
   | MySQL foydalanuvchi nomi | `cpuser_smy` |
   | MySQL foydalanuvchi paroli | 1-qadamdagi parol |
   | @direktorsmybot tokeni | BotFather bergan token |
   | @mustafosmybot tokeni | BotFather bergan token |
   | Raqamli Telegram ID | @userinfobot bergan raqam |

   ℹ️ Parol va tokenlarni kiritganda **ekranda hech narsa ko'rinmaydi** — bu normal
   (xavfsizlik uchun). Joylang va Enter ni bosing.

   ✅ `✓ .env saqlandi` — tayyor. Maxfiy kalitlar (`APP_SECRET_KEY`,
   `TELEGRAM_WEBHOOK_SECRET`) avtomatik yaratildi; ularni bilishingiz shart emas.

   Xato kiritgan bo'lsangiz — buyruqni qayta bajaring yoki bitta qiymatni almashtiring:
   ```bash
   python scripts/setup_env.py --set TELEGRAM_ADMIN_IDS
   ```

---

## 5. Migratsiya va ishga tushirish — deploy (5–10 daqiqa)

📋
```bash
bash scripts/deploy.sh
```
Skript o'zi: kodni yangilaydi → kutubxonalarni o'rnatadi → sozlamalar va bazani
tekshiradi → zaxira oladi (birinchi marta kerak emas) → bazani yaratadi (migratsiya) →
ilovani qayta yuklaydi → saytni tekshiradi.

✅ Oxirida: `https://agent.itcode.uz ishlayapti ✅` va `deploy tugadi ✅`.

❗ Agar `health javob bermadi` desa: 👆 **Setup Python App** → ilova yonida **RESTART** →
so'ng 📋 `bash scripts/deploy.sh --no-pull`.

---

## 6. Sizning akkauntingiz (2 daqiqa)

📋
```bash
python -m app.cli create-owner --username bahrullo
```
Parolni ikki marta kiriting (kamida 12 belgi; ekranda ko'rinmaydi).

✅ Brauzerda **https://agent.itcode.uz** → login → bosh sahifa ochiladi.
(Telefonda "Bosh ekranga qo'shish" qilsangiz, ilova kabi ochiladi.)

---

## 7. Telegram botlarni ulash (3 daqiqa)

📋
```bash
python -m app.cli telegram-set-webhook
python -m app.cli telegram-set-client-webhook
python -m app.cli telegram-webhook-info
```
✅ Oxirgi buyruqda `url` = `https://agent.itcode.uz/api/v1/telegram/webhook` va
xato (`last_error_message`) yo'q.

Sinab ko'ring:
1. **@direktorsmybot** ga `/status` yozing → tizim holati keladi.
2. Boshqa telefondan (yoki do'stingizdan) **@mustafosmybot** ga `Salom` yozing →
   sizga @direktorsmybot'da **"Mustafo javobi (tasdiqlang)"** xabari keladi.

> Mijozga javob **hali ketmaydi** — `OUTBOUND_SENDING_ENABLED=false`. Tayyor bo'lganingizda:
> ```bash
> python scripts/setup_env.py --set OUTBOUND_SENDING_ENABLED
> ```
> `true` deb yozing, so'ng `touch tmp/restart.txt`.

---

## 8. Cron — agentlar o'zi ishlashi uchun (3 daqiqa)

👆 cPanel → **Cron Jobs** → *Add New Cron Job*.
Ro'yxatdagi **mavjud cron'larga tegmang** (boshqa saytlaringizniki) — faqat ikkita yangi qo'shamiz.

**1) Agentlar** — *Common Settings*: **Once Per Five Minutes** (`*/5 * * * *`).
Agar 5 daqiqaga ruxsat bo'lmasa — 10 yoki 15 daqiqa. **Command**:
```bash
cd $HOME/smyagent && $HOME/virtualenv/smyagent/3.12/bin/python -m app.jobs.runner --max-jobs 5 --max-seconds 240 --log-file $HOME/smyagent_data/runner.log >> $HOME/smyagent_data/runner-errors.log 2>&1
```

**2) Kunlik zaxira** — Minute `17`, Hour `3`, qolganlari `*`. **Command**:
```bash
cd $HOME/smyagent && $HOME/virtualenv/smyagent/3.12/bin/python -m app.cli db-backup >> $HOME/smyagent_data/backup.log 2>&1
```
Zaxiralar `~/smyagent_data/backups/` da, oxirgi 14 tasi saqlanadi.
Haftada bir marta bittasini telefoningizga yuklab oling (👆 File Manager → Download).

Log fayli o'zi kichik saqlanadi (1 MB dan oshsa almashadi) — tozalash shart emas.

✅ 10–15 daqiqadan keyin dashboard → **Kompaniyalar** ko'paya boshlaydi
(OpenStreetMap'dan avtomatik qidiruv), **Boshqaruv** sahifasida agentlar ishlaydi.
Boshqaruv va **🧾 Vazifalar** sahifasida "Cron ishlayapti: oxirgi marta N daqiqa oldin"
yozuvi chiqadi. Qizil "Fon ishlari N daqiqadan beri ishlamayapti" chiqsa — cron qatorini
tekshiring. @direktorsmybot'da `/jobs` ham shuni ko'rsatadi.

---

## 9. Yakuniy tekshiruv ro'yxati

- [ ] https://agent.itcode.uz ochiladi, login ishlaydi
- [ ] @direktorsmybot `/status` ga javob beradi
- [ ] @mustafosmybot ga yozilganda sizga tasdiqlash xabari keladi
- [ ] Cron qo'shildi; 15 daqiqadan keyin **Boshqaruv** sahifasida faoliyat bor
- [ ] @direktorsmybot `/jobs` → "✅ Cron ishlayapti"
- [ ] Dashboardda ⛔ **STOP** tugmasi ko'rinadi (favqulodda to'xtatish)

---

## Keyingi yangilanishlar (har safar)

Claude Code yangi funksiyani GitHub'ga qo'shganda, Terminalda bitta buyruq:
```bash
cd ~/smyagent && bash scripts/deploy.sh
```
U o'zi kodni tortadi, zaxira oladi, bazani yangilaydi va saytni tekshiradi.
(cPanel → Git Version Control → *Update from Remote* ni bosish shart emas.)

---

## Muammo bo'lsa

| Belgi | Nima qilish |
|---|---|
| Sayt `Service misconfigured` (503) | 📋 `python -m app.cli check-config` — xabarni o'qing; kerak bo'lsa `python scripts/setup_env.py --set <NOM>` |
| `Virtualenv topilmadi` | 3-qadam bajarilmagan yoki Python versiyasi boshqa. Python App sahifasidagi yo'lni ko'ring; boshqacha bo'lsa: `VENV=/to'liq/yo'l bash scripts/deploy.sh` |
| `.env yo'q` | 4-qadam: `python scripts/setup_env.py` |
| `Database reachable: NO` | 1-qadam: foydalanuvchi bazaga **ALL PRIVILEGES** bilan qo'shilganmi? Baza nomi/foydalanuvchi/parolni qayta kiriting: 📋 `python scripts/setup_env.py --database` |
| `Serverdagi kod qo'lda o'zgartirilgan` | Serverda fayl tahrirlangan. Claude Code'ga xabarni yuboring — o'zingiz o'chirmang |
| `Boshqa deploy ishlayapti` | 10 daqiqa kuting; to'xtab qolgan bo'lsa xabardagi `rmdir ...` buyrug'ini bajaring |
| Webhook: `SSL` yoki `certificate` xatosi | 0-qadam: SSL hali tayyor emas — kuting va 7-qadamni qaytaring |
| "Fon ishlari N daqiqadan beri ishlamayapti" | cPanel → Cron Jobs: qator bormi, yo'li to'g'rimi? 📋 `tail -5 ~/smyagent_data/runner-errors.log` — xabarni Claude Code'ga yuboring |
| Botga "⚠️ Vazifa bajarilmadi" keldi | Tugmani bosing: 🔁 *Qayta urinish* yoki 🔎 *Ko'rish*. Bir xil xato 6 soatda bir marta keladi |
| `mysqldump not found` | hostmaster.uz qo'llab-quvvatlashiga yozing: MySQL client kerak |

Xato chiqsa — **xabarni to'liq nusxalab** Claude Code'ga yuboring (parol/token
ko'rinmaydi, skript ularni chiqarmaydi). Barcha deploy yozuvlari:
`~/smyagent_data/deploy.log`.
