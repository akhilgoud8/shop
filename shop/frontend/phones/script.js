// ══════════════════ SHOPZEN SHARED SHELL ══════════════════
// Shared across every page: nav, subnav, cart drawer, footer, auth, API helpers.
// API_BASE is relative ('/api') because Nginx reverse-proxies /api/* to the
// backend EC2 on the SAME origin as the frontend -- see nginx/shopzen.conf.
// That means the Flask session cookie works normally with no CORS needed.
const API_BASE = '/api';
const ROOT = '/frontend/';
const CATEGORIES = [{"slug": "main", "name": "All", "icon": "\u2630"}, {"slug": "phones", "name": "Mobiles", "icon": "\ud83d\udcf1"}, {"slug": "computers", "name": "Computers", "icon": "\ud83d\udcbb"}, {"slug": "earphones", "name": "Audio", "icon": "\ud83c\udfa7"}, {"slug": "electronics", "name": "Electronics", "icon": "\ud83d\udcfa"}, {"slug": "googleclothes", "name": "Fashion", "icon": "\ud83d\udc57"}, {"slug": "googlegrocery", "name": "Grocery", "icon": "\ud83c\udf3f"}, {"slug": "googlemusic", "name": "Music", "icon": "\ud83c\udfb8"}, {"slug": "googlepay", "name": "ShopZen Pay \u2605", "icon": "\ud83d\udcb3"}];

let CURRENT_USER = null; // populated by checkAuth() on every page load

function fmtINR(n) { return '₹' + Number(n).toLocaleString('en-IN'); }

function stars(rating) {
  const full = Math.floor(rating), half = rating % 1 >= 0.5;
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(5 - full - (half ? 1 : 0));
}

// ── AUTH ──────────────────────────────────────────────────────────
async function checkAuth() {
  try {
    const res = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
    if (!res.ok) { CURRENT_USER = null; return null; }
    const data = await res.json();
    CURRENT_USER = data.user;
    return CURRENT_USER;
  } catch (e) {
    CURRENT_USER = null;
    return null;
  }
}

function requireLoginOrRedirect() {
  if (!CURRENT_USER) {
    const returnTo = encodeURIComponent(window.location.pathname);
    window.location.href = `${ROOT}auth/login.html?next=${returnTo}`;
    return false;
  }
  return true;
}

async function logout() {
  try { await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' }); }
  catch (e) {}
  window.location.href = ROOT + 'main/index.html';
}

// ── CART (server-backed -- requires login) ──────────────────────────
async function loadCart() {
  if (!CURRENT_USER) return { items: [], total: 0, count: 0 };
  try {
    const res = await fetch(`${API_BASE}/cart`, { credentials: 'include' });
    if (!res.ok) return { items: [], total: 0, count: 0 };
    return await res.json();
  } catch (e) {
    return { items: [], total: 0, count: 0 };
  }
}

async function updateCartBadge() {
  const el = document.getElementById('cartCount');
  if (!el) return;
  const cart = await loadCart();
  el.textContent = cart.count || 0;
}

async function addToCart(product) {
  if (!requireLoginOrRedirect()) return;
  try {
    await fetch(`${API_BASE}/cart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ product_id: product.id || 0, quantity: 1 })
    });
  } catch (e) {
    alert('Could not add to cart -- please try again.');
    return;
  }
  await updateCartBadge();
  await renderCartDrawer();
  flashCartIcon();
}

async function changeQty(productId, delta, currentQty) {
  const newQty = currentQty + delta;
  try {
    await fetch(`${API_BASE}/cart/${productId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ quantity: newQty })
    });
  } catch (e) {}
  await updateCartBadge();
  await renderCartDrawer();
}

async function removeFromCart(productId) {
  try {
    await fetch(`${API_BASE}/cart/${productId}`, { method: 'DELETE', credentials: 'include' });
  } catch (e) {}
  await updateCartBadge();
  await renderCartDrawer();
}

function flashCartIcon() {
  const el = document.querySelector('.cart-btn');
  if (!el) return;
  el.style.transform = 'scale(1.15)';
  setTimeout(() => el.style.transform = '', 200);
}

async function openCart() {
  if (!requireLoginOrRedirect()) return;
  await renderCartDrawer();
  document.getElementById('cartOverlay').classList.add('open');
  document.getElementById('cartDrawer').classList.add('open');
}
function closeCart() {
  document.getElementById('cartOverlay').classList.remove('open');
  document.getElementById('cartDrawer').classList.remove('open');
}

async function renderCartDrawer() {
  const body = document.getElementById('cartDrawerBody');
  const footBox = document.getElementById('cartDrawerFoot');
  if (!body) return;
  if (!CURRENT_USER) {
    body.innerHTML = '<div class="empty-state">Sign in to view your cart.</div>';
    footBox.innerHTML = '';
    return;
  }
  const cart = await loadCart();
  if (!cart.items || cart.items.length === 0) {
    body.innerHTML = '<div class="empty-state">Your cart is empty.<br>Go find something you love 🛍️</div>';
    footBox.innerHTML = '';
    return;
  }
  body.innerHTML = cart.items.map(item => `
    <div class="cart-line">
      <div class="emoji">${item.emoji || '🛒'}</div>
      <div class="info">
        <div>${item.name}</div>
        <div class="qty-controls">
          <button onclick="changeQty(${item.product_id}, -1, ${item.quantity})">−</button>
          <span>${item.quantity}</span>
          <button onclick="changeQty(${item.product_id}, 1, ${item.quantity})">+</button>
          <span style="margin-left:8px;color:var(--mid-gray);cursor:pointer" onclick="removeFromCart(${item.product_id})">✕</span>
        </div>
      </div>
      <div style="font-weight:700">${fmtINR(item.price * item.quantity)}</div>
    </div>
  `).join('');
  footBox.innerHTML = `
    <div class="total-row"><span>Total</span><span>${fmtINR(cart.total)}</span></div>
    <button class="btn-primary" style="width:100%" onclick="goToCheckout()">Proceed to ShopZen Pay →</button>
  `;
}

function goToCheckout() {
  window.location.href = ROOT + 'googlepay/index.html';
}

// ── SHELL: topbar / nav / subnav ──
async function renderShell(activeSlug) {
  const mount = document.getElementById('shell');
  if (!mount) return;
  await checkAuth();

  const subnavLinks = CATEGORIES.map(c => {
    const href = c.slug === activeSlug ? '#' : ROOT + c.slug + '/index.html';
    const cls = c.slug === activeSlug ? 'active' : '';
    return `<a href="${href}" class="${cls}">${c.icon} ${c.name}</a>`;
  }).join('');

  const accountBlock = CURRENT_USER
    ? `<div class="nav-link" style="cursor:pointer" onclick="logout()">
         <span>Hello, ${CURRENT_USER.name.split(' ')[0]}</span>
         <strong>Sign Out ▾</strong>
       </div>`
    : `<a class="nav-link" href="${ROOT}auth/login.html">
         <span>Hello, Sign In</span>
         <strong>Account &amp; Lists ▾</strong>
       </a>`;

  mount.innerHTML = `
    <div class="topbar">
      <div class="topbar-links">
        <a href="${ROOT}googlepay/index.html">Sell on ShopZen</a>
        <a href="#">Affiliate</a>
        <a href="#">Business</a>
      </div>
      <div class="topbar-links">
        <a href="#">Help</a>
        <a href="#">Download App</a>
        <a href="#">🇮🇳 India</a>
      </div>
    </div>
    <nav>
      <a href="${ROOT}main/index.html" class="logo">Shop<span>Zen</span></a>
      <div class="location">
        <span>Deliver to</span>
        <strong>📍 Hyderabad 500076</strong>
      </div>
      <div class="search-bar">
        <select id="searchScope">
          <option>All</option>
          <option>Electronics</option>
          <option>Clothing</option>
          <option>Books</option>
          <option>Home</option>
          <option>Sports</option>
        </select>
        <input type="text" placeholder="Search products, brands and more…" id="searchInput">
        <button class="search-btn" onclick="handleSearch()">🔍</button>
      </div>
      <div class="nav-actions">
        ${accountBlock}
        <div class="nav-link">
          <span>Returns</span>
          <strong>&amp; Orders</strong>
        </div>
        <div class="cart-btn nav-link" onclick="openCart()">
          <span class="cart-icon">🛒</span>
          <span class="cart-count" id="cartCount">0</span>
          <span class="cart-label">Cart</span>
        </div>
      </div>
    </nav>
    <div class="subnav">${subnavLinks}</div>

    <div class="cart-drawer-overlay" id="cartOverlay" onclick="closeCart()"></div>
    <div class="cart-drawer" id="cartDrawer">
      <div class="cart-drawer-head">
        <span>Your Cart</span>
        <span class="close" onclick="closeCart()">✕</span>
      </div>
      <div class="cart-drawer-body" id="cartDrawerBody"></div>
      <div class="cart-drawer-foot" id="cartDrawerFoot"></div>
    </div>
  `;
  await updateCartBadge();
  const input = document.getElementById('searchInput');
  if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') handleSearch(); });
}

function handleSearch() {
  const q = document.getElementById('searchInput').value.trim();
  if (!q) return;
  fetch(`${API_BASE}/products/search?q=${encodeURIComponent(q)}`)
    .then(r => r.json())
    .then(results => alert(`Found ${results.length} result(s) for "${q}".\n(Connect a results page to display these.)`))
    .catch(() => alert(`Searching for: "${q}"`));
}

// ── FOOTER ──
function renderFooter() {
  const mount = document.getElementById('siteFooter');
  if (!mount) return;
  mount.innerHTML = `
    <footer>
      <div class="footer-top">
        <div class="footer-col">
          <h4>Get to Know Us</h4>
          <a href="#">About ShopZen</a>
          <a href="#">Careers</a>
          <a href="#">Press Releases</a>
          <a href="#">ShopZen Cares</a>
          <a href="#">Gift Cards</a>
        </div>
        <div class="footer-col">
          <h4>Make Money with Us</h4>
          <a href="#">Sell on ShopZen</a>
          <a href="#">Affiliate Program</a>
          <a href="#">Advertise Your Products</a>
          <a href="${ROOT}googlepay/index.html">ShopZen Pay</a>
        </div>
        <div class="footer-col">
          <h4>ShopZen Payment Products</h4>
          <a href="${ROOT}googlepay/index.html">ShopZen Pay</a>
          <a href="#">EMI Options</a>
          <a href="#">Pay on Delivery</a>
          <a href="#">ShopZen Business Card</a>
        </div>
        <div class="footer-col">
          <h4>Let Us Help You</h4>
          <a href="${ROOT}auth/login.html">Your Account</a>
          <a href="#">Your Orders</a>
          <a href="#">Returns &amp; Replacements</a>
          <a href="#">Customer Service</a>
          <a href="#">Help</a>
        </div>
      </div>
      <div class="footer-bottom">
        <div class="footer-logo">Shop<span>Zen</span></div>
        <div>© 2026 ShopZen.in · Privacy Policy · Terms of Service</div>
        <div>🇮🇳 India · ₹ INR · English</div>
      </div>
    </footer>
  `;
}

// ── DATA FETCH (backend first, static fallback second) ──
async function fetchProducts(categorySlug, fallback) {
  try {
    const res = await fetch(`${API_BASE}/products?category=${encodeURIComponent(categorySlug)}`);
    if (!res.ok) throw new Error('bad response');
    const data = await res.json();
    if (Array.isArray(data) && data.length) return data;
    return fallback;
  } catch (e) {
    return fallback; // backend not reachable -- use the bundled static data
  }
}
function productCard(p) {
  const badgeLabel = p.badge === 'deal' ? '🔥 Deal' : p.badge === 'new' ? '✨ New' : p.badge === 'prime' ? '⭐ Prime' : '';
  return `
    <div class="product-card" onclick="addToCart({emoji:'${p.emoji}', name:${JSON.stringify(p.name)}, price:${p.price}, id:${p.id || 0}})">
      <div class="product-img">
        ${p.emoji}
        ${badgeLabel ? `<span class="badge badge-${p.badge}">${badgeLabel}</span>` : ''}
      </div>
      <div class="product-body">
        <div class="product-name">${p.name}</div>
        <div class="stars">
          <span>${stars(p.rating)}</span>
          <span class="review-count">(${Number(p.reviews).toLocaleString('en-IN')})</span>
        </div>
        <div class="price-row">
          <span class="price">${fmtINR(p.price)}</span>
          <span class="price-original">${fmtINR(p.original)}</span>
          <span class="discount-pct">${p.off}% off</span>
        </div>
        <button class="add-btn" onclick="event.stopPropagation(); addToCart({emoji:'${p.emoji}', name:${JSON.stringify(p.name)}, price:${p.price}, id:${p.id || 0}})">Add to Cart 🛒</button>
      </div>
    </div>
  `;
}
// ══════════════════ PHONES PAGE ══════════════════
const FALLBACK_PRODUCTS = [{"emoji": "📱", "name": "Samsung Galaxy S24 Ultra 5G 256GB Phantom Black", "price": 89999, "original": 109999, "rating": 4.5, "reviews": 12430, "badge": "deal", "off": 18}, {"emoji": "📱", "name": "Apple iPhone 16 128GB", "price": 79900, "original": 82900, "rating": 4.7, "reviews": 26700, "badge": "new", "off": 4}, {"emoji": "📱", "name": "OnePlus 13R 5G 12GB 256GB", "price": 39999, "original": 45999, "rating": 4.4, "reviews": 8900, "badge": "deal", "off": 13}, {"emoji": "📱", "name": "Xiaomi Redmi Note 14 Pro 5G", "price": 21999, "original": 27999, "rating": 4.3, "reviews": 15600, "badge": "deal", "off": 21}, {"emoji": "📱", "name": "Google Pixel 9", "price": 64999, "original": 69999, "rating": 4.6, "reviews": 3200, "badge": "", "off": 7}];

async function renderProducts() {
  const grid = document.getElementById('productsGrid');
  const products = await fetchProducts('phones', FALLBACK_PRODUCTS);
  if (!products.length) {
    grid.innerHTML = '<div class="empty-state">No products found in this category yet.</div>';
    return;
  }
  grid.innerHTML = products.map(productCard).join('');
}

// INIT
(async function init() {
  await renderShell('phones');
  renderFooter();
  await renderCartDrawer();
  renderProducts();
})();
