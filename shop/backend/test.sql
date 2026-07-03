-- ShopZen Database Schema + Seed Data
-- MySQL 8.x / MariaDB
-- Run manually the first time, against your RDS instance:
--   mysql -h <RDS_ENDPOINT> -u <DB_USER> -p <DB_NAME> < test.sql
-- app.py does NOT auto-create this schema (unlike the earlier SQLite
-- version) -- run this file once yourself before starting the backend.

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- ─────────────────────────────
-- USERS
-- ─────────────────────────────
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(120) NOT NULL,
    email         VARCHAR(190) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─────────────────────────────
-- CATEGORIES  (maps 1-1 to each frontend folder)
-- ─────────────────────────────
CREATE TABLE categories (
    id     INT AUTO_INCREMENT PRIMARY KEY,
    slug   VARCHAR(60) UNIQUE NOT NULL,
    name   VARCHAR(120) NOT NULL,
    icon   VARCHAR(10)
) ENGINE=InnoDB;

INSERT INTO categories (slug, name, icon) VALUES
 ('main',          'All Products',        '🛍️'),
 ('computers',     'Computers & Laptops', '💻'),
 ('earphones',     'Earphones & Audio',   '🎧'),
 ('electronics',   'Electronics',         '📺'),
 ('phones',        'Mobile Phones',       '📱'),
 ('googleclothes', 'Fashion & Clothes',   '👗'),
 ('googlegrocery', 'Grocery',             '🌿'),
 ('googlemusic',   'Music & Instruments', '🎸'),
 ('googlepay',     'ShopZen Pay',         '💳');

-- ─────────────────────────────
-- PRODUCTS
-- ─────────────────────────────
CREATE TABLE products (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    category_id  INT NOT NULL,
    emoji        VARCHAR(10),
    name         VARCHAR(255) NOT NULL,
    price        INT NOT NULL,
    original     INT NOT NULL,
    rating       DECIMAL(2,1) DEFAULT 4.5,
    reviews      INT DEFAULT 0,
    badge        VARCHAR(20) DEFAULT '',
    off_pct      INT DEFAULT 0,
    stock        INT DEFAULT 100,
    FOREIGN KEY (category_id) REFERENCES categories(id)
) ENGINE=InnoDB;

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '💻', 'Apple MacBook Air M3 13-inch 8GB RAM 256GB SSD', 114900, 129900, 4.8, 5670, 'new', 12 FROM categories WHERE slug='computers';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🖥️', 'LG 27GN800-B 27" UltraGear QHD 144Hz Gaming Monitor', 22990, 31990, 4.5, 6780, 'prime', 28 FROM categories WHERE slug='computers';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '💻', 'Dell XPS 13 Plus Intel i7 16GB 512GB SSD', 134990, 154990, 4.6, 2310, 'deal', 13 FROM categories WHERE slug='computers';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🖱️', 'Logitech MX Master 3S Wireless Mouse', 8995, 10995, 4.7, 15200, '', 18 FROM categories WHERE slug='computers';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '⌨️', 'Keychron K8 Pro Mechanical Keyboard', 9999, 12999, 4.6, 3400, 'new', 23 FROM categories WHERE slug='computers';

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎧', 'Sony WH-1000XM5 Wireless Noise Cancelling Headphones', 24990, 34990, 4.7, 8210, 'prime', 29 FROM categories WHERE slug='earphones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎧', 'Apple AirPods Pro (2nd Gen) with USB-C', 21990, 26900, 4.8, 19800, 'deal', 18 FROM categories WHERE slug='earphones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎧', 'boAt Airdopes 141 Bluetooth Truly Wireless', 1299, 3990, 4.2, 45300, 'deal', 67 FROM categories WHERE slug='earphones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🔊', 'JBL Flip 6 Portable Wireless Bluetooth Speaker IPX7', 7499, 11999, 4.6, 34500, 'deal', 37 FROM categories WHERE slug='earphones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎧', 'Sennheiser Momentum 4 Wireless Headphones', 27990, 34990, 4.5, 1980, '', 20 FROM categories WHERE slug='earphones';

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📺', 'Samsung 55" 4K QLED Smart TV', 49990, 89990, 4.6, 7200, 'deal', 45 FROM categories WHERE slug='electronics';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📷', 'Canon EOS R50 Mirrorless Camera with 18-45mm Lens Kit', 67990, 79995, 4.4, 2140, '', 15 FROM categories WHERE slug='electronics';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎮', 'Sony PlayStation 5 Slim Digital Edition Console', 44990, 54990, 4.8, 21000, 'deal', 18 FROM categories WHERE slug='electronics';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '⌚', 'Apple Watch Series 10 GPS 42mm Starlight Aluminium', 39900, 45900, 4.6, 3890, 'deal', 13 FROM categories WHERE slug='electronics';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '☕', 'Nespresso Vertuo Next Coffee Machine', 11990, 18990, 4.5, 4100, '', 35 FROM categories WHERE slug='electronics';

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📱', 'Samsung Galaxy S24 Ultra 5G 256GB Phantom Black', 89999, 109999, 4.5, 12430, 'deal', 18 FROM categories WHERE slug='phones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📱', 'Apple iPhone 16 128GB', 79900, 82900, 4.7, 26700, 'new', 4 FROM categories WHERE slug='phones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📱', 'OnePlus 13R 5G 12GB 256GB', 39999, 45999, 4.4, 8900, 'deal', 13 FROM categories WHERE slug='phones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📱', 'Xiaomi Redmi Note 14 Pro 5G', 21999, 27999, 4.3, 15600, 'deal', 21 FROM categories WHERE slug='phones';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '📱', 'Google Pixel 9', 64999, 69999, 4.6, 3200, '', 7 FROM categories WHERE slug='phones';

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '👕', "Men's Cotton T-Shirt Pack of 5", 799, 1499, 4.2, 22000, 'deal', 47 FROM categories WHERE slug='googleclothes';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '👗', "Women's Floral Summer Dress", 1299, 2499, 4.4, 5400, 'new', 48 FROM categories WHERE slug='googleclothes';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '👟', 'Nike Air Max 270 Running Shoes', 5999, 14999, 4.6, 9800, 'deal', 60 FROM categories WHERE slug='googleclothes';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🧥', "Men's Winter Bomber Jacket", 2199, 3999, 4.3, 3100, '', 45 FROM categories WHERE slug='googleclothes';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '👜', "Women's Leather Handbag", 1899, 3499, 4.5, 2700, 'prime', 46 FROM categories WHERE slug='googleclothes';

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🌾', 'Basmati Rice 5kg Premium Aged', 549, 699, 4.5, 8700, '', 21 FROM categories WHERE slug='googlegrocery';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🫒', 'Extra Virgin Olive Oil 1L', 899, 1199, 4.6, 3200, 'new', 25 FROM categories WHERE slug='googlegrocery';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🍫', 'Assorted Chocolate Gift Box', 499, 799, 4.7, 6100, 'deal', 38 FROM categories WHERE slug='googlegrocery';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '☕', 'Arabica Coffee Beans 500g', 649, 899, 4.4, 4300, '', 28 FROM categories WHERE slug='googlegrocery';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🌱', 'Indoor Plant Combo Set of 4', 599, 999, 4.3, 1900, 'prime', 40 FROM categories WHERE slug='googlegrocery';

INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎸', 'Acoustic Guitar Beginner Pack', 3499, 5999, 4.5, 2600, 'deal', 42 FROM categories WHERE slug='googlemusic';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎹', 'Casio CT-S300 61-Key Portable Keyboard', 10999, 13999, 4.6, 1400, 'new', 21 FROM categories WHERE slug='googlemusic';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🥁', 'Electronic Drum Practice Pad Set', 4999, 7999, 4.3, 900, '', 37 FROM categories WHERE slug='googlemusic';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎤', 'USB Condenser Microphone Studio Kit', 3299, 4999, 4.5, 3100, 'deal', 34 FROM categories WHERE slug='googlemusic';
INSERT INTO products (category_id, emoji, name, price, original, rating, reviews, badge, off_pct)
SELECT id, '🎻', 'Student Violin 4/4 Full Size with Case', 6499, 8999, 4.2, 560, '', 28 FROM categories WHERE slug='googlemusic';

-- ─────────────────────────────
-- CART ITEMS  (tied to a logged-in user)
-- ─────────────────────────────
CREATE TABLE cart_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    INT NOT NULL DEFAULT 1,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id),
    UNIQUE KEY uniq_user_product (user_id, product_id)
) ENGINE=InnoDB;

-- ─────────────────────────────
-- ORDERS  (created by /api/checkout -- triggers the confirmation email)
-- ─────────────────────────────
CREATE TABLE orders (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT NOT NULL,
    total_amount   INT NOT NULL,
    payment_method VARCHAR(60) DEFAULT 'ShopZen Pay',
    status         VARCHAR(30) DEFAULT 'placed',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE order_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    INT NOT NULL,
    price       INT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB;
