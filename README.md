# AlbaSambosa — Sistem Penjualan Online

Sistem e-commerce untuk UMKM **AlbaSambosa** (kuliner frozen food), mengintegrasikan Market Basket Analysis (Apriori), Payment Gateway (Midtrans), dan Delivery Aggregator (Biteship).

## Tech Stack

| Lapisan | Teknologi |
| --- | --- |
| Backend | PHP 8.3, Laravel 13 |
| Frontend | Livewire 4, Alpine.js 3, Tailwind CSS 4 |
| Admin | Filament 5 |
| Database | MySQL 8.4 |
| Queue/Cache/Session | Database driver |

## Cara Menjalankan (Langkah demi Langkah)

### Prasyarat

- PHP 8.3 + ekstensi: `pdo_mysql`, `mbstring`, `xml`, `curl`, `fileinfo`
- MySQL 8.4 (atau MariaDB 10.11+)
- Composer 2.x
- Node.js 20+
- Python 3.x (untuk Apriori mining)

### 1. Clone & Install Dependency

```bash
git clone <repo-url> albasambosa
cd albasambosa
composer install
npm install && npm run build
```

### 2. Konfigurasi Environment

```bash
cp .env.example .env
php artisan key:generate
```

Edit file `.env` dan isi:
- **Database**: `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`
- **Midtrans** (opsional, untuk pembayaran): `MIDTRANS_SERVER_KEY`, `MIDTRANS_CLIENT_KEY`, `MIDTRANS_MERCHANT_ID`
- **Biteship** (opsional, untuk ongkir): `BITESHIP_API_KEY`
- **Twilio** (opsional, untuk WhatsApp): `TWILIO_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`

> **Catatan**: Midtrans dan Biteship mendukung mode MOCK untuk development tanpa API key:
> ```
> MIDTRANS_MOCK=true
> BITESHIP_MOCK=true
> ```

### 3. Setup Database

```bash
php artisan migrate --seed
```

Ini akan membuat struktur database dan mengisi data awal:
- 1 akun admin
- 17 produk (4 kategori)
- 100 customer (85 verified + 15 unverified)
- ~511 pesanan (data transaksi untuk Apriori)

### 4. Jalankan Aplikasi

```bash
composer run dev
```

Aplikasi berjalan di `http://localhost:8000`.

### 5. Akses Admin Panel

Buka `http://localhost:8000/admin` dan login dengan:
- **Email**: `admin@albasambosa.com`
- **Password**: `password`

## Fitur Utama

| Fitur | Deskripsi |
| --- | --- |
| Katalog Produk | 17 produk dalam 4 kategori, filter + pencarian real-time |
| Keranjang Belanja | Dual-mode: guest (session) + registered (database) |
| Checkout | Pickup + Delivery (Biteship GoSend/GrabExpress) |
| Pembayaran | Midtrans (VA, e-wallet, QRIS, kartu kredit/debit) |
| Admin Panel | Filament 5: kelola produk, pesanan, pengguna |
| Apriori | Market Basket Analysis — rekomendasi "Beli Bersama" |
| WhatsApp | Notifikasi milestone pesanan via Twilio |
| Privasi | Anonimisasi otomatis sesuai UU PDP |

## Testing

```bash
php artisan test --compact
```

266 tests, 664 assertions, 32 test files (Pest 4).

## Menjalankan Apriori Mining

Setelah login ke admin panel (`/admin/apriori`), klik **Generate Rules**.

Atau via command line:
```bash
php artisan apriori:mine
```

Parameter dapat diubah via modal **Settings** di dashboard Apriori atau langsung di `.env`:
```
APRIORI_MIN_SUPPORT=0.02
APRIORI_MIN_CONFIDENCE=0.6
APRIORI_MIN_TRANSACTIONS=50
```

## Struktur Proyek

```
├── app/                        # Source code (Controllers, Models, Services, Livewire)
│   ├── Actions/                # Invokable action (bisnis operasi tunggal)
│   ├── Services/               # Service layer (Apriori, Midtrans, Biteship)
│   ├── Filament/               # Admin panel (Resources, Widgets, Pages)
│   └── Livewire/               # Komponen reaktif (AddToCart, Checkout, Catalog)
├── database/
│   ├── migrations/             # 19 migration files
│   ├── factories/              # Eloquent factories untuk testing
│   └── seeders/                # Data seeder (admin, produk, customer, pesanan)
├── tests/                      # 32 test files (Pest 4)
├── docs/                       # Diagram, wireframe, design system
├── scripts/apriori/            # Python script untuk mining
└── resources/views/            # Blade template + Livewire views
```

## Lisensi

Proprietary — &copy; AlbaSambosa.
