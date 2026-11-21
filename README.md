# AI Orchestrator — Genel Paylaşım Paketi

Bu klasör Windows, Linux ve Debian tabanlı sistemler için temiz dağıtım paketleri içerir.

- `windows/` — Windows kaynağı ve PowerShell kurulum betiği
- `linux/` — Linux kaynağı, kurulum betiği ve `.tar.gz` arşivi
- `debian/` — Debian/Ubuntu/Kali için kurulum betiği ve arşiv

## Kullanıcı verileri
API anahtarları, ayarlar ve hafıza kullanıcı cihazında oluşturulur. Paylaşılan kaynakla birlikte herhangi bir kişisel ayar veya anahtar gönderilmez.

## Kaynak paketi içeriği
`config/settings.json.example` dışındaki ayar dosyaları, `.env`, hafıza dosyaları ve günlükler bu pakette bulunmaz.

## Sorumluluk ve Kullanım Koşulları

Bu yazılım **olduğu gibi** sunulur ve herhangi bir garanti verilmez. Kurulum, API anahtarları, terminal/desktop yetkileri, dosya işlemleri, hafıza, senkronizasyon, yedekleme, üçüncü taraf sağlayıcılar ve yapılan işlemlerden doğan sonuçların sorumluluğu tamamen kullanıcıya aittir.

Kullanıcı; yazılımı kendi cihazında ve yetkileri kapsamında sorumlu şekilde kullanmalı, önemli dosyaların yedeğini almalı, API anahtarlarını korumalı ve yüksek yetkili terminal, dosya, ekran veya klavye izinlerini yalnızca güvendiği işlerde açmalıdır.

Yazılımın hatalı çalışması, veri kaybı, güvenlik ihlali, üçüncü taraf hizmet kesintisi veya bu yazılımın kullanımından doğabilecek doğrudan/dolaylı zararlardan proje geliştiricileri sorumlu tutulamaz.

## Responsibility and Usage Terms

This software is provided **as is**, without any warranty. Installation, API keys, terminal and desktop permissions, file operations, memory, synchronization, backups, third-party providers, and all consequences of using the software are the user's sole responsibility.

The user must maintain backups of important data, protect credentials, and enable elevated terminal, file, screen, or keyboard permissions only for trusted operations. The developers are not liable for data loss, security incidents, service failures, or any direct or indirect damages arising from use of this software.

## Test ve Geliştirme Durumu / Testing Status

Bu proje şu anda **test aşamasındadır**. Tüm özellikler, güvenlik kontrolleri ve üçüncü taraf sağlayıcı bağlantıları henüz nihai üretim sürümünde değildir. Kullanıcılar uygulamayı yalnızca test, deneme ve yetkili sistemlerde kullanmalıdır.

This project is currently in the **testing stage**. All features, security controls, and third-party provider integrations should be considered work in progress and not a final production release. Users should run it only for testing, evaluation, and on systems they are authorized to use.
