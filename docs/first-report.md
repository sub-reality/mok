# İlk rapor — 17 Kasım 2026

## Gerçekten erişebildiğim ortam
Linux bulut konteyneri (Windows iş istasyonu değil): Python 3.13.18, Node 22.23.4, `claude` CLI, `claude-agent-sdk` 0.2.172. Depo `sub-reality/mok` yalnızca `README.md` içeriyordu. Sekiz artifact/belgeyi okuyabildim (liste: `evidence-register.md`, V9).

## Eksik bağlantılar
Windows iş istasyonu, GPU, QNAP, Obsidian, önceki iş akışı prototipleri, üç `claude.ai/project` bağlantısı, FM27 demosu, gerçek S25 Ultra / S Pen / saat. Güncel editing-shooting iş listen henüz gelmedi.

## İlk çalışan akış
Gerçek ajan çalışma zamanı (Claude Agent SDK, model `claude-fable-5-2`) üzerinden üç ofiste birer görev `awaiting_review` durumuna ulaştı:

| Ofis | Girdi | Çıktı | Araç çağrısı | Kanıt kaydı | Süre | SDK kullanım tahmini |
| --- | --- | --- | --- | --- | --- | --- |
| O.K. Film | sentetik brif + görev listesi | `production-plan.md` | 40 | 18 | 90 sn | $0,41 |
| Enstitü | Sub-Realism Part IX metni | `claim-evidence-map.md` | 27 | 23 | 85 sn | $0,47 |
| Okul | 3 kartlık Fokus 4 dersi (cevapları test için ben girdim) | `next-retrieval.md` | 9 | 5 | 39 sn | $0,18 |

İlk O.K. Film koşusu 30 araç çağrısı sınırına takılıp `budget_exhausted` ile başarısız oldu ($0,28); sınırı 90'a çıkarıp yeniden sıraya aldım. Hiçbir çıktıyı senin yerine kabul etmedim.

## Test sonuçları
- Çekirdek: 20 test geçti (sözleşme doğrulama, yinelenen komut, eski sürüm, geçersiz geçiş, yeniden oynatma ve imleç süresi, ofisler arası ret, yol ve araç sınırlaması, inceleme/kabul ayrımı, değişen çıktının onayı geçersiz kılması, başarısız araç, iptal isteği ve işçi onayı, bütçe aşımı, model ikamesi, ders akışı, prova deposu yalıtımı, yerel API). Bu testler **mock** ve test sağlayıcılarıyla çalışır.
- Arayüz: 32 tarayıcı kontrolü geçti (dört başlık satırı, Space'in durum/tarih değiştirmemesi, gönderilmemiş komutun gönderilmiş gösterilmemesi, prova yalıtımı, mürekkep kalıcılığı, bağlantı kopunca "eski" uyarısı, telefon genişliği).
- Canlı model koşuları: yukarıdaki tablo; toplam dört koşu, biri başarısız.
- Uçtan uca (arayüz ↔ canlı çekirdek API'si, geçici depo, mock sağlayıcı): 7 kontrol geçti — arayüzden girilen iş çekirdekte taslak görev oldu; CLI'den başlatılan koşu arayüzde göründü; inceleme sonrası değişen çıktının kabulünü çekirdek reddetti; çekirdek kapanınca arayüz "eski" uyarısı verdi.
- Yapılmadı: 30 görevlik fayda deneyi, gerçek cihazda S Pen ve saat, Windows kurulumu, canlı model ile arayüz üzerinden uçtan uca koşu.
